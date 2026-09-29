"""D35 horizon check: utility cost as % of the honest run's total cost at T=50 vs T=100 (scripted buyer)."""
import json

from eval import horizon
from obt.llm import CostMeter


def test_points_are_the_obt_default_and_the_chosen_reputation_config():
    p = {name: (d, sim) for name, d, sim in horizon.POINTS}
    assert p["none"] == ("none", {})
    assert p["obt"] == ("obt", {"b0_frac": 0.05, "window": 0, "grace": 0})
    assert p["rep-n18"] == ("reputation", {"rep_n0": 18, "rep_theta": 0.9, "rep_cap": 200.0})


def test_summary_compares_both_horizons(tmp_path, rule_llm):
    kw = dict(backend="fake", model="fake", scenarios=(1, 2), seeds=(1,))
    for T, root in ((50, tmp_path / "t50"), (100, tmp_path / "t100")):
        horizon.run(root, rounds=T, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm, rounds_override=T // 5,
                    **kw)
    s = horizon.summarize({50: tmp_path / "t50", 100: tmp_path / "t100"})
    for d in ("obt", "rep-n18"):
        for T in ("50", "100"):
            v = s["defenses"][d][T]
            assert set(v) >= {"utility_cost", "utility_pct", "attack_loss", "honest_cost_none"}
            assert abs(v["utility_pct"] - 100 * v["utility_cost"] / v["honest_cost_none"]) < 1e-6
    json.dumps(s)
