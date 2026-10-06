"""Table "Simulation and data at a glance" (D46a): every count read from the run logs and data files, each row with
its source. Called by eval.results (tables.json → sim_glance); eval.paper writes the .tex and eval.pack the .csv.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from obt.attacks.suppliers import SCENARIOS
from obt.env import cloud

# (label, run-log glob under the repo root, buyer, extractor, message source)
EXPERIMENTS = [
    ("E1", "runs/e1/*/results.jsonl", "scripted", "gpt-oss:20b (cached)", "message bank"),
    ("E1 reputation grid (D33)", "runs/rep_grid/*/results.jsonl", "scripted", "gpt-oss:20b (cached)", "message bank"),
    ("E2", "runs/e2/results.jsonl", "gpt-oss:20b", "gpt-oss:20b", "message bank"),
    ("E2b", "runs/e2b/results.jsonl", "gpt-oss:20b (trust-aware view)", "gpt-oss:20b", "message bank"),
    ("E2c", "runs/e2c/results.jsonl", "gpt-oss:20b", "gpt-oss:20b", "message bank"),
    ("E3", "runs/e3/results.jsonl", "qwen3:8b", "gpt-oss:20b", "message bank"),
    ("E3b", "runs/e3b/results.jsonl", "qwen3:8b", "gpt-oss:20b", "message bank"),
    ("E5", "runs/e5/*/results.jsonl", "GPT-5.6 Luna, Terra", "gpt-oss:20b", "message bank"),
    ("E7", "runs/e7/runs.jsonl", "scripted", "rule (code)", "message bank"),
    ("Horizon (T = 100)", "runs/horizon/t100/*/results.jsonl", "scripted", "gpt-oss:20b (cached)", "message bank"),
    ("E8", "runs/e8/results.jsonl", "gpt-oss:20b", "gpt-oss:20b",
     "LLM attacker (gpt-oss:20b, frozen prompts); honest runs reused from E2/E2c"),
    ("E9", "runs/e9/results.jsonl", "scripted", "structured parser (code)", "structured intents"),
    ("E9 calibration (D45, D45a)", "runs/e9_calib/*/results.jsonl", "scripted", "structured parser (code)",
     "structured intents"),
]


def _rows(root: Path, pattern: str) -> list[dict]:
    out = []
    for f in sorted(root.glob(pattern)):
        out += [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    return out


def _span(xs) -> str:
    xs = sorted(xs)
    return f"{xs[0]}" if len(xs) == 1 else (f"{xs[0]}-{xs[-1]}" if xs == list(range(xs[0], xs[-1] + 1))
                                            else ", ".join(map(str, xs)))


def table(root: Path) -> dict:
    rows = []
    add = lambda group, item, value, source: rows.append([group, item, value, source])  # noqa: E731
    # ---- simulation
    attacks = [n for n in SCENARIOS if n != 1]
    add("simulation", "rounds per run", "50 (E7 and the horizon check also 100)",
        "runs/*/results.jsonl (rounds)")
    add("simulation", "scenarios (supply chain)", f"{len(SCENARIOS)}: 1 honest + {len(attacks)} attacks "
        f"(scenarios 2-{max(attacks)}); E8 adds 2 LLM-attacker scenarios (13 black-box, 14 white-box)",
        "obt/attacks/suppliers.py (SCENARIOS, EXTRA)")
    add("simulation", "scenarios (cloud, E9)", f"{len(cloud.SCENARIOS)}: 1 honest + {len(cloud.SCENARIOS) - 1} attacks",
        "obt/env/cloud.py (SCENARIOS)")
    add("simulation", "defenses", "none, provenance, llm_selfcheck, reputation (rep-default, rep-strict, rep-n18, "
        "rep+planner), obt, obt+planner", "eval/run.py (VARIANTS)")
    add("simulation", "buyer models", "scripted (code), gpt-oss:20b, qwen3:8b, GPT-5.6 Luna, GPT-5.6 Terra",
        "runs/*/results.jsonl (buyer, model)")
    # ---- runs per experiment (counted from the logs)
    for label, pattern, buyer, extractor, source in EXPERIMENTS:
        rs = _rows(root, pattern)
        if not rs:
            continue
        seeds = {r["seed"] for r in rs}
        defs = sorted({r["defense"] for r in rs})
        add("runs", label, f"{len(rs):,} runs; {len({r['scenario'] for r in rs})} scenarios; seed{'s' if len(seeds) > 1 else ''} "
            f"{_span(seeds)}; "
            f"{len(defs)} defense{'s' if len(defs) != 1 else ''}; buyer {buyer}; extractor {extractor}; messages: "
            f"{source}", f"{pattern} (record count)")
    e4 = root / "runs" / "e4" / "e4.json"
    if e4.exists():
        add("runs", "E4", f"extractor evaluation, no game runs: {len(json.loads(e4.read_text()))} extractors "
            "(gpt-oss:20b, qwen3:8b, rule) on the test set and the hard subset", "runs/e4/e4.json")
    e6 = root / "runs" / "e6" / "e6.json"
    if e6.exists():
        x = json.loads(e6.read_text())
        add("runs", "E6", f"{x['evaluations']:,} attacker evaluations ({x['n_random']:,} random, then local search); "
            "scripted buyer, rule extractor, OBT at the E1 default", "runs/e6/e6.json (evaluations, n_random)")
    # ---- data (each row only when its files exist)
    if (root / "data" / "message_bank.json").exists():
        _bank(root, add)
    if (root / "data" / "extractor_dataset.json").exists():
        _dataset(root, add)
    if (root / "data" / "enron_candidates.csv").exists():
        _enron(root, add)
    if (root / "data" / "annotation_spotcheck_key.csv").exists() and (root / "annotation" / "enron_blind.csv").exists():
        _annotation(root, add)
    return {"caption": "Simulation and data at a glance. Run counts are record counts in the run logs; every row "
                       "names its source.",
            "columns": ["group", "item", "value", "source"], "rows": rows}


def _bank(root: Path, add) -> None:
    bank = json.loads((root / "data" / "message_bank.json").read_text())
    pool = {k: len(v) for k, v in bank["run"].items()}
    n_inj = len(bank["injections"]) if isinstance(bank["injections"], (list, dict)) else bank["injections"]
    g, sc = bank["generator"], bank["semantic_check"]
    q = [len(v) for v in sc["questions"].values()] if isinstance(sc["questions"], dict) else [sc["questions"]]
    nq = f"{min(q)}-{max(q)}" if min(q) != max(q) else f"{q[0]}"
    add("data", "message bank (runs)", f"{sum(pool.values())} templates ("
        + ", ".join(f"{k.replace('_', '-')} {v}" for k, v in sorted(pool.items())) + f") + {n_inj} "
        f"injection templates; generated by {g['model']} (temperature {g['temperature']}, seed {g['seed']}), kept only "
        f"if the numbers survive, a separate {sc['model']} reader confirms meaning ({nq} yes/no questions per kind, "
        "including an expected no) and the slots ground; frozen by sha256 (MESSAGE_BANK_SHA256)",
        "data/message_bank.json (run, injections, generator, semantic_check); obt/config.py")


def _dataset(root: Path, add) -> None:
    ds = json.loads((root / "data" / "extractor_dataset.json").read_text())
    inj = sum(1 for x in ds["test"] if x["kind"] == "injection")
    add("data", "extractor dataset", f"dev {len(ds['dev'])} (prompt tuning), test {len(ds['test'])} (incl. {inj} "
        f"injection), hard subset {len(ds['test_hard'])} (shipping/ready dates); frozen by sha256 "
        "(EXTRACTOR_DATASET_SHA256)", "data/extractor_dataset.json (dev, test, test_hard); obt/config.py")


def _enron(root: Path, add) -> None:
    en = list(csv.DictReader((root / "data" / "enron_candidates.csv").open(newline="")))
    strata = {}
    for r in en:
        strata[r["stratum"]] = strata.get(r["stratum"], 0) + 1
    add("data", "Enron real text", f"{len(en)} sentences (" + ", ".join(f"{k} {v}" for k, v in sorted(strata.items()))
        + f"), labeled ({sum(r['is_commitment'].strip().lower() == 'yes' for r in en)} commitments)",
        "data/enron_candidates.csv (stratum, is_commitment)")


def _annotation(root: Path, add) -> None:
    sp = list(csv.DictReader((root / "data" / "annotation_spotcheck_key.csv").open(newline="")))
    eb = list(csv.DictReader((root / "annotation" / "enron_blind.csv").open(newline="")))
    seeded = sum(r["source"] == "v1_seeded" for r in sp)
    add("data", "independent annotation", f"spot-check {len(sp)} rows ({len(sp) - seeded} v2 + {seeded} seeded "
        f"errors) + Enron {len(eb)} rows, one annotator", "annotation/spotcheck_blind.csv, annotation/enron_blind.csv, "
        "data/annotation_spotcheck_key.csv")
