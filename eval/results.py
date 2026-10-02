"""Rebuild every table and figure from runs/ only (FIXES F12).

    make results            # = python -m eval.results --runs runs --out results

Reads the run records each eval wrote (`results.jsonl`, `extractor.json`) and the frozen-bank reports under
`runs/message_bank/` and `runs/tuning/`. Nothing is simulated and no model is called, so the tables can be
regenerated at any time and always match the runs they came from. Output is deterministic: same runs, same
bytes (SVG figures carry no date and a fixed hash salt).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import defaultdict
from pathlib import Path

from eval.run import markdown, summarize
from eval.stats import (e2b_report, e2b_trust_svg, loss_split, main_share, report, trust_over_time_svg,
                        trust_panels_svg)
from obt.attacks.suppliers import scenario_name

# e1 grid points are summarized together as one grid (_e1), not as separate evals.
SKIP = ("_invalid", "_archive", "_v1_shared_cache", "e8", "e9", "e9_calib", "cache", "message_bank", "tuning", "e1", "e4", "e6", "rep_grid")


def _read_rows(f: Path) -> list[dict]:
    # Read-only: a torn last line is skipped here, never rewritten (eval.run.load_results does that).
    out = []
    for line in f.read_text().splitlines():
        try:
            r = json.loads(line)
            if "meta" in r:
                out.append(r)
        except json.JSONDecodeError:
            continue
    return out


def _evals(runs: Path) -> dict[str, tuple[list[dict], dict]]:
    """name -> (run records of one config, extractor report). An eval dir holding several configs (a resumed
    dir whose config changed) is split by config hash."""
    found = {}
    for f in sorted(runs.rglob("results.jsonl")):
        rel = f.parent.relative_to(runs)
        if any(part.startswith(SKIP) for part in rel.parts):
            continue
        rows = _read_rows(f)
        groups = defaultdict(list)
        for r in rows:
            # One eval = one shared config; named variants inside it keep their own run identity (D27).
            groups[r["meta"].get("eval_config_hash", r["meta"]["config_hash"])].append(r)
        ext = {}
        ef = f.parent / "extractor.json"
        if ef.exists():
            ext = json.loads(ef.read_text()).get("extractor", {})
        name = "__".join(rel.parts)
        for h, rs in sorted(groups.items()):
            found[name if len(groups) == 1 else f"{name}__{h[:8]}"] = (rs, ext)
    return found


def _csv(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def _svg(fig) -> bytes:
    import matplotlib
    matplotlib.rcParams["svg.hashsalt"] = "obt"
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": None})
    return buf.getvalue()


def _attack_loss(summary: dict, d: str) -> float | None:
    vals = [summary["loss_from_lies"].get(f"{n}|{d}") for n in summary["scenarios"] if n != 1]
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _loss_vs_utility(points: list[tuple[str, float, float]], title: str) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for label, x, y in points:
        ax.scatter([x], [y])
        ax.annotate(label, (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("utility cost: extra cost vs no defense, honest S_main ($)")
    ax.set_ylabel("mean loss from lies, attack scenarios ($)")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    out = _svg(fig)
    plt.close(fig)
    return out


def _extractor_md(ext: dict) -> str:
    L = ["## Extractor accuracy", "", "| extractor | split | n | precision | recall | exact | honest→UNTESTABLE |",
         "|---|---|---|---|---|---|---|"]
    for name, e in sorted(ext.items()):
        L.append(f"| {name} | {e.get('split')} | {e.get('n_messages')} | {e.get('precision')} | {e.get('recall')} | "
                 f"{e.get('exact_match')} | {e.get('honest_untestable_rate')} |")
    hard = {k: e["hard"] for k, e in sorted(ext.items()) if "hard" in e}
    if hard:
        L += ["", "## Hard-phrasing subset (shipping/ready/scheduled dates recorded as delivery deadlines)", "",
              "| extractor | recorded | ship | ready | scheduled | PRICE recovered |", "|---|---|---|---|---|---|"]
        for k, h in hard.items():
            g = h["by_group"]
            L.append(f"| {k} | {h['delivery_recorded']}/{h['n']} | " + " | ".join(
                f"{g[x]['delivery_recorded']}/{g[x]['n']}" if x in g else "-" for x in ("ship", "ready", "scheduled"))
                + f" | {h['price_recovery']} |")
    inj = {k: e["injection"] for k, e in sorted(ext.items()) if e.get("injection", {}).get("n")}
    if inj:
        L += ["", "## Scenario-11 injections", "", "| extractor | injected recorded | accuracy vs F5 gold | n |",
              "|---|---|---|---|"]
        for k, i in inj.items():
            L.append(f"| {k} | {i['injected_values_recorded']} | {i['accuracy_vs_f5_gold']} | {i['n']} |")
    return "\n".join(L) + "\n"


def _bank_md(runs: Path) -> str | None:
    v3 = runs / "message_bank" / "v3"
    if not v3.exists():
        return None
    L = ["## Semantic reader (message bank v3)", "", "| check | n | correct | deadline question |", "|---|---|---|---|"]
    for f in sorted(v3.glob("checker_*.json")):
        d = json.loads(f.read_text())
        L.append(f"| {f.stem} | {d.get('n')} | {d.get('correct')} | {d.get('deadline_correct', '-')} |")
    tuning = sorted((runs / "tuning").glob("*/dev_metrics.json")) if (runs / "tuning").exists() else []
    if tuning:
        L += ["", "## Extractor dev tuning (dev split only)", "", "| pass | precision | recall | exact | "
              "honest→UNTESTABLE | errors |", "|---|---|---|---|---|---|"]
        for f in tuning:
            d = json.loads(f.read_text())
            m = d["metrics"]
            L.append(f"| {f.parent.name} | {m['precision']} | {m['recall']} | {m['exact_match']} | "
                     f"{m['honest_untestable_rate']} | {d['n_errors']} |")
    return "\n".join(L) + "\n"


def _e1(runs: Path, out: Path) -> str | None:
    root = runs / "e1"
    if not root.exists():
        return None
    from eval.e1 import summarize_grid
    s = summarize_grid(root, read=lambda p: _read_rows(p / "results.jsonl"))
    d = out / "e1"
    d.mkdir(parents=True, exist_ok=True)
    def front_text(front):
        # Points that never trade (all honest orders blocked) tie at one spot; list them as one group.
        never = [n for n in front if (s["points"][n]["blocked_honest_orders"] or 0) >= s["points"][n]["runs"] / 36
                 * 50 - 1e-9 and s["points"][n]["attack_loss"] == 0]
        rest = [n for n in front if n not in never]
        return ", ".join(rest) + (f"; plus {len(never)} tied points that never trade with S_main" if never else "")
    L = ["## E1 ablation grid (scripted buyer)", "",
         f"OBT Pareto front: {front_text(s['front']) or '-'}.", "",
         f"Reputation Pareto front: {front_text(s['reputation_front']) or '-'}.", "",
         f"Default (min utility cost + attack loss on the OBT front): **{s['default']}**. Reputation config for E2 "
         f"(its front, nearest OBT's utility cost): **{s['reputation_for_e2']}**.", "",
         "| point | defense | attack loss | utility cost | blocked honest orders | runs | invariant viol. | bound ok |"
         " front |", "|---|---|---|---|---|---|---|---|---|"]
    fronts = set(s["front"]) | set(s["reputation_front"])
    for name, p in sorted(s["points"].items()):
        mark = "default" if name == s["default"] else ("yes" if name in fronts else "")
        r1 = lambda x: "-" if x is None else f"{x:.1f}"  # noqa: E731
        L.append(f"| {name} | {p['defense']} | {r1(p['attack_loss'])} | {r1(p['utility_cost'])} | "
                 f"{r1(p['blocked_honest_orders'])} | {p['runs']} | {p['invariant_violations']} | {p['loss_bound_ok']} |"
                 f" {mark} |")
    (d / "e1.md").write_text("\n".join(L) + "\n")
    (d / "e1_summary.json").write_text(json.dumps(s, indent=1, sort_keys=True) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for defense, marker in (("obt", "o"), ("reputation", "s"), ("none", "x"), ("provenance", "^")):
        pts = sorted((p["utility_cost"], p["attack_loss"], n) for n, p in s["points"].items()
                     if p["defense"] == defense and p["utility_cost"] is not None and p["attack_loss"] is not None)
        if pts:
            ax.scatter([x for x, _, _ in pts], [y for _, y, _ in pts], marker=marker, label=defense, alpha=0.7)
    for front in (s["front"], s["reputation_front"]):
        fp = [(s["points"][n]["utility_cost"], s["points"][n]["attack_loss"]) for n in front]
        if fp:
            ax.plot([x for x, _ in fp], [y for _, y in fp], linewidth=1)
    for key, label in (("default", "OBT default"), ("reputation_for_e2", "reputation for E2")):
        if s[key]:
            p = s["points"][s[key]]
            ax.annotate(f"{label}: {s[key]}", (p["utility_cost"], p["attack_loss"]), fontsize=7,
                        xytext=(-10, 14), textcoords="offset points", arrowprops={"arrowstyle": "-", "lw": 0.5})
    never = [p for p in s["points"].values() if p["attack_loss"] == 0 and (p["blocked_honest_orders"] or 0) > 0]
    if never:
        ax.annotate(f"{len(never)} configs that never trade", (never[0]["utility_cost"], 0), fontsize=7,
                    xytext=(-110, 12), textcoords="offset points", arrowprops={"arrowstyle": "-", "lw": 0.5})
    # Loss spans $0 to ~$5k (no defense): symlog keeps both the zero points and the small OBT losses readable.
    ax.set_yscale("symlog", linthresh=10)
    ax.set_xlabel("utility cost vs none, honest S_main ($ per run)")
    ax.set_ylabel("mean loss from lies, scenarios 2-12 ($ per run)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    (d / "e1_pareto.svg").write_bytes(_svg(fig))
    plt.close(fig)
    return "e1/: e1.md, e1_summary.json, e1_pareto.svg (loss vs utility, fronts, default)"


def _e4(runs: Path, out: Path) -> str | None:
    f = runs / "e4" / "e4.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    L = ["## E4: extractor accuracy, both local models (frozen prompt)", "",
         "| extractor | split | n | precision | recall | template precision | template recall | exact | "
         "honest→UNTESTABLE | injected recorded |", "|---|---|---|---|---|---|---|---|---|---|"]
    for name in sorted(d):
        for split in ("test", "test_hard"):
            e = d[name].get(split)
            if e:
                L.append(f"| {name} | {split} | {e['n_messages']} | {e['precision']} | {e['recall']} | "
                         f"{e['template_precision']} | {e['template_recall']} | {e['exact_match']} | "
                         f"{e.get('honest_untestable_rate')} | {e['injection']['injected_values_recorded']} |")
    L += ["", "## E4: hard subset, shipping/ready/scheduled dates recorded as delivery deadlines", "",
          "| extractor | LLM alone (no guard) | with the code guard |", "|---|---|---|"]
    for name in sorted(d):
        on, off = d[name].get("test_hard"), d[name].get("test_hard_no_guard")
        if on and off:
            L.append(f"| {name} | {off['hard']['delivery_recorded']}/{off['hard']['n']} | "
                     f"{on['hard']['delivery_recorded']}/{on['hard']['n']} |")
    (out / "e4.md").write_text("\n".join(L) + "\n")
    return "e4.md: extractor accuracy for both local models, hard subset with and without the guard"


def _e6(runs: Path, out: Path) -> str | None:
    f = runs / "e6" / "e6.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    qs = sorted(h["ratio"] for h in d["history"])
    b, m = d["best"], d["max_damage"]
    L = ["## E6: adaptive attacker search against OBT (damage / Σ bound; > 1 would be a STOP)", "",
         f"{d['evaluations']} evaluations (budget {d['budget']}: {d['n_random']} random, then hill-climbing), seeds "
         f"{d['seeds']}, RNG seed {d['rng_seed']}, {d['wall_s']} s. Ratio quantiles over all evaluations: median "
         f"{qs[len(qs) // 2]:.3f}, p90 {qs[int(0.9 * len(qs))]:.3f}, max {qs[-1]:.4f}.", "",
         f"**Max ratio {b['ratio']:.4f}** (damage {b['damage']} vs bound {b['sum_bound']}, worst seed; mean over "
         f"seeds {b['mean_ratio']:.3f}). Most damage: {m['damage']} vs bound {m['sum_bound']} (ratio "
         f"{m['ratio']:.3f}).", "", "| parameter | max-ratio attacker | max-damage attacker |", "|---|---|---|"]
    for k in b["params"]:
        L.append(f"| {k} | {b['params'][k]} | {m['params'][k]} |")
    r = d["best_on_seeds_1_10"]
    L += ["", f"Max-ratio attacker on seeds 1-10: worst {r['ratio']:.4f}, mean {r['mean_ratio']:.4f}.", "",
          "| OBT config | worst ratio | mean ratio | damage | bound |", "|---|---|---|---|---|"]
    for k, v in d["best_under_variants"].items():
        L.append(f"| {k} | {v['ratio']:.4f} | {v['mean_ratio']:.4f} | {v['damage']} | {v['sum_bound']} |")
    conf = d.get("confirmation_llm_a2a")
    if conf:
        L += ["", "Confirmation with the eval pipeline (gpt-oss extractor, A2A transport, seeds 1-3):", "",
              "| attacker | worst ratio | mean ratio | damage | bound | rule extractor, inproc |", "|---|---|---|---|---|---|"]
        for k, v in conf.items():
            L.append(f"| {k} | {v['ratio']:.4f} | {v['mean_ratio']:.4f} | {v['damage']} | {v['sum_bound']} | "
                     f"{d[k]['ratio']:.4f} |")
    (out / "e6.md").write_text("\n".join(L) + "\n")
    return "e6.md: adaptive attacker search, max damage/bound ratio and the attackers"


def _e2b(runs: Path, out: Path) -> str | None:
    f = runs / "e2b" / "results.jsonl"
    if not f.exists() or not (runs / "e2" / "results.jsonl").exists():
        return None
    e2b, e2 = _read_rows(f), _read_rows(runs / "e2" / "results.jsonl")
    e1 = {"obt": [], "rep-strict": []}
    ef = runs / "e2b" / "e1_scripted.jsonl"
    if ef.exists():
        for line in ef.read_text().splitlines():
            r = json.loads(line)
            e1[r["defense"]].append(r)
    d = out / "e2b"
    d.mkdir(parents=True, exist_ok=True)
    (d / "e2b.md").write_text(e2b_report(e2b, e2))
    (d / "trust_over_time.svg").write_bytes(e2b_trust_svg(e2b, e2, e1))
    return "e2b/: trust-aware buyer view vs E2 (e2b.md) and trust over time with E2 and E1 overlays"


def _grid_md(runs: Path) -> str:
    """D33: the full reputation grid and its front, next to OBT's E1 front (scripted buyer, same config)."""
    root = runs / "rep_grid"
    if not root.exists() or not (runs / "e1" / "none").exists():
        return ""
    from eval import e1, rep_grid
    read = lambda p: _read_rows(p / "results.jsonl")  # noqa: E731
    g = rep_grid.summarize(root, none_dir=runs / "e1" / "none", read=read)
    L = ["", "## Reputation grid (D33; scripted buyer; n0 x θ x cap)", "",
         f"Non-degenerate front (excluding configs that lock out an honest supplier or never trade with one): "
         f"{', '.join(g['front'])}. Chosen (D22 rule, nearest the OBT reference utility {g['reference_utility']}): "
         f"**{g['pick']}**.", "",
         "| config | n0 | θ | cap | utility cost | attack loss | locked | never trades | front |",
         "|---|---|---|---|---|---|---|---|---|"]
    for name, p in sorted(g["points"].items(), key=lambda kv: (kv[1]["utility_cost"], kv[1]["attack_loss"])):
        mark = "chosen" if name == g["pick"] else ("yes" if name in g["front"] else "")
        L.append(f"| {name} | {p['rep_n0']} | {p['rep_theta']} | {p['rep_cap']:.0f} | {p['utility_cost']:.1f} | "
                 f"{p['attack_loss']:.1f} | {p['locked']} | {p['never_trades']} | {mark} |")
    if (runs / "e1").exists():
        s = e1.summarize_grid(runs / "e1", read=read)
        obt = sorted((s["points"][n]["utility_cost"], s["points"][n]["attack_loss"], n) for n in s["front"]
                     if s["points"][n]["attack_loss"] > 0)
        L += ["", "**Finding.** Reputation's front is binary: every non-degenerate reputation config either trades "
              "freely with an honest supplier (utility cost 0) and loses heavily to attacks, or never trades. OBT's "
              "front (E1, same scripted buyer) has intermediate operating points that trade with an honest supplier "
              "and bound the loss:", "", "| OBT config (E1 front) | utility cost | attack loss |", "|---|---|---|"]
        L += [f"| {n} | {u:.1f} | {a:.1f} |" for u, a, n in obt]
    return "\n".join(L) + "\n"


