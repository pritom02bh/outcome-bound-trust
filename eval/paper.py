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
    """Top: the OBT run, B(c) and P(c) as steps, S_main order qty as bars (approved vs blocked), claim outcomes at
    their resolution rounds, lie rounds shaded. Bottom: cumulative loss from lies per defense and OBT's Σ L_e."""
    from matplotlib.patches import Patch
    plt = _plt()
    fig, (top, bot) = plt.subplots(2, 1, figsize=(SINGLE, 4.9), sharex=True,
                                   gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.12})
    o = w["defenses"]["obt"]["rounds"]
    t = [r["round"] for r in o]
    main = lambda r, ok: sum(x["qty"] for x in r["orders"]  # noqa: E731
                             if x["supplier"] != "S_backup" and (x["status"] == "EXECUTED") == ok)
    qa, qb = [main(r, True) for r in o], [main(r, False) for r in o]
    lies = [r["round"] for r in o if r["intent"] and r["intent"].get("truth") is False]
    for ax in (top, bot):
        ax.axvspan(min(lies) - 0.5, max(lies) + 0.5, color=OI["gray"], alpha=0.18, linewidth=0, zorder=0)
    bars = top.twinx()
    bars.bar(t, qa, width=0.8, color=OI["sky"], label="order qty, approved", zorder=1)
    nb = [(x, y, z) for x, y, z in zip(t, qb, qa) if y]
    bars.bar([x for x, _, _ in nb], [y for _, y, _ in nb], bottom=[z for _, _, z in nb], width=0.8, color="white",
             edgecolor=OI["vermillion"], hatch="////", linewidth=0.5, zorder=1)
    blocked = Patch(facecolor="white", edgecolor=OI["vermillion"], hatch="////", linewidth=0.5,
                    label=f"order qty, blocked ({len(nb)} in this run)")
    qmax = max([1, *(a + b for a, b in zip(qa, qb))])
    bars.set_ylim(0, qmax * 3)
    bars.set_yticks([0, qmax])
    bars.set_ylabel("S_main order (units)")
    bars.spines["right"].set_visible(True)
    top.set_zorder(bars.get_zorder() + 1)
    top.patch.set_visible(False)
    top.step(t, [r["B"] for r in o], where="post", color=OI["blue"], label="budget B(c)")
    top.step(t, [r["P"] for r in o], where="post", color=OI["black"], linestyle=":", label="exposure P(c)")
    ymax = 1.35 * max(max(r["B"] or 0 for r in o), max(r["P"] or 0 for r in o))
    ok = [r["round"] for r in o for c in r["resolved"] if c["status"] == "PASSED" and c["id"].endswith(".1")]
    bad = [r["round"] for r in o for c in r["resolved"] if c["status"] == "FAILED" and c["id"].endswith(".1")]
    top.scatter(ok, [ymax * 0.9] * len(ok), marker=r"$\checkmark$", s=16, color=OI["green"], linewidths=0,
                label="delivery claim passed")
    top.scatter(bad, [ymax * 0.9] * len(bad), marker="X", s=22, color=OI["vermillion"], linewidths=0,
                label=f"delivery claim failed ({len(bad)})")
    top.set_ylim(0, ymax)
    top.set_ylabel("$ (B, P)")
    h1, l1 = top.get_legend_handles_labels()
    h2, l2 = bars.get_legend_handles_labels()
    shade = Patch(facecolor=OI["gray"], alpha=0.18, label="lie rounds")
    top.legend(h1 + h2 + [blocked, shade], l1 + l2 + [blocked.get_label(), "lie rounds"], loc="lower center",
               bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=7, handlelength=1.4, columnspacing=0.8, borderaxespad=0.1)
    same = w["defenses"]["none"]["rounds"] == w["defenses"]["rep-default"]["rounds"]
    styles = {"none": (OI["black"], "-.", 1.1), "rep-default": (OI["orange"], (0, (2, 3)) if same else "--",
                                                               1.6 if same else 1.1),
              "obt": (OI["blue"], "-", 1.1)}
    for d, (c, ls, lw) in styles.items():
        rr = w["defenses"][d]["rounds"]
        bot.step([r["round"] for r in rr], [r["loss"] for r in rr], where="post", color=c, linestyle=ls, linewidth=lw,
                 label=("OBT" if d == "obt" else d) + (" (= none here)" if d == "rep-default" and same else ""))
    ev = w["defenses"]["obt"]["events"]
    bound = [sum(e["bound"] for e in ev if e["resolved_round"] <= x) for x in t]
    bot.step(t, bound, where="post", color=OI["vermillion"], linestyle=(0, (4, 2)), linewidth=0.9,
             label="OBT loss bound $\\Sigma L_e$")
    bot.axhline(0, color=OI["gray"], linewidth=0.4)
    bot.set_yscale("symlog", linthresh=10)
    bot.set_ylabel("cumulative loss from lies ($)")
    bot.set_xlabel("round")
    bot.set_xlim(0.5, t[-1] + 0.5)
    bot.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=2, fontsize=7, handlelength=1.8,
               columnspacing=0.8)
    out = _save(fig, path)
    fig.savefig(path.with_suffix(".png"), format="png", dpi=300, metadata={"Software": None})
    plt.close(fig)
    return out


