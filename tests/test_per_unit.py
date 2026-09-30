"""D40: loss per 100 S_main units, a ratio of sums over attack runs (no division by a run's zero units)."""
import pytest

from eval.stats import loss_per_100_units, main_units, per_unit_runs


def run(n, seed, cost, main, back=0, d="obt"):
    acts = [["ORDER", "S_main", main, 6.0, "EXECUTED", "OK", []]] if main else []
    acts += [["ORDER", "S_backup", back, 9.0, "EXECUTED", "OK", []]] if back else []
    acts += [["ORDER", "S_main", 99, 6.0, "BLOCKED", "OVER_BUDGET", []]]      # blocked units never count
    return {"scenario": n, "seed": seed, "defense": d, "total_cost": cost, "trace": [{"actions": acts}]}


def test_units_count_only_executed_s_main_orders():
    assert main_units(run(2, 1, 0, 30, 70)) == 30


def test_ratio_of_sums_per_seed_and_per_scenario():
    rows = [run(1, 1, 100, 50), run(2, 1, 150, 20, 80), run(3, 1, 130, 0, 100),        # seed 1: loss 50 + 30
            run(1, 2, 100, 50), run(2, 2, 110, 10, 90), run(3, 2, 120, 30, 70)]        # seed 2: loss 10 + 20
    x = loss_per_100_units(rows, "obt")
    assert x["by_seed"] == {1: pytest.approx(100 * 80 / 20), 2: pytest.approx(100 * 30 / 40)}
    assert x["by_scenario"] == {2: pytest.approx(100 * 60 / 30), 3: pytest.approx(100 * 50 / 30)}
    assert x["units_per_run"] == pytest.approx(60 / 4)
    assert x["attack_share"] == pytest.approx(60 / 400)
    assert len(per_unit_runs(rows, "obt")) == 4


def test_a_seed_missing_an_attack_scenario_is_left_out_and_zero_units_is_na():
    rows = [run(1, 1, 100, 50), run(2, 1, 150, 0, 100), run(3, 1, 120, 0, 100), run(1, 2, 100, 50), run(2, 2, 90, 5)]
    x = loss_per_100_units(rows, "obt")
    assert x["by_seed"] == {1: None}                  # seed 2 lacks scenario 3; seed 1 bought no S_main unit
    assert x["by_scenario"][2] == pytest.approx(100 * (50 - 10) / 5)