def _commits_md(runs: Path, e2c: list[dict]) -> str:
    """Which git commits E2c's runs were recorded on, and the check that a mid-run fix changed no decision."""
    by: dict = {}
    for i, r in enumerate(e2c, 1):
        by.setdefault(r["meta"]["git_commit"][:10], []).append(i)
    if len(by) < 2:
        return ""
    L = ["**Provenance.** E2c's runs span two git commits:"]
    L += [f"runs {v[0]}-{v[-1]} ({len(v)} runs) on `{k}`" for k, v in by.items()]
    L = [L[0] + " " + "; ".join(L[1:]) + "."]
    f = runs / "e2c" / "commit_check.json"
    if f.exists():
        c = json.loads(f.read_text())
        L.append(f"The second commit adds only the A2A keep-alive fix ({c['obt_diff']}): it changes connection "
                 f"handling, not any decision logic. Check: {c['configs']} with E2c's settings, scenarios {c['scenarios']}, "
                 f"seed {c['seed']}, {c['buyer']} buyer, {c['transport']}, run on both commits: "
                 f"{c['identical']}/{c['runs_compared']} runs identical ({c['compared']}).")
    return " ".join(L) + "\n\n"


def _e2c(runs: Path, out: Path) -> str | None:
    f = runs / "e2c" / "results.jsonl"
    if not f.exists() or not (runs / "e2" / "results.jsonl").exists():
        return None
    e2c, e2 = _read_rows(f), _read_rows(runs / "e2" / "results.jsonl")
    rows = e2 + e2c
    new = list(dict.fromkeys(r["defense"] for r in e2c))
    order = ["obt", "obt+planner", "rep-strict", "rep-default", *[d for d in new if d != "obt+planner"], "none",
             "provenance", "llm_selfcheck"]
    defenses = [d for d in order if any(r["defense"] == d for r in rows)]
    d = out / "e2c"
    d.mkdir(parents=True, exist_ok=True)
    (d / "ci.md").write_text("E2c (D32, D33) next to E2: the planner defenses and the new reputation config, "
                             "with E2's defenses and its `none` utility reference.\n\n" + _commits_md(runs, e2c)
                             + report(rows, defenses) + _grid_md(runs))
    e1 = {}
    ef = runs / "e2b" / "e1_scripted.jsonl"
    if ef.exists():
        for line in ef.read_text().splitlines():
            r = json.loads(line)
            e1.setdefault(r["defense"], []).append(r)
    reps = [x for x in new if x != "obt+planner"]
    panels = [("OBT budget B ($)", [("E2 obt (LLM)", e2, "obt", "B"), ("E2c obt+planner", e2c, "obt+planner", "B"),
                                    ("E1 scripted obt", e1.get("obt", []), "obt", "B")]),
              ("reputation score", [(f"E2c {x}", e2c, x, "score") for x in reps]
               + [("E1 scripted rep-strict", e1.get("rep-strict", []), "rep-strict", "score")]),
              ("S_main unit share (5-round mean)", [("E2 obt", e2, "obt", "share"),
                                                   ("E2c obt+planner", e2c, "obt+planner", "share"),
                                                   ("E2 rep-strict", e2, "rep-strict", "share")]
               + [(f"E2c {x}", e2c, x, "share") for x in reps])]
    (d / "trust_over_time.svg").write_bytes(trust_panels_svg(panels, "Trust over time: E2c vs E2 (honest S_main)"))
    return "e2c/: planner defenses and the new reputation config vs E2 (ci.md, trust_over_time.svg)"