def walkthrough_md(w: dict, stem: str = "walkthrough") -> str:
    d, o = w["defenses"], w["defenses"]["obt"]
    blocked = sum(1 for r in o["rounds"] for x in r["orders"] if x["supplier"] != "S_backup" and x["status"] != "EXECUTED")
    largest = max((x["qty"] for r in o["rounds"] for x in r["orders"] if x["supplier"] != "S_backup"), default=0)
    same = d["none"]["rounds"] == d["rep-default"]["rounds"]
    appendix = stem.endswith("_appendix")
    L = [f"# Walkthrough{' (appendix)' if appendix else ''}: one farm-then-lie run, round by round", "",
         f"{w['run']}; scenario 3 (farm-then-lie), seed {w['seed']}; defenses `obt`, `none` and `rep-default`, each "
         "against its honest run (scenario 1, same defense, config and seed). Read from existing logs only; no new "
         f"runs ({'D46' if appendix else 'D46a'}). Figure: `paper/figures/{stem}.pdf` (and `.png`). Per-round extract: "
         f"`results/walkthrough/rounds{stem[len('walkthrough'):]}.csv`; data: `results/figdata/{stem}.json`.", "",
         "Run records: " + "; ".join(f"`{k}` `{x['log']}` attack line {x['line']}, honest line {x['honest_line']} "
                                     f"(commit `{x['git_commit']}`)" for k, x in d.items()) + ".", ""]
    if "search" in w:
        L += ["**Why this run (D46a).** Every OBT farm-then-lie log was searched for a run where the gate blocked an "
              "S_main order in a lie round. LLM-buyer experiments came first:", "",
              "| experiment | OBT farm-then-lie runs | with a blocked order on the lie |", "|---|---|---|"]
        L += [f"| {k} | {v['runs']} | {v['blocked_on_lie']} |" for k, v in sorted(w["search"].items())]
        L += ["", "No LLM-buyer run qualifies: those buyers sized their S_main orders inside the headroom, so the gate "
              "never had to block on the lie (D46's E2 run is kept as `walkthrough_appendix`). The run shown is E1's "
              "scripted buyer at the chosen default config, seed 1, the fallback the request named.", ""]
    L += ["## Key events (OBT run unless stated)", "", "| round | event | what the log shows | source (file:line → field) |",
          "|---|---|---|---|"]
    L += [f"| {e['round']} | {e['event']} | {e['what']} | {e['source']} |" for e in w["key_events"]]
    L += ["", "## Notes", ""]
    if blocked:
        L.append(f"- **The gate blocks, it does not clip.** An order either passes the gate table or is blocked whole "
                 f"(here OVER_BUDGET: its value exceeds B − P); the blocked quantity is then rerouted to S_backup by "
                 f"code. {blocked} S_main orders are blocked in this run ({o['rerouted_units']} units rerouted; the "
                 "trace logs the reroute count per round and the quantity is the blocked order's, which sums to "
                 "`metrics.rerouted_units`).")
    else:
        L.append(f"- **The gate never had to block.** The OBT buyer sized every S_main order inside the headroom B − P "
                 f"(largest order {largest} unit{'s' if largest != 1 else ''}; 0 blocked orders). What limits the lie "
                 "is the budget: the buyer cannot commit more than B to S_main.")
    if same:
        L.append("- **`rep-default` equals `none` in this run.** Reputation never blocked an order, so the two runs are "
                 "identical round by round; the figure draws both (rep-default dotted over none).")
    # A one-round phase shift between the attack and honest runs makes the per-round difference alternate.
    lr = [r["loss"] for r in o["rounds"]]
    lie_end = max(r["round"] for r in o["rounds"] if r["intent"] and r["intent"].get("truth") is False)
    after = lr[lie_end:]
    swings = sum(1 for x, y in zip(after, after[1:]) if (y - x) * (x - (after[0] if after else 0)) < 0)
    if len(after) > 4 and max(after) - min(after) > 10 and swings > len(after) // 3:
        L.append(f"- **Why OBT's loss curve alternates after round {lie_end}.** After the lie, OBT's buyer orders from "
                 "S_main on the opposite rounds to its honest run (one round out of phase), and a purchase is charged "
                 "when it is paid, so the cumulative difference swings between rounds. That is payment timing, not "
                 f"loss: the run ends at ${o['loss_from_lies']:.2f} (`rounds.csv` has every round).")
    L += ["- **Loss from lies** per round is the cumulative cost of the run minus the cumulative cost of its honest run "
          "(same defense and seed); it ends at the run's loss from lies. It includes reroute premiums and trajectory "
          "differences after the lie, not only damage.",
          f"- **The bound applies to damage** (DESIGN §6), not to the loss from lies: OBT's damage is ${o['damage']:.2f} "
          f"against Σ L_e = ${o['sum_bound']:.2f}; its loss from lies is ${o['loss_from_lies']:.2f}. The figure draws "
          "Σ L_e from the round its failure event resolves.",
          "- Claim ids are `S_main#<round>.<n>`: `.1` is the round's DELIVERY claim and `.2` its PRICE claim; each "
          "resolves at its deadline (PASSED, FAILED, or LAPSED when no executed order relied on it).", ""]
    return "\n".join(L)


