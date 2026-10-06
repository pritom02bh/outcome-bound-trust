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


# Okabe-Ito (colorblind-safe), used with distinct line styles so the walkthrough also reads in grayscale.
OI = {"blue": "#0072B2", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "vermillion": "#D55E00",
      "black": "#000000", "gray": "#999999"}


def fig_walkthrough(w: dict, path: Path) -> float:
    """Top: the OBT run, B(c) and P(c) as steps, S_main order qty as bars (approved vs blocked or clipped), claim
    outcomes at their resolution rounds. Bottom: cumulative loss from lies per defense and OBT's per-event bound."""
    plt = _plt()
    fig, (top, bot) = plt.subplots(2, 1, figsize=(SINGLE, 4.4), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.12})
    o = w["defenses"]["obt"]["rounds"]
    t = [r["round"] for r in o]
    qa = [sum(x["qty"] for x in r["orders"] if x["supplier"] != "S_backup" and x["status"] == "EXECUTED") for r in o]
    qb = [sum(x["qty"] for x in r["orders"] if x["supplier"] != "S_backup" and x["status"] != "EXECUTED") for r in o]
    bars = top.twinx()
    bars.bar(t, qa, width=0.8, color=OI["sky"], label="order qty, approved", zorder=1)
    from matplotlib.patches import Patch
    nb = [(x, y, z) for x, y, z in zip(t, qb, qa) if y]
    bars.bar([x for x, _, _ in nb], [y for _, y, _ in nb], bottom=[z for _, _, z in nb], width=0.8, color="white",
             edgecolor=OI["vermillion"], hatch="////", linewidth=0.5, zorder=1)
    blocked = Patch(facecolor="white", edgecolor=OI["vermillion"], hatch="////", linewidth=0.5,
                    label=f"order qty, blocked/clipped ({len(nb)} in this run)")
    bars.set_ylim(0, 6)
    bars.set_yticks([0, 1, 2])
    bars.set_ylabel("S_main order (units)")
    bars.spines["right"].set_visible(True)
    top.set_zorder(bars.get_zorder() + 1)
    top.patch.set_visible(False)
    top.step(t, [r["B"] for r in o], where="post", color=OI["blue"], label="budget B(c)")
    top.step(t, [r["P"] for r in o], where="post", color=OI["black"], linestyle=":", label="exposure P(c)")
    ymax = 16.0
    ok = [r["round"] for r in o for c in r["resolved"] if c["status"] == "PASSED" and c["id"].endswith(".1")]
    bad = [r["round"] for r in o for c in r["resolved"] if c["status"] == "FAILED" and c["id"].endswith(".1")]
    top.scatter(ok, [ymax - 1.6] * len(ok), marker=r"$\checkmark$", s=16, color=OI["green"], linewidths=0,
                label="delivery claim passed")
    top.scatter(bad, [ymax - 1.6] * len(bad), marker="X", s=22, color=OI["vermillion"], linewidths=0,
                label="delivery claim failed")
    top.set_ylim(0, ymax)
    top.set_ylabel("$ (B, P)")
    lie = next(e for e in w["key_events"] if e["event"].startswith("The lie"))
    top.annotate("lie", (lie["round"], 10.0), xytext=(lie["round"] - 9, 12.2), fontsize=7,
                 arrowprops={"arrowstyle": "->", "linewidth": 0.6})
    h1, l1 = top.get_legend_handles_labels()
    h2, l2 = bars.get_legend_handles_labels()
    h2, l2 = h2 + [blocked], l2 + [blocked.get_label()]
    top.legend(h1 + h2, l1 + l2, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=7,
               handlelength=1.4, columnspacing=0.8, borderaxespad=0.1)
    styles = {"none": (OI["black"], "-."), "rep-default": (OI["orange"], "--"), "obt": (OI["blue"], "-")}
    for d, (c, ls) in styles.items():
        rr = w["defenses"][d]["rounds"]
        bot.step([r["round"] for r in rr], [r["loss"] for r in rr], where="post", color=c, linestyle=ls,
                 label=f"{'OBT' if d == 'obt' else d}")
    ev = w["defenses"]["obt"]["events"]
    bound = [sum(e["bound"] for e in ev if e["resolved_round"] <= x) for x in t]
    bot.step(t, bound, where="post", color=OI["vermillion"], linestyle=(0, (4, 2)), linewidth=0.9,
             label="OBT loss bound $\\Sigma L_e$")
    bot.axhline(0, color=OI["gray"], linewidth=0.4)
    bot.set_yscale("symlog", linthresh=10)
    bot.set_ylabel("cumulative loss from lies ($)")
    bot.set_xlabel("round")
    bot.set_xlim(0.5, t[-1] + 0.5)
    bot.legend(loc="upper left", fontsize=7, handlelength=1.8)
    out = _save(fig, path)
    fig.savefig(path.with_suffix(".png"), format="png", dpi=300, metadata={"Software": None})
    plt.close(fig)
    return out