def _fmt_ci(xs: list[float], nd: int = 1) -> str:
    """mean [95% bootstrap CI over seeds]; the same format as the main table."""
    from statistics import mean

    from eval.stats import bootstrap_ci
    if not xs:
        return "-"
    lo, hi = bootstrap_ci(xs)
    return f"{mean(xs):,.{nd}f} [{lo:,.{nd}f}, {hi:,.{nd}f}]"


def _e5_agg(rows: list[dict], d: str) -> dict:
    """E5 over every seed (D41): loss from lies and utility cost per seed (mean [CI]), the loss split over all
    attack runs, honest S_main share, loss per 100 S_main units (D40), and the largest per-run damage/bound."""
    from statistics import mean

    from eval.stats import (attack_loss_by_seed, loss_per_100_units, loss_split, utility_cost_by_seed,
                            utility_pct_by_seed)
    al = attack_loss_by_seed(rows, d)
    lbs = [r["metrics"]["loss_bound"] for r in rows if r["defense"] == d and r["metrics"]["loss_bound"]["events"]]
    ratios = [lb["damage"] / lb["sum_bound"] for lb in lbs if lb["sum_bound"]]
    sh = [x for x in (main_share(r) for r in rows if r["defense"] == d and r["scenario"] == 1) if x is not None]
    pu = loss_per_100_units(rows, d)
    up = list(utility_pct_by_seed(rows, d).values())
    return {"seeds": sorted(al), "loss": list(al.values()), "split": loss_split(rows, d),
            "util": list(utility_cost_by_seed(rows, d).values()), "util_pct": mean(up) if up else None,
            "share": mean(sh) if sh else None, "per_unit": pu,
            "max_ratio": max(ratios) if ratios else None}


def _e5_row(label: str, rows: list[dict], d: str, none_rows: list[dict]) -> dict:
    """One E5 table row on seed 1: loss split, damage vs bound, utility cost against `none_rows`' honest run."""
    by = {r["scenario"]: r for r in rows if r["defense"] == d and r["seed"] == 1}
    none = {r["scenario"]: r for r in none_rows if r["defense"] == "none" and r["seed"] == 1}
    ls = loss_split([r for r in rows if r["seed"] == 1], d)
    ev = [r["metrics"]["loss_bound"] for r in by.values() if r["metrics"]["loss_bound"]["events"]]
    ratios = [lb["damage"] / lb["sum_bound"] for lb in ev if lb["sum_bound"]]
    util = {n: by[n]["total_cost"] - none[n]["total_cost"] for n in (1, 9) if n in by and n in none}
    share = main_share(by[1]) if 1 in by else None
    return {"label": label, "runs": len(by), "split": ls, "events": sum(len(lb["events"]) for lb in ev),
            "damage": sum(lb["damage"] for lb in ev), "bound": sum(lb["sum_bound"] for lb in ev),
            "max_ratio": max(ratios) if ratios else None,
            "bound_ok": all(r["metrics"]["loss_bound"]["ok"] is not False for r in by.values()),
            "violations": sum(r["metrics"]["invariant_violations"]["count"] for r in by.values()),
            "util": util, "util_pct": {n: 100 * u / none[n]["total_cost"] for n, u in util.items()},
            "share": share}


def _e5(runs: Path, out: Path) -> str | None:
    """E5 (D37, D37a): paid buyers, frozen local gpt-oss extractor, seed 1, in E2c's format. v2 (run-scoped reply
    cache) next to v1 (superseded: cross-run reply reuse), gpt-oss seed-1 rows for reference, the paid models'
    extractor eval, and the spend from the ledger split into v1 and v2."""
    root, v1 = runs / "e5", runs / "e5" / "_v1_shared_cache"
    read = lambda f: _read_rows(f) if f.exists() else []            # noqa: E731
    luna, terra = read(root / "luna" / "results.jsonl"), read(root / "terra" / "results.jsonl")
    luna1, terra1 = read(v1 / "luna" / "results.jsonl"), read(v1 / "terra" / "results.jsonl")
    if not (luna or terra or luna1 or terra1):
        return None
    e2c, e2 = read(runs / "e2c" / "results.jsonl"), read(runs / "e2" / "results.jsonl")
    rows = [("v2", _e5_row("Luna obt+planner", luna, "obt+planner", luna)),
            ("v1", _e5_row("Luna obt+planner", luna1, "obt+planner", luna1)),
            ("v2", _e5_row("Luna none", luna, "none", luna)),
            ("v1", _e5_row("Luna none", luna1, "none", luna1)),
            ("v2", _e5_row("Terra obt+planner", terra, "obt+planner", terra)),
            ("v1", _e5_row("Terra obt+planner (vs Luna none)", terra1, "obt+planner", luna1)),
            ("v2", _e5_row("Terra none", terra, "none", terra)),
            ("ref", _e5_row("gpt-oss obt+planner (E2c, s1)", e2c, "obt+planner", e2)),
            ("ref", _e5_row("gpt-oss none (E2, s1)", e2, "none", e2))]
    rows = [(v, r) for v, r in rows if r["runs"]]
    f = lambda x, p=1: "n/a" if x is None else f"{x:,.{p}f}"          # noqa: E731
    L = ["# E5: paid buyers (GPT-5.6 Luna, Terra)", "",
         "DECISIONS D37, D37a, D41. The buyer is the paid model with `reasoning_effort=low`, and the extractor is the "
         "frozen local gpt-oss:20b (D24). OBT default (b0 5%, W 0, δ 0), k = 1, 50 rounds, A2A.", "",
         "## v2 over every seed (mean [95% bootstrap CI over seeds])", "",
         "| run | seeds | loss from lies | damage | reroute premium | resid | utility cost | % of cost | "
         "S_main share | max damage/bound |", "|---|---|---|---|---|---|---|---|---|---|"]
    for label, rs, d in (("Luna obt+planner", luna, "obt+planner"), ("Luna none", luna, "none"),
                         ("Terra obt+planner", terra, "obt+planner"), ("Terra none", terra, "none")):
        a = _e5_agg(rs, d) if rs else None
        if not a or not a["loss"]:
            continue
        sp = a["split"]
        L.append(f"| {label} | {', '.join(map(str, a['seeds']))} | {_fmt_ci(a['loss'])} | {f(sp['damage'])} | "
                 f"{f(sp['reroute'])} | {f(sp['resid'])} | {_fmt_ci(a['util'])} | {f(a['util_pct'], 2)}% | "
                 f"{f(a['share'], 3)} | {f(a['max_ratio'], 3)} |")
    L += ["", "## Seed 1: v2 next to v1 (superseded) and the gpt-oss reference", "",
         "- **v2** (current): every buyer call sampled fresh; the reply cache is scoped to one run and call index "
         "(resume only). Terra has its own `none` baseline.",
         "- **v1** (superseded: cross-run reply reuse): byte-identical prompts in another run reused an earlier paid "
         "reply (134/1,200 Luna and 70/600 Terra buyer calls). Terra's utility there was against Luna's `none`.",
         "- **ref**: the same configs with the local gpt-oss buyer on seed 1 (E2c / E2).", "",
         "## Loss from lies (mean of scenarios 2-12) = damage + reroute premium + resid", "",
         "| version | run | attack runs | loss from lies | damage | reroute premium | resid |", "|---|---|---|---|---|---|---|"]
    for v, r in rows:
        s = r["split"]
        L.append(f"| {v} | {r['label']} | {s['n']} | {f(s['loss'])} | {f(s['damage'])} | {f(s['reroute'])} | "
                 f"{f(s['resid'])} |")
    L += ["", "## Damage vs bound (OBT runs; DESIGN §6)", "",
          "| version | run | failure events | Σ damage | Σ bound | max damage/bound | bound held | invariant violations |",
          "|---|---|---|---|---|---|---|---|"]
    for v, r in rows:
        if "obt" in r["label"]:
            L.append(f"| {v} | {r['label']} | {r['events']} | {f(r['damage'])} | {f(r['bound'])} | "
                     f"{f(r['max_ratio'], 3)} | {'yes' if r['bound_ok'] else 'NO'} | {r['violations']} |")
    L += ["", "## Utility (primary: cost − cost(none), same seed, same buyer model unless noted)", "",
          "| version | run | utility cost, honest | % of none's honest cost | utility cost, noisy-honest | "
          "S_main unit share, honest |", "|---|---|---|---|---|---|"]
    for v, r in rows:
        L.append(f"| {v} | {r['label']} | {f(r['util'].get(1))} | {f(r['util_pct'].get(1), 2)}% | "
                 f"{f(r['util'].get(9))} | {f(r['share'], 3)} |")
    L += ["", "## Extractor eval: the paid models' own extraction (frozen prompt; per item, from v1, not re-paid)",
          "", "| extractor | split | n | precision | recall | exact | honest→UNTESTABLE | injected recorded |",
          "|---|---|---|---|---|---|---|---|"]
    hard = []
    for name in ("luna", "terra"):
        ef = root / name / "extractor.json"
        ef = ef if ef.exists() else v1 / name / "extractor.json"
        if not ef.exists():
            continue
        ext = json.loads(ef.read_text())["extractor"]
        for k in sorted(ext):
            if k.endswith(":no_guard") or (k.startswith("rule") and name == "terra"):
                continue                                    # the rule baseline is the same for both
            e = ext[k]
            L.append(f"| {k} | {e.get('split')} | {e.get('n_messages')} | {e.get('precision')} | {e.get('recall')} | "
                     f"{e.get('exact_match')} | {e.get('honest_untestable_rate')} | "
                     f"{e.get('injection', {}).get('injected_values_recorded')} |")
        for k in sorted(ext):
            if k.startswith("llm:") and k.endswith(":test_hard") and ext.get(k + ":no_guard"):
                on, off = ext[k], ext[k + ":no_guard"]
                hard.append(f"| {k[4:-10]} | {off['hard']['delivery_recorded']}/{off['hard']['n']} | "
                            f"{on['hard']['delivery_recorded']}/{on['hard']['n']} |")
    e4 = runs / "e4" / "e4.json"
    if e4.exists():
        d = json.loads(e4.read_text()).get("gpt-oss:20b", {})
        if d.get("test_hard") and d.get("test_hard_no_guard"):
            hard.append(f"| gpt-oss:20b (E4, reference) | {d['test_hard_no_guard']['hard']['delivery_recorded']}/"
                        f"{d['test_hard_no_guard']['hard']['n']} | {d['test_hard']['hard']['delivery_recorded']}/"
                        f"{d['test_hard']['hard']['n']} |")
    if hard:
        L += ["", "## Hard subset: shipping/ready/scheduled dates wrongly recorded as delivery deadlines (lower is "
              "better)", "", "| extractor | LLM alone (no guard) | with the code guard |", "|---|---|---|"] + hard
    led = [json.loads(x) for x in (runs / "cost_ledger.jsonl").read_text().splitlines()] \
        if (runs / "cost_ledger.jsonl").exists() else []
    if led:
        # v1's calls end with its last logged paid call; everything after is v2.
        v1_end = max((json.loads(x)["ts"] for d in ("luna", "terra") if (v1 / d / "llm_calls.jsonl").exists()
                      for x in (v1 / d / "llm_calls.jsonl").read_text().splitlines()), default=0.0)
        L += ["", "## Spend (runs/cost_ledger.jsonl; hard stop $16 over v1 + v2)", "",
              "| version | model | part | calls | input tokens | output tokens | of which reasoning | $ |",
              "|---|---|---|---|---|---|---|---|"]
        parts: dict = defaultdict(lambda: [0, 0, 0, 0, 0.0])
        for x in led:
            ver = "v1" if x["ts"] <= v1_end else "v2"
            p = parts[(ver, x["model"], "extractor eval" if x["run"] == "extractor_eval" else "eval runs (buyer)")]
            p[0] += 1
            p[1] += x["prompt_tokens"]
            p[2] += x["completion_tokens"]
            p[3] += x.get("reasoning_tokens", 0)
            p[4] += x["usd"]
        for (ver, m, part), p in sorted(parts.items()):
            L.append(f"| {ver} | {m} | {part} | {p[0]:,} | {p[1]:,} | {p[2]:,} | {p[3]:,} | {p[4]:.4f} |")
        for ver in ("v1", "v2"):
            L.append(f"| **{ver} total** | | | | | | | **{sum(p[4] for k, p in parts.items() if k[0] == ver):.4f}** |")
        L.append(f"| **total (ledger)** | | | {len(led):,} | | | | **{sum(x['usd'] for x in led):.4f}** |")
    d = out / "e5"
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.md").write_text("\n".join(L) + "\n")
    return "e5/report.md: paid buyers (Luna, Terra), v2 next to v1 (superseded), gpt-oss reference, extractor eval, spend"

