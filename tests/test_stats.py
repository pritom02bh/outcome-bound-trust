"""Final-report statistics: bootstrap CIs over seeds, utility cost, S_main share, OBT damage vs bound."""
import pytest

from eval import stats


def row(n, d, s, cost, **m):
    metrics = {"main_orders_blocked": 0, "main_orders_executed": 1,
               "loss_bound": {"damage": None, "sum_bound": None, "ok": None, "events": []}}
    metrics.update(m)
    return {"scenario": n, "defense": d, "seed": s, "total_cost": cost, "metrics": metrics, "trace": []}


def test_bootstrap_ci_is_deterministic_and_brackets_the_mean():
    lo, hi = stats.bootstrap_ci([1.0, 2.0, 6.0])
    assert lo <= 3.0 <= hi and (lo, hi) == stats.bootstrap_ci([1.0, 2.0, 6.0])
    assert stats.bootstrap_ci([5.0]) == (5.0, 5.0)
    assert stats.bootstrap_ci([]) == (None, None)


def test_bootstrap_resamples_seeds_with_replacement():
    lo, hi = stats.bootstrap_ci([0.0, 10.0])
    assert lo == pytest.approx(0.0) and hi == pytest.approx(10.0)


def test_attack_loss_per_seed_averages_scenarios_2_to_12():
    rows = [row(1, "obt", 1, 100), row(2, "obt", 1, 130), row(3, "obt", 1, 110),
            row(1, "obt", 2, 100), row(2, "obt", 2, 100), row(3, "obt", 2, 100)]
    assert stats.attack_loss_by_seed(rows, "obt") == {1: 20.0, 2: 0.0}


def test_utility_cost_is_against_none_on_the_same_seed():
    rows = [row(1, "none", 1, 100), row(1, "obt", 1, 130), row(1, "none", 2, 90), row(1, "obt", 2, 100)]
    assert stats.utility_cost_by_seed(rows, "obt") == {1: 30.0, 2: 10.0}


def test_damage_vs_bound_summary():
    ev = [{"bound": 10.0, "apriori": 40.0}, {"bound": 5.0, "apriori": 40.0}]
    rows = [row(2, "obt", 1, 0, loss_bound={"damage": 12.0, "sum_bound": 15.0, "ok": True, "events": ev}),
            row(4, "obt", 1, 0, loss_bound={"damage": 1.0, "sum_bound": 10.0, "ok": True,
                                            "events": [{"bound": 10.0, "apriori": 40.0}]}),
            row(1, "obt", 1, 0, loss_bound={"damage": 0.0, "sum_bound": 0.0, "ok": True, "events": []})]
    s = stats.damage_vs_bound(rows)
    assert s["runs_with_events"] == 2 and s["events"] == 3 and s["all_ok"]
    assert s["total_damage"] == 13.0 and s["total_bound"] == 25.0
    assert s["max_ratio"] == pytest.approx(0.8) and s["min_ratio"] == pytest.approx(0.1)


def test_report_markdown_has_every_section():
    rows = [row(n, d, s, 100 + n * (d == "none") + s) for n in (1, 2) for d in ("none", "obt") for s in (1, 2, 3)]
    md = stats.report(rows)
    for heading in ("Attack loss per defense", "Utility cost per defense", "Loss from lies per scenario",
                    "OBT damage vs bound", "95% CI"):
        assert heading in md
