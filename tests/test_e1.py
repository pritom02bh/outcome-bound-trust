"""E1: ablation grid (scripted buyer). Grid, config overrides, Pareto front and default pick."""
import json

import pytest

import eval.run as er
from eval.run import EvalConfig
from obt.llm import CostMeter


def test_grid_matches_fixes_and_d22():
    from eval.e1 import grid
    g = grid()
    obt = [x for x in g if x[1] == "obt"]
    rep = [x for x in g if x[1] == "reputation"]
    assert len(obt) == 4 * 3 * 3 and len(rep) == 4 * 4
    assert {tuple(sorted(o[2].items())) for o in obt} == {
        (("b0_frac", b), ("grace", d), ("window", w)) for b in (0.0, 0.025, 0.05, 0.10) for w in (0, 5, 10)
        for d in (0, 1, 2)}
    assert {(r[2]["rep_cap"], r[2]["rep_theta"]) for r in rep} == {
        (c, t) for c in (50.0, 100.0, 200.0, 400.0) for t in (0.6, 0.7, 0.8, 0.9)}
    assert ("none", "none", {}) in g and ("provenance", "provenance", {}) in g
    assert len({x[0] for x in g}) == len(g)                       # unique run-dir names


def test_sim_overrides_reach_the_sim_and_the_config_hash(tmp_path, rule_llm):
    base = dict(backend="fake", model="fake", buyer="scripted", scenarios=(1,), defenses=("obt",), rounds=6,
                extractor_eval=False)
    a, b = EvalConfig(**base), EvalConfig(**base, sim={"b0_frac": 0.1, "window": 0, "grace": 2})
    assert er.config_hash(a) != er.config_hash(b)
    sc = er.sim_config(b, "obt")
    assert (sc.b0_frac, sc.window, sc.grace) == (0.1, 0, 2)
    er.run_eval(b, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    r = json.loads((tmp_path / "results.jsonl").read_text().splitlines()[0])
    assert r["meta"]["sim"] == {"b0_frac": 0.1, "window": 0, "grace": 2}


def test_unknown_override_is_refused():
    with pytest.raises(TypeError):
        er.sim_config(EvalConfig(sim={"b0": 1}), "obt")


def test_pareto_front_and_default_pick():
    from eval.e1 import pareto_front, pick_default
    pts = {"a": (0.0, 100.0), "b": (10.0, 50.0), "c": (20.0, 60.0), "d": (30.0, 5.0), "e": (5.0, 100.0)}
    assert pareto_front(pts) == ["a", "b", "d"]
    assert pick_default(pts) == "d"                                 # min utility + loss on the front


def test_e1_summary_uses_the_shared_none_baseline(tmp_path, rule_llm):
    from eval import e1
    root = tmp_path / "e1"
    kw = dict(backend="fake", model="fake", scenarios=(1, 2), seeds=(1,), rounds=6)
    for name, d, sim in [("none", "none", {}), ("obt_b0.05_W10_d0", "obt", {"b0_frac": 0.05, "window": 10,
                                                                             "grace": 0})]:
        e1.run_point(root, name, d, sim, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm, **kw)
    s = e1.summarize_grid(root)
    p = s["points"]["obt_b0.05_W10_d0"]
    rows = {n: json.loads(line) for n in ("none", "obt_b0.05_W10_d0")
            for line in (root / n / "results.jsonl").read_text().splitlines() if json.loads(line)["scenario"] == 1}
    assert p["utility_cost"] == pytest.approx(rows["obt_b0.05_W10_d0"]["total_cost"] - rows["none"]["total_cost"])
    assert set(s) >= {"points", "front", "default", "reputation_for_e2"}


def test_make_results_builds_the_e1_tables_and_pareto_figure(tmp_path, rule_llm):
    from eval import e1, results
    runs = tmp_path / "runs"
    kw = dict(backend="fake", model="fake", scenarios=(1, 2), seeds=(1,), rounds=6)
    for name, d, sim in [("none", "none", {}), ("obt_b0.05_W10_d0", "obt", {"b0_frac": 0.05, "window": 10,
                                                                             "grace": 0}),
                         ("rep_cap200_th0.8", "reputation", {"rep_cap": 200.0, "rep_theta": 0.8})]:
        e1.run_point(runs / "e1", name, d, sim, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm, **kw)
    out = tmp_path / "results"
    results.build(runs, out)
    assert (out / "e1" / "e1.md").exists() and (out / "e1" / "e1_pareto.svg").exists()
    table = (out / "e1" / "e1.md").read_text()
    assert "obt_b0.05_W10_d0" in table and "default" in table
    assert not (out / "e1__none").exists()                        # grid points are not separate evals


def test_cli_sim_overrides_are_typed():
    assert er.parse_sim("b0_frac=0.025,window=5,grace=1,rep_cap=100,rep_theta=0.7") == {
        "b0_frac": 0.025, "window": 5, "grace": 1, "rep_cap": 100.0, "rep_theta": 0.7}
    assert er.parse_sim("") == {}
    with pytest.raises(ValueError):
        er.parse_sim("b0=1")
