"""Paper assets (D35): figure data and tables exported by `make results`, and figures/tables built from results/ only."""
import json

import pytest

from eval import paper


def _results(tmp_path):
    r = tmp_path / "results"
    fd = r / "figdata"
    fd.mkdir(parents=True)
    series = {"E2 LLM": {"obt": {"B": [5, 10, 10], "share": [0.1, 0.1, 0.1]}},
              "E1 scripted": {"obt": {"B": [5, 15, 25], "share": [0.1, 0.3, 0.4]},
                              "rep-strict": {"score": [0.5, 0.7, 0.8], "share": [0.3, 0.2, 0.0]}}}
    (fd / "trust.json").write_text(json.dumps(series))
    (fd / "pareto.json").write_text(json.dumps({
        "obt": [{"name": "obt_a", "utility_cost": 300, "attack_loss": 150, "front": True}],
        "reputation": [{"name": "rep_a", "utility_cost": 0, "attack_loss": 700, "front": True, "never_trades": False},
                       {"name": "rep_b", "utility_cost": 494, "attack_loss": 0, "front": False, "never_trades": True}],
        "none": {"utility_cost": 0, "attack_loss": 5500}, "chosen": {"obt": "obt_a", "reputation": "rep_a"}}))
    (fd / "damage_bound.json").write_text(json.dumps({
        "E2 obt": [{"damage": 10, "sum_bound": 30, "events": 3}], "E6 max ratio": [{"damage": 12, "sum_bound": 14,
                                                                                    "events": 1}]}))
    (fd / "loss.json").write_text(json.dumps({"defenses": ["obt", "none"], "scenarios": ["2_always_lie"],
                                              "mean": {"2_always_lie|obt": 100, "2_always_lie|none": 7000},
                                              "ci": {"2_always_lie|obt": [90, 110], "2_always_lie|none": [6800, 7200]}}))
    (r / "tables.json").write_text(json.dumps({
        "main": {"caption": "Main results", "columns": ["defense", "loss (\\$)", "utility (%)"],
                 "rows": [["obt", "43.1 [32.8, 56.3]", "4.97"], ["rep_n18 & co", "702", "0.0"]]}}))
    return r


def test_builds_every_figure_and_table_from_results_only(tmp_path):
    out = tmp_path / "paper"
    built = paper.build(_results(tmp_path), out)
    for name in ("pareto", "trust_over_time", "damage_vs_bound", "loss_by_scenario"):
        pdf = out / "figures" / f"{name}.pdf"
        assert pdf.exists() and pdf.read_bytes().startswith(b"%PDF")
    tex = (out / "tables" / "main.tex").read_text()
    assert "\\toprule" in tex and "\\midrule" in tex and "\\bottomrule" in tex
    assert "rep\\_n18 \\& co" in tex                                  # LaTeX special characters escaped
    assert built["min_font_pt"] >= 7


def test_is_deterministic(tmp_path):
    r = _results(tmp_path)
    paper.build(r, tmp_path / "a")
    paper.build(r, tmp_path / "b")
    for sub in ("figures", "tables"):
        for f in (tmp_path / "a" / sub).iterdir():
            assert f.read_bytes() == (tmp_path / "b" / sub / f.name).read_bytes(), f.name


def test_refuses_text_below_7pt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.text(0, 0, "tiny", fontsize=5)
    with pytest.raises(ValueError, match="7"):
        paper.check_fonts(fig)
    plt.close(fig)
