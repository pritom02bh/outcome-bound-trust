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
from eval.stats import e2b_report, e2b_trust_svg, report, trust_over_time_svg, trust_panels_svg
from obt.attacks.suppliers import scenario_name

# e1 grid points are summarized together as one grid (_e1), not as separate evals.
SKIP = ("_invalid", "_archive", "cache", "message_bank", "tuning", "e1", "e4", "e6", "rep_grid")


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
    paper = _paper_data(runs, out)
    if paper:
        index.append("- " + paper)
    bank = _bank_md(runs)
    if bank:
        (out / "bank.md").write_text(bank)
        index.append("- bank.md: semantic reader checks and extractor dev tuning")
    (out / "index.md").write_text("\n".join(index) + "\n")
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
    from eval.stats import (attack_loss_by_seed, bootstrap_ci, damage_vs_bound, main_share, utility_cost_by_seed,
                            utility_pct_by_seed)
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
                       "(broken promises), reroute and resid (everything else, e.g. the buyer's own over-stocking), "
                       "mean over attack runs, $ per run. Damage is n/a for a defense without claims.",
            "columns": ["run", "defense", "attack runs", "loss from lies", "damage", "reroute", "resid"],
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
    (out / "tables.json").write_text(json.dumps(tables, indent=1, sort_keys=True))
    return "figdata/ and tables.json: data for eval/paper.py (figures and LaTeX tables)"


if __name__ == "__main__":
    main()
