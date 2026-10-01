"""E9 calibration (DECISIONS D45): the grid, E1's selection rule with D33's exclusion, and the harness check that the
transferred configs' grid points reproduce E9's own runs."""
from eval import e9, e9_calib


def test_grid_is_the_requested_one():
    g = e9_calib.grid()
    obt = [s for _, d, s in g if d == "obt"]
    rep = [s for _, d, s in g if d == "reputation"]
    assert len(obt) == 8 and {(s["b0_frac"], s["budget_k"]) for s in obt} == \
        {(b, k) for b in (0.025, 0.05, 0.10, 0.20) for k in (1, 2)}
    assert len(rep) == 27 and all(s["window"] == 0 and s["grace"] == 0 for _, _, s in g)
    names = {n for n, _, _ in g}
    assert set(e9_calib.TRANSFERRED.values()) <= names


def test_choose_is_e1s_rule_without_never_trading_points():
    p = lambda d, u, l, nt=False: {"defense": d, "utility_cost": u, "attack_loss": l, "never_trades": nt}  # noqa: E731
    pts = {"a": p("obt", 0, 500), "b": p("obt", 100, 50), "c": p("obt", 120, 60), "z": p("obt", 0, 0, nt=True),
           "r": p("reputation", 0, 10)}
    front, pick = e9_calib.choose(pts, "obt")
    assert front == ["a", "b"] and pick == "b"                    # c dominated; z degenerate; r another defense
    assert e9_calib.choose(pts, "reputation") == (["r"], "r")


def test_transferred_points_reproduce_e9_runs(tmp_path):
    e9.run(tmp_path / "e9", scenarios=(1, 2), defenses=("none", "obt", "rep-strict"), seeds=(1,), rounds=20)
    pts = [x for x in e9_calib.grid() if x[0] in e9_calib.TRANSFERRED.values()]
    e9_calib.run(tmp_path / "cal", points=pts, scenarios=(1, 2), seeds=(1,), rounds=20)
    s = e9_calib.summarize(tmp_path / "cal", tmp_path / "e9")
    assert s["reproduces_e9"] == {"obt": True, "rep-strict": True}
    assert set(s["points"]) == set(e9_calib.TRANSFERRED.values())
    assert s["points"]["obt_b0.05_k1"]["bound_held"]
    rows = e9_calib.calibrated_rows(tmp_path / "cal", tmp_path / "e9")
    assert {r["defense"] for r in rows} == {"none", "obt", "rep-strict"}


def test_extended_grid_adds_only_obt_points():
    base, ext = e9_calib.grid(), e9_calib.grid(ext=True)
    new = [x for x in ext if x not in base]
    assert {x[0] for x in base} <= {x[0] for x in ext} and all(d == "obt" for _, d, _ in new)
    assert {(s["b0_frac"], s["budget_k"]) for _, _, s in new} == \
        {(b, k) for b in (0.40, 0.80) for k in (1, 2, 4)} | {(b, 4) for b in (0.025, 0.05, 0.10, 0.20)}
    assert len([x for x in ext if x[1] == "obt"]) == 18