def _enron(runs: Path, out: Path) -> str | None:
    """Enron real-text check (D34, D38): the frozen extractors on 100 labeled real sentences, per stratum."""
    f = runs / "enron" / "eval.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    L = ["## Enron real-text check (D34, D38): frozen extractors on 100 labeled real sentences", "",
         "Labels: `data/enron_candidates.csv` (drafted with LLM assistance, verified row by row by the author). "
         "Per stratum, never pooled. Target for wrong claims recorded: 0.", "",
         "| extractor | stratum | rows | commitments | labeled claims | claims UNTESTABLE | recorded | "
         "wrong recorded | recorded from non-commitments |", "|---|---|---|---|---|---|---|---|---|"]
    for name in sorted(d):
        for st in sorted(d[name]):
            x = d[name][st]
            L.append(f"| {name} | {st} | {x['rows']} | {x['commitments']} | {x['commitment_claims']} | "
                     f"{x['commitment_claims_untestable']} | {x['recorded_claims']} | {x['wrong_claims_recorded']} | "
                     f"{x['recorded_from_non_commitments']} |")
    (out / "enron.md").write_text("\n".join(L) + "\n")
    return "enron.md: frozen extractors on labeled real Enron sentences, per stratum"


def build(runs: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    built, index, pareto = {}, ["# Results (rebuilt from runs/ only)", ""], []
    for name, (rows, ext) in _evals(runs).items():
        summary = summarize(rows)
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        files = {"summary.md": markdown(summary, ext)}
        files["loss_from_lies.csv"] = _csv([["scenario", *summary["defenses"]]] + [
            [scenario_name(n), *[summary["loss_from_lies"].get(f"{n}|{x}") for x in summary["defenses"]]]
            for n in summary["scenarios"]])
        files["loss_bound.csv"] = _csv([["scenario|defense", "damage", "sum_bound", "reroute_cost_diff", "resid",
                                         "events", "bound_ok"]] + [
            [k, v["damage"], v["sum_bound"], v["reroute_cost_diff"], v["resid"], v["events"], v["bound_ok"]]
            for k, v in sorted(summary["loss_bound"].items())])
        files["utility.csv"] = _csv([["scenario|defense", "cost", "extra_cost_vs_none", "blocked_main_orders"]] + [
            [k, v["cost"], v["extra_cost_vs_none"], v["blocked_main_orders"]]
            for k, v in sorted(summary["utility"].items())])
        if ext:
            files["extractor.md"] = _extractor_md(ext)
        # Final-report statistics: bootstrap CIs over seeds, utility cost first, OBT damage vs bound.
        files["ci.md"] = report(rows, summary["defenses"])
        if {"obt", "none"} <= set(summary["defenses"]) and any(r["scenario"] == 1 for r in rows):
            files["trust_over_time.svg"] = trust_over_time_svg(
                rows, tuple(d for d in ("obt", "rep-strict", "none") if d in summary["defenses"]))
        metas = sorted({json.dumps({k: r["meta"][k] for k in ("git_commit", "git_dirty", "config_hash", "model",
                                                              "model_digest", "message_bank_sha256",
                                                              "extractor_prompt_sha256", "extractor_dataset_sha256",
                                                              "transport")}, sort_keys=True) for r in rows})
        files["provenance.json"] = json.dumps([json.loads(m) for m in metas], indent=1) + "\n"
        pts = []
        for x in summary["defenses"]:
            u = summary["utility"].get(f"1|{x}", {}).get("extra_cost_vs_none")
            y = _attack_loss(summary, x)
            if u is not None and y is not None:
                pts.append((x, u, y))
                pareto.append((f"{name}:{x}", u, y))
        if pts:
            files["loss_vs_utility.svg"] = _loss_vs_utility(pts, name)
        for fname, content in files.items():
            (d / fname).write_bytes(content if isinstance(content, bytes) else content.encode())
        built[name] = {"summary": summary, "files": sorted(files)}
        index.append(f"- **{name}**: {len(rows)} runs, config `{rows[0]['meta']['config_hash'][:12]}`, "
                     f"commit `{rows[0]['meta']['git_commit'][:10]}`: " + ", ".join(sorted(files)))
    if pareto:
        (out / "pareto.svg").write_bytes(_loss_vs_utility(sorted(pareto), "all evals: loss vs utility"))
        index.append("- pareto.svg: every eval x defense")
    e1 = _e1(runs, out)
    if e1:
        index.append("- " + e1)
    e4 = _e4(runs, out)
    if e4:
        index.append("- " + e4)
    e6 = _e6(runs, out)
    if e6:
        index.append("- " + e6)
    e2b = _e2b(runs, out)
    if e2b:
        index.append("- " + e2b)
    e2c = _e2c(runs, out)
    if e2c:
        index.append("- " + e2c)
    e5 = _e5(runs, out)
    if e5:
        index.append("- " + e5)
    enron = _enron(runs, out)
    if enron:
        index.append("- " + enron)
    paper = _paper_data(runs, out)
    if paper:
        index.append("- " + paper)
    bank = _bank_md(runs)
    if bank:
        (out / "bank.md").write_text(bank)
        index.append("- bank.md: semantic reader checks and extractor dev tuning")
    # evals.md, not index.md: on a case-insensitive filesystem index.md is the hand-written INDEX.md.
    (out / "evals.md").write_text("\n".join(index) + "\n")
    return built


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    built = build(Path(a.runs), Path(a.out))
    print(f"{len(built)} evals -> {a.out}/")



# ---------------------------------------------------------------- paper data (D35): everything eval/paper.py reads

def _smooth(ys: list[float], k: int = 5) -> list[float]:
    return [round(sum(ys[max(0, i - k + 1):i + 1]) / len(ys[max(0, i - k + 1):i + 1]), 4) for i in range(len(ys))]


def _trust_block(rows: list[dict], defenses: dict[str, tuple[str, ...]]) -> dict:
    from eval.stats import series, share_by_round
    out = {}
    for d, keys in defenses.items():
        block = {}
        for k in keys:
            ys = share_by_round(rows, d) if k == "share" else series(rows, d, k)
            if ys:
                block[k] = _smooth(ys) if k == "share" else [round(y, 4) for y in ys]
        if block:
            out[d] = block
    return out


def _paper_data(runs: Path, out: Path) -> str | None:
    from statistics import mean

    from eval import e1, rep_grid
    from eval.stats import (attack_loss_by_seed, bootstrap_ci, damage_vs_bound, loss_per_100_units, main_share,
                            per_unit_runs, utility_cost_by_seed, utility_pct_by_seed)
    read = lambda p: _read_rows(p / "results.jsonl") if (p / "results.jsonl").exists() else []  # noqa: E731
    e2, e2b, e2c = read(runs / "e2"), read(runs / "e2b"), read(runs / "e2c")
    if not e2:
        return None
    fd = out / "figdata"
    fd.mkdir(parents=True, exist_ok=True)
    tables: dict = {}
    fmt = lambda xs, nd=1: "-" if not xs else (  # noqa: E731
        f"{mean(xs):,.{nd}f} [{bootstrap_ci(xs)[0]:,.{nd}f}, {bootstrap_ci(xs)[1]:,.{nd}f}]")

    # Trust over time (honest supplier; share as a 5-round mean).
    e1s = [json.loads(x) for x in (runs / "e2b" / "e1_scripted.jsonl").read_text().splitlines()] \
        if (runs / "e2b" / "e1_scripted.jsonl").exists() else []
    trust = {"E2 LLM": _trust_block(e2, {"obt": ("B", "share"), "rep-strict": ("share",)}),
             "E2b trust-aware": _trust_block(e2b, {"obt": ("B", "share"), "rep-strict": ("score", "share")}),
             "E2c planner": _trust_block(e2c, {"obt+planner": ("B", "share"), "rep+planner": ("score", "share"),
                                               "rep-n18": ("score", "share")}),
             "E1 scripted": _trust_block(e1s, {"obt": ("B", "share"), "rep-strict": ("score", "share")})}
    (fd / "trust.json").write_text(json.dumps({k: v for k, v in trust.items() if v}, indent=1, sort_keys=True))

    # Pareto: E1's OBT grid and the D33 reputation grid (scripted buyer).
    if (runs / "e1").exists():
        s = e1.summarize_grid(runs / "e1", read=read)
        g = rep_grid.summarize(runs / "rep_grid", none_dir=runs / "e1" / "none", read=read) \
            if (runs / "rep_grid").exists() else {"points": {}, "front": [], "pick": None}
        obt = [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                "front": n in s["front"]} for n, p in sorted(s["points"].items()) if p["defense"] == "obt"]
        rep = [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                "front": n in g["front"], "never_trades": p["never_trades"], "locked": p["locked"]}
               for n, p in sorted(g["points"].items())]
        none = s["points"].get("none", {})
        (fd / "pareto.json").write_text(json.dumps({
            "obt": obt, "reputation": rep, "none": {"utility_cost": none.get("utility_cost", 0),
                                                   "attack_loss": none.get("attack_loss", 0)},
            "chosen": {"obt": s["default"], "reputation": g["pick"]}}, indent=1, sort_keys=True))
        tables["e1_obt_front"] = {
            "caption": "OBT Pareto front over b0, W and grace (E1, scripted buyer; $ per run). Chosen default marked.",
            "columns": ["config", "utility cost", "loss from lies", "default"],
            "rows": [[n, f"{s['points'][n]['utility_cost']:.1f}", f"{s['points'][n]['attack_loss']:.1f}",
                      "yes" if n == s["default"] else ""] for n in s["front"] if s["points"][n]["attack_loss"] > 0]}
        if g["points"]:
            tables["reputation_grid"] = {
                "caption": "Reputation grid over probation n0, threshold and cap (scripted buyer; $ per run). "
                           "Configs that lock out or never trade with an honest supplier are degenerate.",
                "columns": ["n0", "theta", "cap", "utility cost", "loss from lies", "locks out", "never trades",
                            "chosen"],
                "rows": [[p["rep_n0"], p["rep_theta"], f"{p['rep_cap']:.0f}", f"{p['utility_cost']:.1f}",
                          f"{p['attack_loss']:.1f}", "yes" if p["locked"] else "", "yes" if p["never_trades"] else "",
                          "yes" if n == g["pick"] else ""]
                         for n, p in sorted(g["points"].items(), key=lambda kv: (kv[1]["utility_cost"],
                                                                                 kv[1]["attack_loss"]))]}

    # Damage vs bound per run (OBT runs with failure events) and the E6 extremes.
    dmg = {}
    for label, rows, d in (("E2 obt", e2, "obt"), ("E2c obt+planner", e2c, "obt+planner")):
        pts = [{"damage": r["metrics"]["loss_bound"]["damage"], "sum_bound": r["metrics"]["loss_bound"]["sum_bound"],
                "events": len(r["metrics"]["loss_bound"]["events"])} for r in rows
               if r["defense"] == d and r["metrics"]["loss_bound"]["events"]]
        if pts:
            dmg[label] = pts
    e6f = runs / "e6" / "e6.json"
    if e6f.exists():
        e6 = json.loads(e6f.read_text())
        for key, label in (("best", "E6 max ratio"), ("max_damage", "E6 max damage")):
            dmg[label] = [{"damage": e6[key]["damage"], "sum_bound": e6[key]["sum_bound"], "events": None}]
        tables["e6"] = {"caption": f"Adaptive attacker search against OBT ({e6['evaluations']:,} attackers, "
                                   "worst of 3 seeds). A ratio above 1 would break the bound.",
                        "columns": ["attacker", "damage", "sum of bounds", "damage / bound"],
                        "rows": [[label, f"{e6[k]['damage']:.1f}", f"{e6[k]['sum_bound']:.1f}", f"{e6[k]['ratio']:.3f}"]
                                 for k, label in (("best", "max ratio"), ("max_damage", "max damage"))]}
    (fd / "damage_bound.json").write_text(json.dumps(dmg, indent=1, sort_keys=True))

    # Main LLM-buyer results: E2 with E2c alongside (5 seeds where run), and per-scenario loss.
    rows = e2 + e2c
    order = ["obt", "obt+planner", "rep-n18", "rep+planner", "rep-strict", "rep-default", "llm_selfcheck",
             "provenance", "none"]
    defenses = [d for d in order if any(r["defense"] == d for r in rows)]
    main_rows = []
    for d in defenses:
        al = list(attack_loss_by_seed(rows, d).values())
        uc = list(utility_cost_by_seed(rows, d).values())
        up = list(utility_pct_by_seed(rows, d).values())
        sh = [x for x in (main_share(r) for r in rows if r["defense"] == d and r["scenario"] == 1) if x is not None]
        main_rows.append([d, len(al), fmt(al), fmt(uc), f"{mean(up):.2f}" if up else "-",
                          f"{mean(sh):.3f}" if sh else "-"])
    tables["main"] = {"caption": "LLM buyer (gpt-oss:20b): loss from lies (mean of scenarios 2-12) and utility "
                                 "cost with an honest supplier, mean [95% bootstrap CI over seeds], $ per run.",
                      "columns": ["defense", "seeds", "loss from lies", "utility cost", "utility (% of cost)",
                                  "S_main share"], "rows": main_rows}
    from obt.attacks.suppliers import scenario_name
    scen = [scenario_name(n) for n in range(2, 13)]
    cost = {(r["scenario"], r["defense"], r["seed"]): r["total_cost"] for r in rows}
    means, cis = {}, {}
    for n, name in zip(range(2, 13), scen):
        for d in defenses:
            xs = [cost[(n, d, s)] - cost[(1, d, s)] for s in sorted({k[2] for k in cost})
                  if (n, d, s) in cost and (1, d, s) in cost]
            if xs:
                means[f"{name}|{d}"] = round(mean(xs), 2)
                cis[f"{name}|{d}"] = [round(v, 2) for v in bootstrap_ci(xs)]
    (fd / "loss.json").write_text(json.dumps({"defenses": defenses, "scenarios": scen, "mean": means, "ci": cis},
                                             indent=1, sort_keys=True))
    tables["loss_by_scenario"] = {"caption": "Loss from lies per scenario (LLM buyer, mean over seeds, $ per run).",
                                  "columns": ["scenario", *defenses],
                                  "rows": [[s.split("_", 1)[1].replace("_", " "),
                                            *[f"{means[f'{s}|{d}']:,.1f}" if f"{s}|{d}" in means else "-"
                                              for d in defenses]] for s in scen]}
    db = damage_vs_bound([r for r in rows if r["defense"] == "obt"])
    tables["damage_vs_bound"] = {"caption": "OBT damage against the per-event bound (E2, LLM buyer).",
                                 "columns": ["failure events", "runs", "damage", "sum of bounds", "max damage/bound"],
                                 "rows": [[db["events"], db["runs_with_events"], f"{db['total_damage']:,.1f}",
                                           f"{db['total_bound']:,.1f}",
                                           "-" if db["max_ratio"] is None else f"{db['max_ratio']:.3f}"]]}

    # Extractor (E4) and the second buyer model (E3, and E3b once run).
    e4f = runs / "e4" / "e4.json"
    if e4f.exists():
        e4 = json.loads(e4f.read_text())
        tables["extractor"] = {
            "caption": "Extractor on the 199-item test set and the 30-item hard subset (shipping/ready/scheduled "
                       "dates recorded as delivery deadlines, without and with the code guard).",
            "columns": ["extractor", "precision", "recall", "exact", "hard: LLM alone", "hard: with guard"],
            "rows": [[m, d["test"]["precision"], d["test"]["recall"], d["test"]["exact_match"],
                      f"{d['test_hard_no_guard']['hard']['delivery_recorded']}/30",
                      f"{d['test_hard']['hard']['delivery_recorded']}/30"] for m, d in sorted(e4.items())]}
        # E5 (D37): the paid models' own extraction, measured only in their extractor eval.
        for name in ("luna", "terra"):
            xf = runs / "e5" / name / "extractor.json"
            if xf.exists():
                x = json.loads(xf.read_text())["extractor"]
                k = next(k for k in x if k.startswith("llm:") and ":" not in k[4:].replace("gpt-5.6", ""))
                tables["extractor"]["rows"].append(
                    [k[4:], x[k]["precision"], x[k]["recall"], x[k]["exact_match"],
                     f"{x[k + ':test_hard:no_guard']['hard']['delivery_recorded']}/30",
                     f"{x[k + ':test_hard']['hard']['delivery_recorded']}/30"])
    from eval.stats import loss_split
    e3_rows = []
    money = lambda x: "n/a" if x is None else f"{x:,.1f}"  # noqa: E731
    for label, rs in (("E3", read(runs / "e3")), ("E3b", read(runs / "e3b"))):
        for d in sorted({r["defense"] for r in rs}):
            sp = loss_split(rs, d)
            if sp["n"]:
                e3_rows.append([label, d, sp["n"], money(sp["loss"]), money(sp["damage"]), money(sp["reroute"]),
                                money(sp["resid"])])
    if e3_rows:
        tables["second_model"] = {
            "caption": "Second buyer model (qwen3:8b; gpt-oss extractor; seed 1): loss from lies split into damage "
                       "(broken promises), reroute premium and resid (everything else, e.g. the buyer's own over-stocking), "
                       "mean over attack runs, $ per run. Damage is n/a for a defense without claims.",
            "columns": ["run", "defense", "attack runs", "loss from lies", "damage", "reroute premium", "resid"],
            "rows": e3_rows}
    e7f = runs / "e7" / "summary.json"
    if e7f.exists():
        e7 = json.loads(e7f.read_text())
        chk = e7.get("k1_matches_e1", {})
        tables["budget_k"] = {
            "caption": "Budget growth multiplier k, B = b0 + k x max honored exposure (E7, scripted buyer, OBT default, "
                       "12 scenarios x 3 seeds). Damage ratios use the per-event bound and the k-scaled a-priori bound. "
                       f"k = 1 at 50 rounds matches E1 in {chk.get('identical', '-')}/{chk.get('compared', '-')} runs "
                       "(all 36 with E1's extractor).",
            "columns": ["k", "rounds", "utility (% of cost)", "loss from lies", "S_main share",
                        "max damage/bound", "max damage/a-priori"],
            "rows": [[k, T, f"{p['utility_pct']:.2f}", f"{p['attack_loss']:.1f}", f"{p['main_share']:.3f}",
                      f"{p['max_ratio']:.3f}", f"{p['max_ratio_apriori']:.3f}"]
                     for k, v in e7["points"].items() for T, p in v.items()]}
    hf = runs / "horizon" / "summary.json"
    if hf.exists():
        h = json.loads(hf.read_text())
        tables["horizon"] = {"caption": "Horizon check (scripted buyer): utility cost as a % of the honest run's "
                                        "total cost, and loss from lies, at 50 and 100 rounds.",
                             "columns": ["defense", "utility % (T=50)", "utility % (T=100)", "loss (T=50)",
                                         "loss (T=100)"],
                             "rows": [[d, f"{v['50']['utility_pct']:.2f}", f"{v['100']['utility_pct']:.2f}",
                                       f"{v['50']['attack_loss']:.1f}", f"{v['100']['attack_loss']:.1f}"]
                                      for d, v in h["defenses"].items()]}
    # E5 v2 (D37a, D41): paid buyers, each against its own none, over every seed run. v1 is superseded.
    e5l, e5t = read(runs / "e5" / "luna"), read(runs / "e5" / "terra")
    if e5l or e5t:
        e5_rows = []
        for model, rs in (("GPT-5.6 Luna", e5l), ("GPT-5.6 Terra", e5t)):
            for d in ("obt+planner", "none"):
                a = _e5_agg(rs, d)
                if not a["loss"]:
                    continue
                sp = a["split"]
                e5_rows.append([model, d, len(a["seeds"]), fmt(a["loss"]), money(sp["damage"]), money(sp["reroute"]),
                                money(sp["resid"]), fmt(a["util"]),
                                "-" if a["util_pct"] is None else f"{a['util_pct']:.2f}",
                                "-" if a["share"] is None else f"{a['share']:.3f}",
                                "-" if a["max_ratio"] is None else f"{a['max_ratio']:.3f}"])
        tables["e5"] = {
            "caption": "Paid buyer models (E5 v2; reasoning effort low; frozen gpt-oss extractor; OBT default; "
                       "every buyer call sampled fresh): loss from lies (mean of scenarios 2-12) and utility cost "
                       "against the same model's none run, mean [95% bootstrap CI over seeds]; damage + reroute "
                       "premium + resid are means over all attack runs; $ per run.",
            "columns": ["buyer", "defense", "seeds", "loss from lies", "damage", "reroute premium", "resid",
                        "utility cost", "utility (% of cost)", "S_main share", "max damage/bound"],
            "rows": e5_rows}
    # Loss per 100 S_main units (D40): an explored metric, rejected for the paper. Still computed, with its per-run
    # trace, under results/per_unit/ only; not in tables.json, so no paper table, NUMBERS row or pack sheet uses it.
    pu_tables: dict = {}
    gpt = [(("E2c" if d in ("obt+planner", "rep-n18", "rep+planner") else "E2"), rows, d) for d in defenses]
    e5s = [(f"E5 {m}", rs, d) for m, rs in (("Luna", e5l), ("Terra", e5t)) if rs for d in ("obt+planner", "none")]
    pu_rows, trace = [], [["eval", "defense", "scenario", "seed", "loss_from_lies", "s_main_units", "all_units"]]
    for ev, rs, d in gpt + e5s:
        x = loss_per_100_units(rs, d)
        if not x["by_seed"]:
            continue
        al = attack_loss_by_seed(rs, d)
        pu_rows.append([ev, d, len(x["by_seed"]), fmt([al[s] for s in x["by_seed"]]),
                        "-" if x["units_per_run"] is None else f"{x['units_per_run']:.1f}",
                        "-" if x["attack_share"] is None else f"{x['attack_share']:.3f}",
                        fmt([v for v in x["by_seed"].values() if v is not None])])
        trace += [[ev, d, u["scenario"], u["seed"], round(u["loss"], 4), u["main_units"], u["all_units"]]
                  for u in per_unit_runs(rs, d)]
    pu_tables["loss_per_unit"] = {
        "caption": "Loss from lies per 100 units bought from S_main in the attack runs (D40): 100 x sum of losses / "
                   "sum of S_main units over scenarios 2-12 within a seed, mean [95% bootstrap CI over seeds], $ per "
                   "100 units. It compares defenses per unit actually traded, so one that avoids S_main is not "
                   "credited for it.",
        "columns": ["eval", "defense", "seeds", "loss from lies", "S_main units per attack run",
                    "S_main share (attack runs)", "loss per 100 S_main units"], "rows": pu_rows}
    by_sc = lambda items: [[scenario_name(n).split("_", 1)[1].replace("_", " "),  # noqa: E731
                            *["n/a" if loss_per_100_units(rs, d)["by_scenario"].get(n) is None
                              else f"{loss_per_100_units(rs, d)['by_scenario'][n]:,.1f}" for _, rs, d in items]]
                           for n in range(2, 13)]
    pu_tables["loss_per_unit_by_scenario"] = {
        "caption": "Loss per 100 S_main units by scenario, LLM buyer gpt-oss:20b (E2, E2c): 100 x sum of losses / "
                   "sum of S_main units over seeds (D40); n/a where no S_main unit was bought.",
        "columns": ["scenario", *[d for _, _, d in gpt]], "rows": by_sc(gpt)}
    if e5s:
        pu_tables["e5_loss_per_unit_by_scenario"] = {
            "caption": "Loss per 100 S_main units by scenario, paid buyers (E5 v2): 100 x sum of losses / sum of "
                       "S_main units over seeds (D40); n/a where no S_main unit was bought.",
            "columns": ["scenario", *[f"{ev[3:]} {d}" for ev, _, d in e5s]], "rows": by_sc(e5s)}
    (out / "per_unit").mkdir(parents=True, exist_ok=True)
    (out / "per_unit" / "runs.csv").write_text(_csv(trace))
    (out / "per_unit" / "loss_per_unit.json").write_text(json.dumps(pu_tables, indent=1, sort_keys=True) + "\n")
    # Enron real-text check (D34, D38): per stratum, never pooled.
    ef = runs / "enron" / "eval.json"
    if ef.exists():
        en = json.loads(ef.read_text())
        tables["enron"] = {
            "caption": "Frozen extractors on 100 labeled real Enron sentences (50 delivery-like, 50 price-only). "
                       "Wrong claims recorded is the safety metric (target 0); commitments the schema cannot express "
                       "(calendar dates, non-widget units) come out UNTESTABLE.",
            "columns": ["extractor", "stratum", "rows", "commitments", "claims UNTESTABLE", "recorded",
                        "wrong recorded", "from non-commitments"],
            "rows": [[name.replace("llm:", ""), st, x["rows"], x["commitments"],
                      f"{x['commitment_claims_untestable']}/{x['commitment_claims']}", x["recorded_claims"],
                      x["wrong_claims_recorded"], x["recorded_from_non_commitments"]]
                     for name in sorted(en) for st in sorted(en[name]) for x in [en[name][st]]]}
    # Independent annotator (D42, D42a): agreement with our labels, from runs/agreement/agreement.json.
    af = runs / "agreement" / "agreement.json"
    if af.exists():
        ag = json.loads(af.read_text())
        f4 = lambda x: "-" if x is None else f"{x:.3f}"   # noqa: E731
        sets = [("spot-check, all", ag["spotcheck"]["all"]), ("spot-check, v2 rows", ag["spotcheck"]["v2"]),
                ("spot-check, seeded errors", ag["spotcheck"]["seeded"]), ("Enron is_commitment", ag["enron"])]
        tables["annotator_agreement"] = {
            "caption": "Independent annotator (a professor not involved in the project) vs our labels (D42, D42a). "
                       "Kappa is marked degenerate when one side gives every row the same label (our v2 spot-check "
                       "labels are all yes; the seeded rows are all no); raw agreement and the disagreements then "
                       "carry the information. Detection rate: seeded errors the annotator marked no.",
            "columns": ["set", "rows", "raw agreement", "kappa", "kappa degenerate", "detection rate",
                        "disagreements"],
            "rows": [[name, x["n"], f4(x["raw_agreement"]), f4(x["kappa"]), "yes" if x["degenerate"] else "no",
                      f4(x.get("detection_rate")), len(x["disagreements"])] for name, x in sets]}
        tables["annotator_slots"] = {
            "caption": "Enron slot agreement on the rows both we and the annotator mark is_commitment = yes (D42a).",
            "columns": ["slot", "rows", "agree"],
            "rows": [[s, v["rows"], v["agree"]] for s, v in ag["enron"]["slot_agreement_on_rows_both_yes"].items()]}
        L = ["# Independent annotator agreement (D42, D42a)", ""]
        for name in ("annotator_agreement", "annotator_slots"):
            t = tables[name]
            L += [t["caption"], "", "| " + " | ".join(t["columns"]) + " |", "|" + "---|" * len(t["columns"])]
            L += ["| " + " | ".join(str(c) for c in r) + " |" for r in t["rows"]] + [""]
        L += ["## Every disagreement", ""]
        L += [f"- Spot-check row {d['row']} ({d['source']}, {d['id']}): ours {d['ours']}, annotator {d['theirs']}. "
              f"\"{d.get('message', '')}\" Recorded: {d.get('recorded', '')}."
              for d in ag["spotcheck"]["all"]["disagreements"]]
        L += [f"- Enron row {d['row']}: ours {d['ours']}, annotator {d['theirs']}. \"{d['message']}…\" Our note: "
              f"{d['our_notes']}. Annotator's note: {d['their_notes']}." for d in ag["enron"]["disagreements"]]
        L += [f"- Enron row {d['row']}, slot {d['slot']}: ours {d['ours']!r}, annotator {d['theirs']!r}."
              for d in ag["enron"]["slot_disagreements"]]
        (out / "annotation.md").write_text("\n".join(L) + "\n")
    # Bound tightness: the largest per-run damage / sum of per-event bounds in every OBT eval (DESIGN §6).
    tight = []
    for label, rs, d in (("E2 (gpt-oss)", e2, "obt"), ("E2c (gpt-oss)", e2c, "obt+planner"),
                         ("E3 (qwen3)", read(runs / "e3"), "obt"), ("E3b (qwen3)", read(runs / "e3b"), "obt+planner"),
                         ("E5 v2 (Luna)", e5l, "obt+planner"), ("E5 v2 (Terra)", e5t, "obt+planner")):
        lbs = [r["metrics"]["loss_bound"] for r in rs if r["defense"] == d and r["metrics"]["loss_bound"]["events"]]
        ratios = [lb["damage"] / lb["sum_bound"] for lb in lbs if lb["sum_bound"]]
        if lbs:
            tight.append([label, d, len(lbs), sum(len(lb["events"]) for lb in lbs),
                          f"{sum(lb['damage'] for lb in lbs):,.1f}", f"{sum(lb['sum_bound'] for lb in lbs):,.1f}",
                          f"{max(ratios):.3f}", "yes" if all(lb["ok"] is not False for lb in lbs) else "NO"])
    if e6f.exists():
        tight.append(["E6 (adaptive search)", "obt", f"{e6['evaluations']:,} attackers", "-", f"{e6['best']['damage']:.1f}",
                      f"{e6['best']['sum_bound']:.1f}", f"{e6['best']['ratio']:.3f}", "yes"])
    if e7f.exists():
        tight.append(["E7 (k = 1, 2, 4)", "obt", "-", "-", "-", "-",
                      f"{max(p['max_ratio'] for v in e7['points'].values() for p in v.values()):.3f}", "yes"])
    tables["bound_tightness"] = {
        "caption": "Bound tightness: the largest per-run ratio of damage to the sum of per-event bounds, per eval "
                   "(runs with failure events). A ratio above 1 would break the bound.",
        "columns": ["eval", "defense", "runs", "failure events", "damage", "sum of bounds", "max damage/bound",
                    "held"], "rows": tight}
    # E8 (D43): the LLM adversarial supplier, against honest runs of the same defense and seed (hash-matched).
    e8rows = read(runs / "e8")
    if any(r["scenario"] in (13, 14) for r in e8rows):
        from eval import e8 as e8m
        recs = e8m.per_run(e8rows, e8m.honest_runs(root=runs))
        f1 = lambda x, p=1: "-" if x is None else f"{x:,.{p}f}"   # noqa: E731
        tables["e8"] = {
            "caption": "E8: an LLM adversarial supplier (gpt-oss:20b, maximizing its own profit; black-box or "
                       "white-box) against each defense, LLM buyer gpt-oss:20b, seeds 1-3. Loss from lies against "
                       "the same defense's honest run (mean [95% bootstrap CI over seeds]) = damage + reroute "
                       "premium + resid (means); attacker profit = payments received - $3 x units delivered; "
                       "S_main share in the attack runs; $ per run.",
            "columns": ["knowledge", "defense", "seeds", "loss from lies", "damage", "reroute premium", "resid",
                        "max damage/bound", "attacker profit", "utility cost", "S_main share"],
            "rows": [[g["knowledge"], g["defense"], g["seeds"], fmt(g["loss"]), money(g["damage"]),
                      money(g["reroute"]), money(g["resid"]), "-" if g["max_ratio"] is None else f"{g['max_ratio']:.3f}",
                      fmt(g["profit"]), fmt(g["utility"]), f1(g["share"], 3)] for g in e8m.summary(recs)]}
        tables["e8_strategies"] = {
            "caption": "E8 attacker strategies per run, classified by code from the run logs (D43): identities that "
                       "farmed then defected, rounds with claim splitting, rounds with injection or decoy text, "
                       "identity resets, and orders invoiced above the message's stated price.",
            "columns": ["knowledge", "defense", "seed", "loss from lies", "attacker profit", "farm then defect",
                        "claim splitting", "injection or decoy", "identity resets", "invoice overpricing"],
            "rows": [[x["knowledge"], x["defense"], x["seed"], f1(x["loss"]), f1(x["profit"]), x["farm_then_defect"],
                      x["claim_splitting"], x["injection_or_decoy"], x["identity_resets"], x["invoice_overpricing"]]
                     for x in recs]}
        (out / "e8").mkdir(parents=True, exist_ok=True)
        keys = list(recs[0]) if recs else []
        (out / "e8" / "runs.csv").write_text(_csv([keys] + [[x[k] for k in keys] for x in recs]))
        (out / "e8" / "report.md").write_text(e8m.report_md(recs))
    # E9 (D44): the cloud/API-capacity domain (scripted, structured intents).
    e9rows = read(runs / "e9")
    if e9rows:
        from eval import e9 as e9m
        s9 = e9m.summary(e9rows)
        f3 = lambda x: "-" if x is None else f"{x:.3f}"   # noqa: E731
        tables["e9"] = {
            "caption": "E9, second domain (an agent buying cloud/API capacity; scripted buyer and providers, "
                       "structured intents, no natural-language extraction; seeds 1-3): loss from lies (mean of "
                       "scenarios 2-7) and utility cost against none, mean [95% bootstrap CI over seeds]; damage + "
                       "reroute premium + resid are means over attack runs; $ per run.",
            "columns": ["defense", "seeds", "loss from lies", "damage", "reroute premium", "resid", "utility cost",
                        "utility (% of cost)", "provider share"],
            "rows": [[d, len(v["loss"]), fmt(v["loss"]), money(v["split"]["damage"]), money(v["split"]["reroute"]),
                      money(v["split"]["resid"]), fmt(v["util"]),
                      f"{mean(v['util_pct']):.2f}" if v["util_pct"] else "-",
                      "-" if v["share"] is None else f"{v['share']:.3f}"] for d, v in s9["defenses"].items()]}
        b = s9["bound"]
        tables["e9_damage_vs_bound"] = {
            "caption": "E9 damage against the per-event bound (OBT runs; QUOTA and SLA events; docs/E9_PLAN.md §4). "
                       "A ratio above 1 would break the bound.",
            "columns": ["events", "failure events", "runs with events", "sum of bounds", "damage",
                        "max damage/bound", "max damage/a-priori", "held"],
            "rows": [["QUOTA", b["QUOTA"]["events"], b["QUOTA"]["runs"], f"{b['QUOTA']['sum_bound']:,.1f}", "-", "-",
                      "-", "-"],
                     ["SLA", b["SLA"]["events"], b["SLA"]["runs"], f"{b['SLA']['sum_bound']:,.1f}", "-", "-", "-", "-"],
                     ["all", b["QUOTA"]["events"] + b["SLA"]["events"], b["all"]["runs_with_events"],
                      f"{b['all']['sum_bound']:,.1f}", f"{b['all']['damage']:,.1f}", f3(b["all"]["max_ratio"]),
                      f3(b["all"]["max_apriori_ratio"]), "yes" if b["all"]["held"] else "NO"]]}
        (out / "e9").mkdir(parents=True, exist_ok=True)
        L = ["# E9: second domain, cloud/API capacity (D44)", "",
             "Scripted buyer and providers; structured intents (no natural-language extraction). Defense rows over "
             "seeds 1-3; $ per run.", "", "| " + " | ".join(tables["e9"]["columns"]) + " |",
             "|" + "---|" * len(tables["e9"]["columns"])]
        L += ["| " + " | ".join(str(c) for c in r) + " |" for r in tables["e9"]["rows"]]
        L += ["", "## Damage vs bound (OBT)", "", "| " + " | ".join(tables["e9_damage_vs_bound"]["columns"]) + " |",
              "|" + "---|" * len(tables["e9_damage_vs_bound"]["columns"])]
        L += ["| " + " | ".join(str(c) for c in r) + " |" for r in tables["e9_damage_vs_bound"]["rows"]]
        (out / "e9" / "report.md").write_text("\n".join(L) + "\n")
    # E9 calibration (D45): each defense's own cloud-domain config by E1's rule, next to the transferred defaults.
    if e9rows and (runs / "e9_calib").exists():
        from eval import e9_calib
        cs = e9_calib.summarize(runs / "e9_calib", runs / "e9")
        sc = e9m.summary(e9_calib.calibrated_rows(runs / "e9_calib", runs / "e9"))
        cfg = lambda p: ", ".join(f"{k} {v}" for k, v in cs["points"][p].items()  # noqa: E731
                                  if k in (("b0_frac", "budget_k") if cs["points"][p]["defense"] == "obt"
                                           else ("rep_n0", "rep_theta", "rep_cap")))
        side = []
        for d in ("obt", "rep-strict"):
            for setting, s, p in (("transferred", s9, cs["transferred"][d]), ("calibrated", sc, cs["picks"][d])):
                v = s["defenses"][d]
                side.append([d, setting, f"{p} ({cfg(p)})", fmt(v["loss"]), money(v["split"]["damage"]),
                             money(v["split"]["reroute"]), money(v["split"]["resid"]), fmt(v["util"]),
                             f"{mean(v['util_pct']):.2f}", "-" if v["share"] is None else f"{v['share']:.3f}"])
        tables["e9_calibration"] = {
            "caption": "E9 with transferred vs calibrated configs (D45). Transferred: the supply-domain configs E9 ran "
                       "with (D44). Calibrated: each defense's cloud-domain grid point chosen by E1's rule (Pareto "
                       "front in utility cost and attack loss, smallest sum; never-trading points excluded). Seeds "
                       "1-3, mean [95% bootstrap CI over seeds]; $ per run.",
            "columns": ["defense", "setting", "config", "loss from lies", "damage", "reroute premium", "resid",
                        "utility cost", "utility (% of cost)", "provider share"],
            "rows": side}
        tables["e9_calibration_grid"] = {
            "caption": "E9 calibration grids (D45): every point, scripted buyer, seeds 1-3, $ per run. OBT over b0 "
                       "(fraction of per-round spend) and k; reputation over n0, theta and cap (the D33 grid). "
                       "Max damage/bound over the point's OBT runs.",
            "columns": ["defense", "point", "utility cost", "loss from lies", "never trades", "locks out", "front",
                        "chosen", "transferred", "max damage/bound"],
            "rows": [["obt" if p["defense"] == "obt" else "rep-strict", n, f"{p['utility_cost']:.1f}",
                      f"{p['attack_loss']:.1f}", "yes" if p["never_trades"] else "", "yes" if p["locked"] else "",
                      "yes" if n in cs["fronts"]["obt" if p["defense"] == "obt" else "rep-strict"] else "",
                      "yes" if n in cs["picks"].values() else "", "yes" if n in cs["transferred"].values() else "",
                      f3(p["max_ratio"]) if p["defense"] == "obt" else "-"] for n, p in cs["points"].items()]}
        obt_pts = [p for p in cs["points"].values() if p["defense"] == "obt"]
        ratios = [p["max_ratio"] for p in obt_pts if p["max_ratio"] is not None]
        tables["e9_calibration_bound"] = {
            "caption": "E9 calibration (D45): the loss bound over every OBT grid run (8 points x 7 scenarios x 3 "
                       "seeds), and the harness check that the transferred grid points reproduce E9's runs.",
            "columns": ["OBT runs", "failure events", "max damage/bound", "held", "invariant violations",
                        "transferred points reproduce E9"],
            "rows": [[sum(p["runs"] for p in obt_pts), sum(p["failure_events"] for p in obt_pts), f3(max(ratios)),
                      "yes" if all(p["bound_held"] for p in obt_pts) else "NO",
                      sum(p["invariant_violations"] for p in cs["points"].values()),
                      "yes" if all(cs["reproduces_e9"].values()) else "NO"]]}
        none9 = s9["defenses"].get("none", {})
        pick = lambda d: {"obt": cs["picks"]["obt"], "reputation": cs["picks"]["rep-strict"]}[d]  # noqa: E731
        (fd / "e9_pareto.json").write_text(json.dumps({
            "obt": [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                     "front": n in cs["fronts"]["obt"]} for n, p in cs["points"].items() if p["defense"] == "obt"],
            "reputation": [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                            "front": n in cs["fronts"]["rep-strict"], "never_trades": p["never_trades"],
                            "locked": p["locked"]} for n, p in cs["points"].items() if p["defense"] == "reputation"],
            "none": {"utility_cost": 0.0, "attack_loss": round(mean(none9.get("loss") or [0.0]), 4)},
            "chosen": {d: pick(d) for d in ("obt", "reputation")}, "transferred": cs["transferred"]},
            indent=1, sort_keys=True))
        L = ["# E9 calibration: transferred vs calibrated configs (D45)", "",
             "Rule (fixed in E1, D22, with D33's never-trade exclusion): per defense, the Pareto front in (utility "
             "cost, attack loss) over its non-degenerate grid points; pick the front point with the smallest sum.", ""]
        for name in ("e9_calibration", "e9_calibration_bound", "e9_calibration_grid"):
            t = tables[name]
            L += [f"## {name}", "", t["caption"], "", "| " + " | ".join(t["columns"]) + " |",
                  "|" + "---|" * len(t["columns"])]
            L += ["| " + " | ".join(str(c) for c in r) + " |" for r in t["rows"]] + [""]
        L += [f"OBT front: {', '.join(cs['fronts']['obt'])}.", "",
              f"Reputation front (never-trading points excluded): {', '.join(cs['fronts']['rep-strict'])}.", ""]
        (out / "e9" / "calibration.md").write_text("\n".join(L))
        (out / "e9" / "calibration_pareto.svg").write_bytes(_loss_vs_utility(
            sorted((n, p["utility_cost"], p["attack_loss"]) for n, p in cs["points"].items()
                   if n in cs["fronts"]["obt"] + cs["fronts"]["rep-strict"]), "E9 calibration: Pareto fronts"))
    # D45a: the extended OBT grid (b0 up to 80%, k up to 4), same rule; D45's tables above stay on the original grid.
    ext_only = [n for n, d, _ in e9_calib.grid(ext=True) if (n, d) not in {(m, e) for m, e, _ in e9_calib.grid()}] \
        if e9rows and (runs / "e9_calib").exists() else []
    if ext_only and all((runs / "e9_calib" / n / "results.jsonl").exists() for n in ext_only):
        cx = e9_calib.summarize(runs / "e9_calib", runs / "e9", ext=True)
        sx = e9m.summary(e9_calib.calibrated_rows(runs / "e9_calib", runs / "e9", ext=True))
        rows_x = []
        for setting, s, p in (("transferred", s9, cs["transferred"]["obt"]), ("calibrated, D45 grid", sc,
                                                                                cs["picks"]["obt"]),
                              ("calibrated, extended grid", sx, cx["picks"]["obt"])):
            v = s["defenses"]["obt"]
            rows_x.append(["obt", setting, f"{p} ({cfg(p)})", fmt(v["loss"]), money(v["split"]["damage"]),
                           money(v["split"]["reroute"]), money(v["split"]["resid"]), fmt(v["util"]),
                           f"{mean(v['util_pct']):.2f}", "-" if v["share"] is None else f"{v['share']:.3f}"])
        tables["e9_calibration_ext"] = {
            "caption": "E9 OBT calibration on the extended grid (D45a: b0 2.5-80% of per-round spend x k 1, 2, 4), "
                       "same rule as D45, next to the transferred config and D45's pick. Seeds 1-3, mean [95% "
                       f"bootstrap CI over seeds]; $ per run. Pick moved: "
                       f"{'yes' if cx['picks']['obt'] != cs['picks']['obt'] else 'no'}; pick on a grid edge: "
                       f"{', '.join(cx['obt_pick_edges']) or 'none'}.",
            "columns": tables["e9_calibration"]["columns"], "rows": rows_x}
        obt_x = {n: p for n, p in cx["points"].items() if p["defense"] == "obt"}
        tables["e9_calibration_ext_grid"] = {
            "caption": "E9 extended OBT grid (D45a): every point, scripted buyer, seeds 1-3, $ per run. Max "
                       "damage/bound over the point's runs.",
            "columns": ["point", "b0", "k", "utility cost", "loss from lies", "never trades", "front", "chosen",
                        "new in D45a", "max damage/bound"],
            "rows": [[n, p["b0_frac"], p["budget_k"], f"{p['utility_cost']:.1f}", f"{p['attack_loss']:.1f}",
                      "yes" if p["never_trades"] else "", "yes" if n in cx["fronts"]["obt"] else "",
                      "yes" if n == cx["picks"]["obt"] else "", "yes" if n in ext_only else "",
                      f3(p["max_ratio"])] for n, p in obt_x.items()]}
        rx = [p["max_ratio"] for p in obt_x.values() if p["max_ratio"] is not None]
        tables["e9_calibration_ext_bound"] = {
            "caption": "E9 extended OBT grid (D45a): the loss bound over every run (18 points x 7 scenarios x 3 seeds).",
            "columns": ["OBT runs", "failure events", "max damage/bound", "held", "invariant violations",
                        "pick moved", "pick on grid edge"],
            "rows": [[sum(p["runs"] for p in obt_x.values()), sum(p["failure_events"] for p in obt_x.values()),
                      f3(max(rx)), "yes" if all(p["bound_held"] for p in obt_x.values()) else "NO",
                      sum(p["invariant_violations"] for p in obt_x.values()),
                      "yes" if cx["picks"]["obt"] != cs["picks"]["obt"] else "no",
                      ", ".join(cx["obt_pick_edges"]) or "none"]]}
        (fd / "e9_pareto_ext.json").write_text(json.dumps({
            "obt": [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                     "front": n in cx["fronts"]["obt"]} for n, p in obt_x.items()],
            "reputation": [{"name": n, "utility_cost": p["utility_cost"], "attack_loss": p["attack_loss"],
                            "front": n in cx["fronts"]["rep-strict"], "never_trades": p["never_trades"],
                            "locked": p["locked"]} for n, p in cx["points"].items() if p["defense"] == "reputation"],
            "none": {"utility_cost": 0.0, "attack_loss": round(mean(none9.get("loss") or [0.0]), 4)},
            "chosen": {"obt": cx["picks"]["obt"], "reputation": cx["picks"]["rep-strict"]},
            "transferred": cx["transferred"]}, indent=1, sort_keys=True))
        L = ["# E9 calibration, extended OBT grid (D45a)", "",
             "Same rule as D45. If the pick is again on a grid edge, that is reported, not extended further.", ""]
        for name in ("e9_calibration_ext", "e9_calibration_ext_bound", "e9_calibration_ext_grid"):
            t = tables[name]
            L += [f"## {name}", "", t["caption"], "", "| " + " | ".join(t["columns"]) + " |",
                  "|" + "---|" * len(t["columns"])]
            L += ["| " + " | ".join(str(c) for c in r) + " |" for r in t["rows"]] + [""]
        L += [f"OBT front (extended grid): {', '.join(cx['fronts']['obt'])}.", ""]
        (out / "e9" / "calibration_ext.md").write_text("\n".join(L))
    (out / "tables.json").write_text(json.dumps(tables, indent=1, sort_keys=True))
    return "figdata/ and tables.json: data for eval/paper.py (figures and LaTeX tables)"


if __name__ == "__main__":
    main()
