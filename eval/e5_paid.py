"""E5: paid runs, PREPARE ONLY (FIXES Evaluation E5). This script never runs anything.

    python -m eval.e5_paid            # prints the plan, the projected cost, and the commands; aborts over $12

Plan: Luna, 12 scenarios x {none, obt} x seed 1, plus the extractor eval; Terra, scenarios {1, 3, 5, 8, 9, 11} x
obt x seed 1, plus the extractor eval. Token use is projected from measured local LLM-buyer runs (tokens per
call from the call logs, calls per round from the run records), times a safety margin. Prices come only from
obt.llm.PAID_PRICES, which is empty until the user fills in real prices: without them the projection aborts
(fails closed). Paid execution needs OBT_ALLOW_PAID=1, which only the user sets.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from obt import llm
from obt.llm import RUNS

# API model ids for GPT-5.6 Luna / Terra (DESIGN §10). Confirm them before any paid run.
LUNA = "gpt-5.6-luna"
TERRA = "gpt-5.6-terra"
CAP_USD = 12.0            # abort threshold for the projection; the harness's hard stop stays at $13
MARGIN = 1.5              # safety factor on measured token use (tokenizers differ across model families)
EXTRACTOR_ITEMS = 229     # 199 test + 30 hard-subset items; the no-guard ablation reuses the same outputs
ROUNDS = 50
# Fallback when no current LLM-buyer run exists: per-call means measured on the v1 local gpt-oss eval (its
# numbers are invalid for the paper, but its token counts per call are a fair size estimate).
FALLBACK = {("buyer", "none"): (1563, 63), ("buyer", "obt"): (1563, 63), ("replan", "obt"): (160, 1),
            ("extract", "obt"): (431, 44)}


class Abort(RuntimeError):
    pass


def plan() -> list[dict]:
    items = [{"kind": "run", "model": LUNA, "scenario": n, "defense": d, "seed": 1}
             for n in range(1, 13) for d in ("none", "obt")]
    items += [{"kind": "run", "model": TERRA, "scenario": n, "defense": "obt", "seed": 1} for n in (1, 3, 5, 8, 9, 11)]
    items += [{"kind": "extractor_eval", "model": m, "scenario": None, "defense": None, "seed": None}
              for m in (LUNA, TERRA)]
    return items


def measured_usage(runs: Path = RUNS) -> tuple[dict, str]:
    """(purpose, defense) -> (prompt tokens, completion tokens) per round, from local LLM-buyer runs."""
    per_call: dict = defaultdict(lambda: [0, 0, 0])            # tokens in, out, n (uncached calls only)
    calls: dict = defaultdict(lambda: [0, 0])                  # calls incl. cache hits, rounds
    for f in runs.rglob("results.jsonl"):
        if "_invalid" in str(f):
            continue
        for line in f.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("buyer") != "llm":
                continue
            for purpose, u in r["usage"]["by_purpose"].items():
                c = calls[(purpose.split(":")[0], r["defense"])]
                c[0] += u["calls"]
                c[1] += r["rounds"]
        log = f.parent / "llm_calls.jsonl"
        if log.exists():
            for line in log.read_text().splitlines():
                x = json.loads(line)
                if x.get("cached") or not x.get("run"):
                    continue
                parts = x["run"].split("|")
                if len(parts) >= 2:
                    k = per_call[(x["purpose"].split(":")[0], parts[1])]
                    k[0] += x["prompt_tokens"]
                    k[1] += x["completion_tokens"]
                    k[2] += 1
    usage = {}
    for key, (n_calls, n_rounds) in calls.items():
        tin, tout, n = per_call.get(key, (0, 0, 0))
        if n and n_rounds:
            usage[key] = (tin / n * n_calls / n_rounds, tout / n * n_calls / n_rounds)
    if usage:
        return usage, "measured on current local LLM-buyer runs"
    return dict(FALLBACK), "fallback: per-call sizes from the v1 local eval, one call per round"


def project(items: list[dict], per_round: dict, rounds: int = ROUNDS, extractor_items: int = EXTRACTOR_ITEMS) -> dict:
    out, missing = [], set()
    for it in items:
        if it["kind"] == "run":
            keys = [k for k in per_round if k[1] == it["defense"]]
            tin = sum(per_round[k][0] for k in keys) * rounds * MARGIN
            tout = sum(per_round[k][1] for k in keys) * rounds * MARGIN
        else:
            tin, tout = (x * extractor_items * MARGIN for x in per_round.get(("extract", "obt"), (0, 0)))
        price = llm.PAID_PRICES.get(it["model"])
        if price is None:
            missing.add(it["model"])
        usd = None if price is None else (tin * price[0] + tout * price[1]) / 1e6
        out.append({**it, "tokens_in": round(tin), "tokens_out": round(tout), "usd": usd})
    total = None if missing else sum(p["usd"] for p in out)
    return {"items": out, "total_usd": total, "missing_prices": sorted(missing)}


def check(proj: dict) -> None:
    if proj["missing_prices"]:
        raise Abort(f"no price in obt.llm.PAID_PRICES for {proj['missing_prices']}; fill in real prices first")
    if proj["total_usd"] > CAP_USD:
        raise Abort(f"projected ${proj['total_usd']:.2f} is over the ${CAP_USD:.0f} limit")


def commands() -> list[str]:
    base = "OBT_ALLOW_PAID=1 python -m eval.run --backend openai --buyer llm --seeds 1"
    return [f"{base} --model {LUNA} --scenarios 1-12 --defenses none,obt --out runs/e5_luna",
            f"{base} --model {TERRA} --scenarios 1,3,5,8,9,11 --defenses obt --out runs/e5_terra"]


def main(argv: list[str] | None = None) -> None:
    usage, source = measured_usage()
    proj = project(plan(), usage)
    print(f"E5 paid plan ({len(plan())} items); token use {source}, margin x{MARGIN}")
    for p in proj["items"]:
        usd = "-" if p["usd"] is None else f"${p['usd']:.3f}"
        what = f"s{p['scenario']} {p['defense']}" if p["kind"] == "run" else "extractor eval"
        print(f"  {p['model']:15s} {what:16s} in {p['tokens_in']:>8,} out {p['tokens_out']:>7,}  {usd}")
    total = "unknown (prices missing)" if proj["total_usd"] is None else f"${proj['total_usd']:.2f}"
    print(f"projected total: {total} (abort above ${CAP_USD:.0f}; hard stop ${llm.HARD_CAP_USD:.0f})")
    try:
        check(proj)
    except Abort as e:
        print(f"ABORT: {e}")
        sys.exit(1)
    print("Commands (NOT RUN by this script; only the user runs paid commands):")
    for c in commands():
        print("  " + c)


if __name__ == "__main__":
    main(sys.argv[1:])
