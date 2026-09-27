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
from obt.attacks.suppliers import scenario_name

SKIP = ("_invalid", "_archive", "cache", "message_bank", "tuning")


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
            groups[r["meta"]["config_hash"]].append(r)
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


if __name__ == "__main__":
    main()
