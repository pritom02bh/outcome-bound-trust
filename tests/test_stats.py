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


def trace_row(n, d, s, cost, rounds):
    """rounds: list of (S_main units, backup units) executed per round."""
    tr = [{"round": t + 1, "actions": [["ORDER", "S_main", m, 5.0 * m, "EXECUTED", "OK", []],
                                        ["ORDER", "S_backup", b, 6.0 * b, "EXECUTED", "OK", []]]}
          for t, (m, b) in enumerate(rounds)]
    r = row(n, d, s, cost)
    r["trace"] = tr
    return r


def test_share_by_round_is_the_mean_over_seeds():
    rows = [trace_row(1, "obt", 1, 100, [(0, 10), (5, 5)]), trace_row(1, "obt", 2, 100, [(10, 0), (5, 5)])]
    assert stats.share_by_round(rows, "obt") == [0.5, 0.5]
    rows.append(trace_row(1, "obt", 3, 100, [(0, 0), (1, 3)]))       # a round with no orders doesn't count
    assert stats.share_by_round(rows, "obt") == [0.5, (0.5 + 0.5 + 0.25) / 3]


def test_utility_cost_as_a_percent_of_the_honest_no_defense_cost():
    rows = [row(1, "none", 1, 200), row(1, "obt", 1, 210), row(1, "none", 2, 100), row(1, "obt", 2, 120)]
    assert stats.utility_pct_by_seed(rows, "obt") == {1: 5.0, 2: 20.0}


def test_report_has_scenario_9_and_percent_sections():
    rows = [row(n, d, s, 100 + n * (d == "none") + s) for n in (1, 9) for d in ("none", "obt") for s in (1, 2)]
    md = stats.report(rows)
    assert "Scenario 9 (noisy-honest) utility cost" in md and "% of the honest run's total cost" in md


def test_trust_over_time_figure_is_deterministic():
    rows = [trace_row(1, d, s, 100, [(s, 5), (5, s)]) for d in ("obt", "rep-strict", "none") for s in (1, 2)]
    a, b = stats.trust_over_time_svg(rows), stats.trust_over_time_svg(rows)
    assert a == b and a.startswith(b"<?xml")


def test_report_states_seed_counts_per_row_when_defenses_have_different_seeds():
    rows = [row(n, d, s, 100 + n + s) for n in (1, 2) for d in ("none", "obt") for s in (1, 2, 3)]
    rows += [row(n, "obt", s, 100 + n + s) for n in (1, 2) for s in (4, 5)]      # extra seeds, obt only
    md = stats.report(rows)
    attack = md.split("## Attack loss per defense")[1].split("##")[0]
    assert "| obt | 5 |" in attack and "| none | 3 |" in attack
    util = md.split("## Utility cost per defense")[1].split("##")[0]
    assert "| obt | 3 |" in util                         # no `none` run for seeds 4-5, so utility stays at 3 seeds
    assert "seeds per row" in md.lower()


def test_generic_trust_panels_figure():
    rows = [trace_row(1, "obt", 1, 100, [(1, 5), (5, 1)]), trace_row(1, "obt+planner", 1, 100, [(3, 3), (6, 0)])]
    for r in rows:
        for i, t in enumerate(r["trace"]):
            t["B"] = 5.0 + i
    panels = [("OBT budget B ($)", [("E2 obt", rows, "obt", "B"), ("E2c obt+planner", rows, "obt+planner", "B")]),
              ("S_main unit share", [("E2 obt", rows, "obt", "share"), ("E2c", rows, "obt+planner", "share")])]
    a = stats.trust_panels_svg(panels, "title")
    assert a == stats.trust_panels_svg(panels, "title") and a.startswith(b"<?xml")
