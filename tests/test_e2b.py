"""E2b (D30): the frozen "trust-aware" buyer view variant, its plumbing, and the reputation score in the trace."""
import hashlib
import json

import eval.run as er
from eval.run import EvalConfig, run_eval
from obt import config
from obt.agent import LLMBuyer, ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import GameConfig
from obt.llm import LLM, CostMeter
from obt.memory_view import TRUST_AWARE_OBT, TRUST_AWARE_REP, render
from obt.sim import Sim, SimConfig

G = GameConfig(rounds=8)


def sim(defense):
    s = Sim(SimConfig(game=G, defense=defense), 1, make_supplier(1, G, 1), ScriptedClaimBuyer(G))
    s.run()
    return s


def test_variant_text_is_frozen_by_hash():
    assert config.BUYER_TRUST_AWARE_SHA256 == hashlib.sha256((TRUST_AWARE_OBT + TRUST_AWARE_REP).encode()).hexdigest()


def test_trust_aware_view_explains_growth_with_code_numbers():
    s = sim("obt")
    v = s.view()
    base, aware = render(v), render(v, variant="trust-aware")
    assert "TRUST GROWTH" not in base and "TRUST GROWTH (computed by code)" in aware
    assert aware.startswith(base)                                    # only adds lines
    s = sim("reputation")
    aware = render(s.view(), variant="trust-aware")
    assert "REPUTATION GROWTH (computed by code)" in aware and "TRUST GROWTH" not in aware


def test_variant_reaches_the_buyer_and_the_run_record(tmp_path):
    seen = []

    def fake(system, user):
        seen.append(user)
        if "checkable claims" in system:
            return json.dumps({"claims": []})
        return json.dumps({"s_main_order": None, "backup_qty": 20, "next_lot_request": 1, "note": "",
                           "note_cites": []})
    ec = EvalConfig(backend="fake", model="fake", buyer="llm", scenarios=(1,), seeds=(1,), rounds=3,
                    defenses=("obt",), buyer_variant="trust-aware", extractor_eval=False)
    run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=fake)
    assert any("TRUST GROWTH (computed by code)" in u for u in seen)
    r = json.loads((tmp_path / "results.jsonl").read_text().splitlines()[0])
    assert r["meta"]["buyer_variant"] == "trust-aware"
    assert er.config_hash(ec) != er.config_hash(EvalConfig(backend="fake", model="fake", buyer="llm"))
    assert EvalConfig().buyer_variant is None and LLMBuyer(LLM("fake", "f", fake=fake), G).variant is None


def test_reputation_score_is_in_the_trace():
    t = sim("reputation").trace
    assert all("rep" in x for x in t) and all(0 < x["rep"]["score"] < 1 for x in t)
    assert "rep" not in sim("obt").trace[0]


def test_e2b_report_overlays_e2_and_e1(tmp_path):
    from eval import results, stats

    def run_rows(d, s, B, share_main, rep=None):
        tr = [{"round": t, "B": B + t, "P": 0.0, "actions": [["ORDER", "S_main", share_main, 5.0, "EXECUTED", "OK", []],
                                                        ["ORDER", "S_backup", 10 - share_main, 6.0, "EXECUTED", "OK", []]],
               **({"rep": {"score": rep, "resolved": t, "limit": 100.0}} if rep else {})} for t in (1, 2, 3)]
        return {"scenario": 1, "defense": d, "seed": s, "total_cost": 100.0, "trace": tr,
                "metrics": {"main_orders_blocked": 0, "loss_bound": {"damage": None, "sum_bound": None, "ok": None,
                                                                    "events": []}}}
    e2b = [run_rows("obt", 1, 10, 5), run_rows("rep-strict", 1, 5, 3, rep=0.7)]
    e2 = [run_rows("obt", 1, 5, 1), run_rows("rep-strict", 1, 5, 1)]
    e1 = {"obt": [run_rows("obt", 1, 20, 4)], "rep-strict": [run_rows("rep-strict", 1, 5, 2, rep=0.6)]}
    svg = stats.e2b_trust_svg(e2b, e2, e1)
    assert svg.startswith(b"<?xml") and svg == stats.e2b_trust_svg(e2b, e2, e1)
    md = stats.e2b_report(e2b, e2)
    assert "trust-aware" in md and "S_main unit share" in md and "damage vs bound" in md.lower()


def test_e2c_section_merges_with_e2(tmp_path, rule_llm):
    from eval import results
    base = dict(backend="fake", model="fake", buyer="llm", scenarios=(1, 2), seeds=(1,), rounds=6,
                sim={"b0_frac": 0.05, "window": 0, "grace": 0}, extractor_eval=False)

    def fake(system, user):
        if "checkable claims" in system:
            return rule_llm(system, user)
        return json.dumps({"s_main_order": None, "backup_qty": 20, "next_lot_request": 5, "note": "",
                           "note_cites": []})
    run_eval(EvalConfig(**base, defenses=("none", "obt")), tmp_path / "runs" / "e2",
             meter=CostMeter(tmp_path / "c.json"), fake=fake)
    run_eval(EvalConfig(**base, defenses=("obt+planner",)), tmp_path / "runs" / "e2c",
             meter=CostMeter(tmp_path / "c.json"), fake=fake)
    results.build(tmp_path / "runs", tmp_path / "out")
    ci = (tmp_path / "out" / "e2c" / "ci.md").read_text()
    assert "| obt+planner |" in ci and "| obt |" in ci
    assert (tmp_path / "out" / "e2c" / "trust_over_time.svg").exists()