def walkthrough_md(w: dict) -> str:
    d = w["defenses"]
    L = ["# Walkthrough: one farm-then-lie run, round by round", "",
         f"E2, scenario 3 (farm-then-lie), seed {w['seed']}, gpt-oss:20b buyer and extractor, A2A; defenses `obt`, "
         f"`none` and `rep-default`, each against its honest run (scenario 1, same defense and seed). Read from "
         f"existing logs only (`{w['log']}`, commit `{d['obt']['git_commit']}`); no new runs (D46). Figure: "
         "`paper/figures/walkthrough.pdf` (and `.png`). Per-round extract: `results/walkthrough/rounds.csv`; data: "
         "`results/figdata/walkthrough.json`.", "",
         "Run records: " + "; ".join(f"`{k}` attack line {x['line']}, honest line {x['honest_line']}"
                                     for k, x in d.items()) + ".", "",
         "## Key events (OBT run unless stated)", "", "| round | event | what the log shows | source (file:line → field) |",
         "|---|---|---|---|"]
    L += [f"| {e['round']} | {e['event']} | {e['what']} | {e['source']} |" for e in w["key_events"]]
    L += ["", "## Notes", "",
          "- **The gate never had to block.** The OBT buyer sized every S_main order inside the headroom B − P "
          f"(largest order 1 unit; {d['obt']['main_orders_blocked']} blocked orders; {d['obt']['rerouted_units']} "
          "units rerouted after a block). The only backup order caused by a failure is the remediation of the "
          f"shortfall ({d['obt']['shortfall_rerouted_units']} unit). What limits the lie is the budget: with B = $10 the buyer can "
          "commit at most $10 to S_main, so the defection costs it one prepaid unit, while `none` and `rep-default` "
          "order 21 units on the same message.",
          "- **Loss from lies** per round is the cumulative cost of the run minus the cumulative cost of its honest run "
          "(same defense and seed); it ends at the run's loss from lies. Before the lie the three pairs are identical "
          "(0.0 in every round), so the curves isolate the lie's effect; afterwards they also include trajectory "
          "differences of the LLM buyer (e.g. the dip below 0 in rounds 26-29).",
          "- **The bound applies to damage** (DESIGN §6), not to the loss from lies: OBT's damage is "
          f"${d['obt']['damage']:.2f} against Σ L_e = ${d['obt']['sum_bound']:.2f}; its loss from lies is "
          f"${d['obt']['loss_from_lies']:.2f}. The figure draws Σ L_e from the round its event resolves.",
          "- Claim ids are `S_main#<round>.<n>`: `.1` is the round's DELIVERY claim and `.2` its PRICE claim. Each "
          "round's claims resolve two rounds later (PASSED, FAILED, or LAPSED when no order relied on them).", ""]
    return "\n".join(L)


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
                           ("loss_by_scenario", fig_loss, load("loss")), ("e9_pareto", fig_pareto, load("e9_pareto")),
                           ("e9_pareto_ext", fig_pareto, load("e9_pareto_ext"))):
        if data:
            sizes.append(fn(data, out / "figures" / f"{name}.pdf"))
    w = load("walkthrough")
    if w:
        sizes.append(fig_walkthrough(w, out / "figures" / "walkthrough.pdf"))
        (out / "walkthrough.md").write_text(walkthrough_md(w))
    tables = json.loads((results / "tables.json").read_text()) if (results / "tables.json").exists() else {}
    (out / "tables").mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        (out / "tables" / f"{name}.tex").write_text(table_tex(name, t))
    numbers = None
    from eval import numbers as nb
    if set(nb.REQUIRED) <= set(tables) and (results / "figdata" / "pareto.json").exists():
        numbers = nb.write(results, out, results.parent / "spec" / "results").name
    return {"figures": len(sizes), "tables": len(tables), "min_font_pt": min(sizes, default=MIN_PT),
            "numbers": numbers}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default="paper")
    a = ap.parse_args()
    print(json.dumps(build(Path(a.results), Path(a.out))))


if __name__ == "__main__":
    main()
