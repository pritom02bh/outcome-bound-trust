import json
import re

from obt.agent import LLMBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import BACKUP, MAIN, GameConfig
from obt.llm import LLM
from obt.sim import Sim, SimConfig
from tests.test_extractor_view import CANARIES, InjectionSupplier

G = GameConfig()


def offer_ids(user):
    return re.findall(r"\[(S_main#\d+\.\d+)\] (?:DELIVERY|PRICE)", user.split("RECENT S_main CLAIMS")[0])


def decision(cite=(), qty=0, backup=10, lot=20, **extra):
    d = {"s_main_order": {"cite": list(cite), "qty": qty} if (cite or qty) else None,
         "backup_qty": backup, "next_lot_request": lot, "note": "n", "note_cites": list(cite)[:1]}
    d.update(extra)
    return json.dumps(d)


def make(tmp_path, fn, defense="obt", supplier=None, rounds=None):
    cfg = G if rounds is None else GameConfig(rounds=rounds)
    llm = LLM("fake", "fake", fake=fn, log_path=tmp_path / "calls.jsonl")
    buyer = LLMBuyer(llm, cfg, defense)
    sim = Sim(SimConfig(game=cfg, defense=defense), 1, supplier or make_supplier(1, cfg, 1), buyer)
    return sim, buyer


def main_actions(sim):
    return [a for a in sim.actions if a.counterparty == MAIN]


def test_obt_order_value_comes_from_claims_not_llm(tmp_path):
    def fn(system, user):
        if "BLOCKED with reason" in user:
            return json.dumps({"backup_qty": 0})
        # Claims lot 1 at b0; LLM tries to inflate qty and smuggle a value/trust field.
        return decision(offer_ids(user), qty=999, backup=0, lot=1, value=0.01, trust_budget=1e9)
    sim, _ = make(tmp_path, fn, rounds=3)
    sim.run()
    execd = [a for a in main_actions(sim) if a.was_executed]
    assert execd
    for a in execd:
        dels = [sim.ledger[k] for k in a.cited_claims if sim.ledger[k].template == "DELIVERY"]
        assert a.qty == sum(c.slots["qty"] for c in dels) and a.qty != 999
        assert a.value == a.qty * 5.0
    assert sim.budget.B(MAIN, sim.game.round) <= 5.0 + max(a.value for a in execd)


def test_block_triggers_one_replan_call(tmp_path):
    calls = []

    def fn(system, user):
        calls.append(user)
        if "BLOCKED with reason OVER_BUDGET" in user:
            return json.dumps({"backup_qty": 33})
        return decision(offer_ids(user), backup=0, lot=100)   # 100-unit lot is way over b0
    sim, buyer = make(tmp_path, fn, rounds=3)
    sim.run()
    blocked = [a for a in main_actions(sim) if a.status == "BLOCKED"]
    assert blocked and all(a.reason == "OVER_BUDGET" for a in blocked)
    assert buyer.stats["replans"] == len(blocked)
    backups = [a for a in sim.actions if a.counterparty == BACKUP]
    assert [a.qty for a in backups if a.round in {b.round for b in blocked}] == [33] * len(blocked)


def test_unparseable_output_falls_back_to_backup(tmp_path):
    sim, buyer = make(tmp_path, lambda s, u: "I think we should order some widgets!", rounds=4)
    sim.run()
    assert buyer.stats["parse_failures"] == 4
    assert not main_actions(sim)
    assert any(a.counterparty == BACKUP for a in sim.actions)


def test_cannot_cite_untestable_or_foreign_ids(tmp_path):
    def fn(system, user):
        if "BLOCKED with reason" in user:
            return json.dumps({"backup_qty": 0})
        return decision(["S_main#1.9", "S_backup#1.1"], backup=0)
    sim, _ = make(tmp_path, fn, rounds=2)
    sim.run()
    assert {a.reason for a in main_actions(sim)} == {"UNKNOWN_CLAIM"}


def test_selfcheck_veto_blocks_main_order(tmp_path):
    def fn(system, user):
        if "procurement auditor" in system:
            return json.dumps({"trustworthy": False, "reason": "no"})
        if "BLOCKED with reason" in user:
            return json.dumps({"backup_qty": 7})
        return decision(qty=20, backup=0)
    sim, buyer = make(tmp_path, fn, defense="selfcheck", rounds=3)
    sim.run()
    acts = main_actions(sim)
    assert acts and all(a.status == "BLOCKED" and a.reason == "SELF_CHECK" for a in acts)
    assert buyer.stats["selfcheck_vetoes"] == 3
    assert [a.qty for a in sim.actions if a.counterparty == BACKUP] == [7, 7, 7]


def test_no_defense_orders_by_qty_ungated(tmp_path):
    sim, _ = make(tmp_path, lambda s, u: decision(qty=40, backup=0), defense="none", rounds=3)
    sim.run()
    acts = main_actions(sim)
    assert [a.qty for a in acts] == [40, 40, 40] and all(a.reason == "UNGATED" for a in acts)


def test_llm_prompt_has_no_raw_text_under_obt(tmp_path):
    for defense, leaks in (("obt", False), ("none", True), ("selfcheck", True)):
        seen = []

        def fn(system, user):
            seen.append(system + user)
            if "procurement auditor" in system:
                return json.dumps({"trustworthy": True, "reason": ""})
            return decision(offer_ids(user), qty=5, backup=10)
        sim, _ = make(tmp_path, fn, defense=defense, supplier=InjectionSupplier(G, 3), rounds=6)
        sim.run()
        blob = "\n".join(seen)
        assert any(c in blob for c in CANARIES) is leaks, defense
        if not leaks:
            assert "OVERRIDE" not in blob and "bankrupt" not in blob
