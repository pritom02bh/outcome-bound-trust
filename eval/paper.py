"""Publication assets from results/ only (DECISIONS D35).

    python -m eval.paper            # results/ -> paper/figures/*.pdf, paper/tables/*.tex

Reads only what `make results` exported (results/figdata/*.json, results/tables.json): nothing is simulated,
no run record is read and no model is called, so every number in the paper traces to results/. Figures are
vector PDFs in one style, sized for print (single column 3.4 in, double 7 in) with all text at least 7 pt at that
size (checked); fonts are embedded (Type 42) and metadata fixed so rebuilds are byte-identical. Tables are
booktabs LaTeX.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MIN_PT = 7.0
SINGLE, DOUBLE = 3.4, 7.0
STYLE = {"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
         "legend.fontsize": 7, "font.family": "DejaVu Sans", "pdf.fonttype": 42, "axes.linewidth": 0.6,
         "lines.linewidth": 1.1, "lines.markersize": 3.5, "legend.frameon": False, "axes.spines.top": False,
         "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02}
# One colour per defense across every figure.
COLORS = {"obt": "#1f77b4", "obt+planner": "#17becf", "rep-strict": "#ff7f0e", "rep-default": "#ffbb78",
          "rep-n18": "#d62728", "rep+planner": "#9467bd", "none": "#7f7f7f", "provenance": "#8c564b",
          "llm_selfcheck": "#2ca02c", "reputation": "#ff7f0e"}


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams.update(STYLE)
    import matplotlib.pyplot as plt
    return plt


def check_fonts(fig) -> float:
    """Smallest visible text size in the figure, in points at its print size; raises if below 7 pt."""
    from matplotlib.text import Text
    sizes = [t.get_fontsize() for t in fig.findobj(Text) if t.get_text().strip() and t.get_visible()]
    smallest = min(sizes, default=MIN_PT)
    if smallest < MIN_PT - 1e-9:
        raise ValueError(f"text at {smallest} pt is below the {MIN_PT} pt minimum")
    return smallest


def _save(fig, path: Path) -> float:
    smallest = check_fonts(fig)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf", metadata={"CreationDate": None, "ModDate": None, "Creator": None,
                                              "Producer": None})
    return smallest


def fig_pareto(fd: dict, path: Path) -> float:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(SINGLE, 2.5))
    for defense, marker in (("obt", "o"), ("reputation", "s")):
        pts = fd[defense]
        ax.scatter([p["utility_cost"] for p in pts], [p["attack_loss"] for p in pts], marker=marker, s=10,
                   color=COLORS[defense], alpha=0.35, linewidths=0)
        front = sorted((p for p in pts if p["front"]), key=lambda p: p["utility_cost"])
        ax.plot([p["utility_cost"] for p in front], [p["attack_loss"] for p in front], marker=marker,
                color=COLORS[defense], label=f"{'OBT' if defense == 'obt' else 'reputation'} front")
    ax.scatter([fd["none"]["utility_cost"]], [fd["none"]["attack_loss"]], marker="x", color=COLORS["none"],
               label="no defense")
    ax.set_yscale("symlog", linthresh=10)
    ax.set_xlabel("utility cost, honest supplier ($/run)")
    ax.set_ylabel("loss from lies ($/run)")
    ax.legend(loc="upper right")
    out = _save(fig, path)
    plt.close(fig)
    return out


def fig_trust(fd: dict, path: Path) -> float:
    plt = _plt()
    panels = (("B", "OBT budget B ($)"), ("score", "reputation score"), ("share", "S_main unit share"))
    fig, axes = plt.subplots(len(panels), 1, figsize=(DOUBLE / 2 + 0.2, 5.0), sharex=True)
    for ax, (key, label) in zip(axes, panels):
        for source in sorted(fd):
            for defense in sorted(fd[source]):
                ys = fd[source][defense].get(key)
                if ys:
                    ax.plot(range(1, len(ys) + 1), ys, color=COLORS.get(defense, "#000000"),
                            linestyle={"E1 scripted": ":", "E2 LLM": "--", "E2b trust-aware": "-."}.get(source, "-"),
                            label=f"{defense} ({source})")
        ax.set_ylabel(label)
        if ax.lines:
            ax.legend(loc="best", ncol=1)
    axes[-1].set_xlabel("round (honest supplier, mean over seeds)")
    out = _save(fig, path)
    plt.close(fig)
    return out


def fig_damage(fd: dict, path: Path) -> float:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(SINGLE, 2.5))
    top = 1.0
    for i, (label, pts) in enumerate(sorted(fd.items())):
        xs, ys = [p["sum_bound"] for p in pts], [p["damage"] for p in pts]
        top = max([top, *xs, *ys])
        emph = label.startswith("E6")
        ax.scatter(xs, ys, s=18 if emph else 8, marker="*" if emph else "o", label=label, zorder=3 if emph else 2)
    ax.plot([0, top], [0, top], color="#000000", linewidth=0.6, linestyle="--", label="damage = bound")
    ax.set_xlabel("sum of per-event bounds ($)")
    ax.set_ylabel("damage ($)")
    ax.legend(loc="upper left")
    out = _save(fig, path)
    plt.close(fig)
    return out


def fig_loss(fd: dict, path: Path) -> float:
    plt = _plt()
    scen, defs = fd["scenarios"], fd["defenses"]
    fig, ax = plt.subplots(figsize=(DOUBLE, 2.6))
    width = 0.8 / max(1, len(defs))
    for j, d in enumerate(defs):
        xs, ys, lo, hi = [], [], [], []
        for i, s in enumerate(scen):
            m = fd["mean"].get(f"{s}|{d}")
            if m is None:
                continue
            c = fd["ci"].get(f"{s}|{d}", [m, m])
            xs.append(i + (j - (len(defs) - 1) / 2) * width)
            ys.append(max(m, 0.0))
            lo.append(max(m, 0.0) - max(c[0], 0.0))
            hi.append(max(c[1], 0.0) - max(m, 0.0))
        ax.bar(xs, ys, width=width, color=COLORS.get(d, "#000000"), label=d, yerr=[lo, hi], error_kw={"lw": 0.5})
    ax.set_xticks(range(len(scen)))
    ax.set_xticklabels([s.split("_", 1)[1].replace("_", " ") for s in scen], rotation=30, ha="right")
    ax.set_yscale("symlog", linthresh=10)
    ax.set_ylabel("loss from lies ($/run)")
    ax.legend(ncol=min(len(defs), 7), loc="upper center", bbox_to_anchor=(0.5, 1.18))
    out = _save(fig, path)
    plt.close(fig)
    return out


_TEX = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
        "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def tex_escape(s: str) -> str:
    # Cells may be pre-escaped (e.g. a header "\$"); escape only characters not already escaped.
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] in "&%$#_{}":
            out.append(s[i:i + 2])
            i += 2
            continue
        out.append(_TEX.get(s[i], s[i]))
        i += 1
    return "".join(out)


def table_tex(name: str, t: dict) -> str:
    cols = t["columns"]
    L = [r"\begin{table}[t]", r"\centering", r"\small", r"\caption{" + tex_escape(t["caption"]) + "}",
         r"\label{tab:" + name + "}", r"\begin{tabular}{l" + "r" * (len(cols) - 1) + "}", r"\toprule",
         " & ".join(tex_escape(str(c)) for c in cols) + r" \\", r"\midrule"]
    L += [" & ".join(tex_escape(str(c)) for c in row) + r" \\" for row in t["rows"]]
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(L) + "\n"


def build(results: Path, out: Path) -> dict:
    fd = results / "figdata"
    load = lambda n: json.loads((fd / f"{n}.json").read_text()) if (fd / f"{n}.json").exists() else None  # noqa: E731
    sizes = []
    for name, fn, data in (("pareto", fig_pareto, load("pareto")), ("trust_over_time", fig_trust, load("trust")),
                           ("damage_vs_bound", fig_damage, load("damage_bound")),
                           ("loss_by_scenario", fig_loss, load("loss"))):
        if data:
            sizes.append(fn(data, out / "figures" / f"{name}.pdf"))
    tables = json.loads((results / "tables.json").read_text()) if (results / "tables.json").exists() else {}
    (out / "tables").mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        (out / "tables" / f"{name}.tex").write_text(table_tex(name, t))
    return {"figures": len(sizes), "tables": len(tables), "min_font_pt": min(sizes, default=MIN_PT)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="paper")
    a = ap.parse_args()
    print(json.dumps(build(Path(a.results), Path(a.out))))


if __name__ == "__main__":
    main()