def fig_round_loop(path: Path) -> float:
    """One simulation round, in order, with what is an LLM and what is code (D46a). Static: it draws the sim's order
    of play (obt/sim.py), not data. The sim starts a round with steps 6-8 (env, verify, budget) and then 1-5; drawn
    as a loop, that is the same cycle starting at the message."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
    plt = _plt()
    fig, ax = plt.subplots(figsize=(SINGLE, 4.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 15.0)
    ax.axis("off")
    LLM = {"facecolor": "#FBE3B5", "edgecolor": OI["orange"], "linestyle": "--", "linewidth": 0.9}
    CODE = {"facecolor": "#D5EAF7", "edgecolor": OI["blue"], "linestyle": "-", "linewidth": 0.9}
    ENV = {"facecolor": "#CDEBE0", "edgecolor": OI["green"], "linestyle": "-", "linewidth": 0.9}
    ACTOR = {"facecolor": "white", "edgecolor": OI["black"], "linestyle": "-", "linewidth": 0.7}

    def box(x, y, w, h, text, style, ha="left"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", **style))
        ax.text(x + (0.15 if ha == "left" else w / 2), y + h / 2, text, ha=ha, va="center", fontsize=7,
                linespacing=1.05)

    def arrow(a, b, ls="-", color=OI["black"], rad=0.0, style="-|>"):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=7, linewidth=0.7, linestyle=ls,
                                     color=color, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0))

    X, W, H, G = 0.75, 6.3, 1.02, 0.36
    steps = [("1  Supplier sends a message\n     (LLM-written text)", LLM),
             ("2  Extractor turns it into typed\n     claims (or UNTESTABLE)", LLM),
             ("3  Claim ledger records them\n     (append-only, PENDING)", CODE),
             ("4  Buyer proposes an order\n     citing a claim", LLM),
             ("5  Gate approves, or blocks\n     an order over B − P", CODE),
             ("6  Deliveries and invoices\n     are recorded", ENV),
             ("7  Verifier resolves due claims\n     (PASSED/FAILED/LAPSED)", CODE),
             ("8  Trust budget B(c) is updated", CODE)]
    top = 14.0
    ys = [top - i * (H + G) for i in range(len(steps))]
    for y, (text, style) in zip(ys, steps):
        box(X, y - H, W, H, text, style)
    for y1, y2 in zip(ys, ys[1:]):
        arrow((X + W / 2, y1 - H), (X + W / 2, y2))
    # Next round: from step 8 back up to step 1, in the left margin.
    arrow((X, ys[-1] - H / 2), (X, ys[0] - H / 2), ls=":", rad=-0.18)
    ax.text(0.05, (ys[0] + ys[-1] - H) / 2, "next round", rotation=90, fontsize=7, ha="center", va="center")
    # Actors beside the step they act in.
    AX, AW = 7.75, 2.1
    box(AX, ys[0] - H, AW, H, "S_main", ACTOR, ha="center")
    arrow((AX, ys[0] - H / 2), (X + W, ys[0] - H / 2))
    box(AX, ys[3] - H, AW, H, "Buyer\nagent", LLM, ha="center")
    arrow((AX, ys[3] - H / 2), (X + W, ys[3] - H / 2))
    box(AX, ys[4] - H, AW, H, "S_backup", ACTOR, ha="center")
    ax.texts[-1].set_fontsize(7)
    arrow((X + W, ys[4] - H / 2), (AX, ys[4] - H / 2), ls="--", color=OI["vermillion"])
    ax.text((X + W + AX) / 2, ys[4] - 0.05, "reroute", fontsize=7, color=OI["vermillion"], ha="center",
            va="bottom")
    box(AX, ys[6] - H, AW, ys[5] - ys[6] + H, "Environment\nrecords", ENV, ha="center")
    arrow((X + W, ys[5] - H / 2), (AX, ys[5] - H / 2))
    arrow((AX, ys[6] - H / 2), (X + W, ys[6] - H / 2), ls="--")
    # Notes.
    ax.text(0.1, ys[-1] - H - 0.35,
            "Step 1 message source: E1-E7 and horizon, frozen message\n"
            "bank (qwen3:8b-written templates, sha256-pinned); E8, LLM\n"
            "attacker (gpt-oss:20b); E9, structured intents (no text).\n"
            "Step 2 is code in E6, E7 (rule extractor) and E9 (parser).\n"
            "Step 4 is a scripted buyer (code) in E1, E6, E7 and E9.\n"
            "The buyer sees claim cards, never raw supplier text.",
            fontsize=7, va="top", ha="left", linespacing=1.15)
    ax.legend(handles=[Patch(**LLM, label="LLM"), Patch(**CODE, label="code"),
                       Patch(**ENV, label="environment (code)")], loc="lower center", bbox_to_anchor=(0.5, 0.955),
              ncol=3, fontsize=7, handlelength=1.6, columnspacing=1.0)
    out = _save(fig, path)
    fig.savefig(path.with_suffix(".png"), format="png", dpi=300, metadata={"Software": None})
    plt.close(fig)
    return out


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


# Text-heavy tables: full width, wrapped columns (env, size, column spec). Every other table keeps l + r columns.
LAYOUT = {"sim_glance": ("table*", r"\footnotesize",
                         r"p{0.07\linewidth}p{0.16\linewidth}p{0.47\linewidth}p{0.24\linewidth}")}


def table_tex(name: str, t: dict) -> str:
    cols = t["columns"]
    env, size, spec = LAYOUT.get(name, ("table", r"\small", "l" + "r" * (len(cols) - 1)))
    L = [r"\begin{" + env + "}[t]", r"\centering", size, r"\caption{" + tex_escape(t["caption"]) + "}",
         r"\label{tab:" + name + "}", r"\begin{tabular}{" + spec + "}", r"\toprule",
         " & ".join(tex_escape(str(c)) for c in cols) + r" \\", r"\midrule"]
    L += [" & ".join(tex_escape(str(c)) for c in row) + r" \\" for row in t["rows"]]
    L += [r"\bottomrule", r"\end{tabular}", r"\end{" + env + "}"]
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
    sizes.append(fig_round_loop(out / "figures" / "round_loop.pdf"))
    for stem in ("walkthrough", "walkthrough_appendix"):
        w = load(stem)
        if w:
            sizes.append(fig_walkthrough(w, out / "figures" / f"{stem}.pdf"))
            (out / f"{stem}.md").write_text(walkthrough_md(w, stem))
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
