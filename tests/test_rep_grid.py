"""D33: reputation lock-out grid (n0 x theta x cap), scripted buyer; non-locking front and the D22-rule pick."""
import pytest

from eval import rep_grid
from obt.llm import CostMeter


def test_grid_is_the_user_spec():
    g = rep_grid.grid()
    assert len(g) == 27 and len({n for n, _ in g}) == 27
    assert {(s["rep_n0"], s["rep_theta"], s["rep_cap"]) for _, s in g} == {
        (n0, t, c) for n0 in (3, 8, 18) for t in (0.8, 0.85, 0.9) for c in (100.0, 200.0, 400.0)}


@pytest.mark.parametrize("n0,theta,locks", [(3, 0.8, False), (3, 0.85, True), (3, 0.9, True), (8, 0.9, False),
                                            (18, 0.9, False), (8, 0.85, False)])
def test_analytic_lock_out(n0, theta, locks):
    # After n0 completed orders and no failure the score is (n0+1)/(n0+2); below theta it locks out for good.
    assert rep_grid.locks_out(n0, theta) is locks


def test_pick_is_the_non_locking_front_point_nearest_the_reference():
    pts = {"a": {"utility_cost": 0.0, "attack_loss": 700.0, "locked": False},
           "b": {"utility_cost": 300.0, "attack_loss": 100.0, "locked": False},
           "c": {"utility_cost": 340.0, "attack_loss": 150.0, "locked": False},        # dominated by b
           "d": {"utility_cost": 494.0, "attack_loss": 0.0, "locked": True},           # locks: excluded
           "e": {"utility_cost": 420.0, "attack_loss": 50.0, "locked": False}}
    front, pick = rep_grid.choose(pts, reference_utility=344.2)
    assert front == ["a", "b", "e"] and pick == "b"


def test_never_trading_points_are_degenerate_and_excluded_like_lock_out():
    # D33: correcting the D22 rule's intent, not an outcome-based choice.
    pts = {"trades": {"utility_cost": 0.0, "attack_loss": 702.0, "locked": False, "never_trades": False},
           "trades2": {"utility_cost": 0.0, "attack_loss": 900.0, "locked": False, "never_trades": False},
           "never": {"utility_cost": 494.2, "attack_loss": 0.0, "locked": False, "never_trades": True}}
    front, pick = rep_grid.choose(pts, reference_utility=344.2)
    assert front == ["trades"] and pick == "trades"


def test_summary_marks_empirical_lock_out(tmp_path, rule_llm):
    root = tmp_path / "rg"
    kw = dict(backend="fake", model="fake", scenarios=(1, 2), seeds=(1,), rounds=30)
    from eval import e1
    e1.run_point(root, "none", "none", {}, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm, **kw)
    for name, sim in (("rep_n3_th0.9_cap200", {"rep_n0": 3, "rep_theta": 0.9, "rep_cap": 200.0}),
                      ("rep_n8_th0.9_cap200", {"rep_n0": 8, "rep_theta": 0.9, "rep_cap": 200.0})):
        e1.run_point(root, name, "reputation", sim, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm, **kw)
    s = rep_grid.summarize(root, none_dir=root / "none", reference_utility=344.2)
    assert s["points"]["rep_n3_th0.9_cap200"]["locked"] and not s["points"]["rep_n8_th0.9_cap200"]["locked"]
    assert s["points"]["rep_n3_th0.9_cap200"]["analytic_lock"] is True
