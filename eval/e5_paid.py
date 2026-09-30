"""E5: paid runs, Plan B (DECISIONS D37).

    python -m eval.e5_paid                          # dry run: plan + projection from measured gpt-oss usage; no calls
    OBT_ALLOW_PAID=1 python -m eval.e5_paid pilot   # Terra obt+planner s1 + first 20 extractor test items, then
                                                    #   re-project the rest of Plan B from the pilot's real tokens
    OBT_ALLOW_PAID=1 python -m eval.e5_paid rest    # everything else (Luna first, then Terra) if pilot spend +
                                                    #   re-projected rest <= GO_USD; otherwise stops and says so
    python -m eval.e5_paid v2-plan                  # v2 (D37a): projection only, from v1's real per-call tokens
    OBT_ALLOW_PAID=1 python -m eval.e5_paid v2      # v2: every buyer run again with the run-scoped reply cache,
                                                    #   plus Terra none; runs only if spent + projection <= GO_USD

v1 (pilot + rest) reused paid replies across runs for byte-identical prompts; it is archived in runs/e5/_v1_shared_cache
and superseded by v2 (D37a). v2 keeps v1's extractor eval: it is per item, with no cross-run reuse.

Plan B: Luna runs obt+planner and none, Terra runs obt+planner; k = 1, all 12 scenarios, seed 1, the OBT default
(b0 5%, W 0, delta 0). Each model also gets the extractor eval: test set (199) and hard subset (30), LLM alone and
with the code deadline guard.

Extraction follows D24: in every eval run the paid model is the buyer and the extractor stays the frozen local
gpt-oss:20b, served from the shared extraction cache when it has seen the message. The paid models' own extraction
is measured only in the extractor eval.

Money: every paid call goes through obt.llm.CostMeter, a persistent ledger (runs/cost_ledger.json, per-call lines
in runs/cost_ledger.jsonl) with a hard stop at CAP_USD. Nothing is paid for twice: completed runs are skipped
on resume (run key + config hash), every paid reply is cached (LLM cache; a resumed partial run replays its paid
calls for free), and every extractor item is cached by text + model (extraction cache).

The OpenAI key is read from .env into this process only. It is never printed, logged or written anywhere.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from eval import run as er
from obt import llm
from obt.extractor import LLMExtractor
from obt.llm import RUNS

LUNA = "gpt-5.6-luna"
TERRA = "gpt-5.6-terra"
CAP_USD = 16.0            # hard stop on total paid spend (user decision, D37)
GO_USD = 14.0             # the rest of Plan B runs only if pilot spend + re-projected rest is at most this
MARGIN = 1.25             # safety factor on projected tokens
SIM = {"b0_frac": 0.05, "window": 0, "grace": 0}       # the OBT default (E1 pick)
LOCAL_EXTRACTOR = "gpt-oss:20b"
OUT = RUNS / "e5"
SCENARIOS = tuple(range(1, 13))
TEST_ITEMS, HARD_ITEMS, PILOT_ITEMS = 199, 30, 20
DEFENSES = {LUNA: ("obt+planner", "none"), TERRA: ("obt+planner", "none")}     # v2: Terra gets its own none (D37a)
V1 = RUNS / "e5" / "_v1_shared_cache"
DIRS = {LUNA: "luna", TERRA: "terra"}


class Abort(RuntimeError):
    pass


def plan() -> list[dict]:
    items = [{"kind": "run", "model": m, "scenario": n, "defense": d, "seed": 1}
             for m in (LUNA, TERRA) for d in DEFENSES[m] for n in SCENARIOS]
    items += [{"kind": "extractor_eval", "model": m, "scenario": None, "defense": None, "seed": None,
               "items": TEST_ITEMS + HARD_ITEMS} for m in (LUNA, TERRA)]
    return items


def eval_config(model: str, scenarios=SCENARIOS) -> er.EvalConfig:
    return er.EvalConfig(backend="openai", model=model, buyer="llm", scenarios=tuple(scenarios),
                         defenses=DEFENSES[model], seeds=(1,), extractor_eval=False, cap_usd=CAP_USD, cache=True,
                         sim=dict(SIM), extractor_model=LOCAL_EXTRACTOR, extractor_backend="ollama",
                         extractor_eval_model=model)


# ------------------------------------------------------------------ measured usage (gpt-oss logs, no calls)

def _calls(f: Path) -> list[dict]:
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def _scen(tag: str) -> int:
    return int(tag.split("|")[0].split("_")[0])


def measured_buyer(runs: Path = RUNS) -> dict[tuple[str, int], tuple[float, float]]:
    """(defense, scenario) -> mean buyer (input, output) tokens per run on the local gpt-oss buyer:
    obt+planner from E2c, none from E2 (seeds 1-3; E2c has no none)."""
    acc: dict = defaultdict(lambda: [0, 0, set()])
    for f, d, seeds in ((runs / "e2c" / "llm_calls.jsonl", "obt+planner", None),
                        (runs / "e2" / "llm_calls.jsonl", "none", {1, 2, 3})):
        for r in _calls(f):
            p = r.get("run", "").split("|")
            if r["purpose"] != "buyer" or len(p) < 3 or p[1] != d or (seeds and int(p[2][1:]) not in seeds):
                continue
            a = acc[(d, _scen(r["run"]))]
            a[0] += r["prompt_tokens"]
            a[1] += r["completion_tokens"]
            a[2].add(r["run"])
    return {k: (v[0] / len(v[2]), v[1] / len(v[2])) for k, v in acc.items()}


def measured_extract_item(runs: Path = RUNS) -> tuple[float, float]:
    """Mean (input, output) tokens of one uncached gpt-oss extractor call outside eval runs."""
    rows = [r for sub in ("e4", "tuning", "tuning/v3_pass1", "tuning/v3_hard")
            for r in _calls(runs / sub / "llm_calls.jsonl")
            if r["purpose"] == "extract" and not r["cached"] and r["model"] == LOCAL_EXTRACTOR]
    return (sum(r["prompt_tokens"] for r in rows) / len(rows), sum(r["completion_tokens"] for r in rows) / len(rows))


def _usd(model: str, tin: float, tout: float) -> float:
    pin, pout = llm.PAID_PRICES[model]
    return (tin * pin + tout * pout) / 1e6


def project(items: list[dict], buyer: dict, extract_item: tuple[float, float], scale=(1.0, 1.0),
            margin: float = MARGIN) -> dict:
    """Cost of `items`: buyer tokens per run x scale (paid / gpt-oss, from the pilot) and extractor-eval tokens
    per item, times the margin. In eval runs the extractor is local (free); only the buyer is paid."""
    out, missing = [], set()
    for it in items:
        if it["kind"] == "run":
            tin, tout = buyer[(it["defense"], it["scenario"])]
            tin, tout = tin * scale[0] * margin, tout * scale[1] * margin
        else:
            tin, tout = (x * it["items"] * margin for x in extract_item)
        if it["model"] not in llm.PAID_PRICES:
            missing.add(it["model"])
            usd = None
        else:
            usd = _usd(it["model"], tin, tout)
        out.append({**it, "tokens_in": round(tin), "tokens_out": round(tout), "usd": usd})
    total = None if missing else sum(p["usd"] for p in out)
    return {"items": out, "total_usd": total, "missing_prices": sorted(missing)}


def check(proj: dict, limit: float = GO_USD) -> None:
    if proj["missing_prices"]:
        raise Abort(f"no price in obt.llm.PAID_PRICES for {proj['missing_prices']}")
    if proj["total_usd"] > limit:
        raise Abort(f"projected ${proj['total_usd']:.2f} is over the ${limit:.0f} limit")


# ------------------------------------------------------------------ paid stages

def _load_key(env: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    """Put OPENAI_API_KEY into this process's environment from .env. Never prints or logs it."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    for line in env.read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "OPENAI_API_KEY" and v.strip():
            os.environ["OPENAI_API_KEY"] = v.strip().strip("'\"")
            return
    raise Abort("OPENAI_API_KEY not found in .env")


def meter() -> llm.CostMeter:
    return llm.CostMeter(cap=CAP_USD)


def ledger(runs: Path = RUNS) -> list[dict]:
    return _calls(runs / "cost_ledger.jsonl")


def usage(rows: list[dict]) -> dict:
    return {"calls": len(rows), "input": sum(r["prompt_tokens"] for r in rows),
            "output": sum(r["completion_tokens"] for r in rows),
            "reasoning": sum(r.get("reasoning_tokens", 0) for r in rows), "usd": sum(r["usd"] for r in rows)}


def run_models(model: str, scenarios=SCENARIOS) -> dict:
    """E5 eval runs for one model (resumable). Raises on any invariant or loss-bound violation (STOP rule)."""
    report = er.run_eval(eval_config(model, scenarios), OUT / DIRS[model], meter())
    if report["stopped"]:
        raise Abort(f"hard stop: {report['stopped']}")
    return report


def extractor_items(model: str, limit: int) -> dict:
    """The paid model's extraction on the first `limit` test items (cached per item, never paid twice)."""
    ec = eval_config(model)
    m = meter()
    er.check_budget(ec, m)
    ext = LLMExtractor(er.make_llm(ec, "extractor_eval", m, model=model, backend="openai"),
                       er.make_extract_cache(ec, model, "openai"))
    return er.extractor_eval(ext, limit)


def extractor_report(model: str) -> dict:
    """Full extractor eval (test 199 + hard 30, LLM alone and with the code guard), written to extractor.json."""
    ec = eval_config(model)
    (OUT / DIRS[model]).mkdir(parents=True, exist_ok=True)
    ec.log_dir = OUT / DIRS[model]
    return er._extractor_report(ec, OUT / DIRS[model], meter())


def reproject(runs: Path = RUNS) -> dict:
    """Pilot spend + the rest of Plan B projected from the pilot's real tokens."""
    rows = ledger(runs)
    pilot_run = [r for r in rows if r["model"] == TERRA and r["run"].startswith("1_honest|obt+planner|s1")]
    pilot_ext = [r for r in rows if r["model"] == TERRA and r["run"] == "extractor_eval"]
    if not pilot_run or not pilot_ext:
        raise Abort("no pilot usage in the ledger")
    buyer = measured_buyer(runs)
    run_u, ext_u = usage(pilot_run), usage(pilot_ext)
    base = buyer[("obt+planner", 1)]
    scale = (run_u["input"] / base[0], run_u["output"] / base[1])
    per_item = (ext_u["input"] / ext_u["calls"], ext_u["output"] / ext_u["calls"])
    # What is left: runs not yet in results (the pilot's run included) and extractor items not yet paid for.
    done = {(m, r["defense"], r["scenario"]) for m in (LUNA, TERRA)
            for r in er.load_results(runs / "e5" / DIRS[m]) if r["model"] == m}
    paid_items = {m: sum(r["run"] == "extractor_eval" and r["model"] == m for r in rows) for m in (LUNA, TERRA)}
    rest = [it for it in plan() if it["kind"] != "run" or (it["model"], it["defense"], it["scenario"]) not in done]
    for it in rest:
        if it["kind"] == "extractor_eval":
            it["items"] = max(0, TEST_ITEMS + HARD_ITEMS - paid_items[it["model"]])
    proj = project(rest, buyer, per_item, scale)
    spent = sum(r["usd"] for r in rows)
    return {"pilot": {"run": run_u, "extractor_items": ext_u}, "scale_vs_gpt_oss": scale,
            "paid_tokens_per_extractor_item": per_item, "spent_usd": spent, "rest": proj,
            "total_usd": spent + proj["total_usd"]}


def pilot() -> dict:
    _load_key()
    run_models(TERRA, scenarios=(1,))
    extractor_items(TERRA, PILOT_ITEMS)
    rp = reproject()
    (OUT / "pilot.json").write_text(json.dumps(rp, indent=1, default=str) + "\n")
    return rp


def rest() -> dict:
    _load_key()
    rp = reproject()
    if rp["total_usd"] > GO_USD:
        raise Abort(f"re-projected total ${rp['total_usd']:.2f} is over ${GO_USD:.0f}: not running the rest")
    for model in (LUNA, TERRA):
        run_models(model)
        extractor_report(model)
    spent = llm.CostMeter(cap=CAP_USD).spent()
    (OUT / "spend.json").write_text(json.dumps({"ledger_usd": spent, "by_model": {
        m: usage([r for r in ledger() if r["model"] == m]) for m in (LUNA, TERRA)}}, indent=1) + "\n")
    return {"spent_usd": spent}


def v1_per_call(v1: Path = V1) -> dict[tuple[str, str], tuple[float, float, int]]:
    """(model, defense) -> mean paid (input, output) tokens per buyer call and buyer calls per run, from v1's logs
    (calls answered from the cross-run cache are counted as calls but not as token samples)."""
    acc: dict = defaultdict(lambda: [0, 0, 0, 0, set()])            # tin, tout, paid n, all n, runs
    for m, d in DIRS.items():
        for r in _calls(v1 / d / "llm_calls.jsonl"):
            p = r.get("run", "").split("|")
            if r.get("backend") != "openai" or r["purpose"] != "buyer" or len(p) < 3:
                continue
            a = acc[(m, p[1])]
            a[3] += 1
            a[4].add(r["run"])
            if not r["cached"]:
                a[0] += r["prompt_tokens"]
                a[1] += r["completion_tokens"]
                a[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2], round(v[3] / len(v[4]))) for k, v in acc.items() if v[2]}


def project_v2(runs: Path = RUNS, margin: float = MARGIN) -> dict:
    """Spent so far + every v2 buyer run not yet done, each paying for all its calls (no cross-run reuse)."""
    pc = v1_per_call(runs / "e5" / "_v1_shared_cache")
    if (TERRA, "none") not in pc:                                     # Terra had no none in v1: scale by Luna's ratio
        lo, ln, t = pc[(LUNA, "obt+planner")], pc[(LUNA, "none")], pc[(TERRA, "obt+planner")]
        pc[(TERRA, "none")] = (t[0] * ln[0] / lo[0], t[1] * ln[1] / lo[1], ln[2])
    done = {(m, r["defense"], r["scenario"]) for m in (LUNA, TERRA)
            for r in er.load_results(runs / "e5" / DIRS[m]) if r["model"] == m}
    parts: dict = defaultdict(lambda: {"runs": 0, "input": 0.0, "output": 0.0, "usd": 0.0})
    for m in (LUNA, TERRA):
        for d in DEFENSES[m]:
            tin, tout, calls = pc[(m, d)]
            for n in SCENARIOS:
                if (m, d, n) in done:
                    continue
                p = parts[f"{m} {d}"]
                p["runs"] += 1
                p["input"] += tin * calls * margin
                p["output"] += tout * calls * margin
                p["usd"] += _usd(m, tin * calls * margin, tout * calls * margin)
    spent = llm.CostMeter(runs / "cost_ledger.json", cap=CAP_USD).spent()
    rest = sum(p["usd"] for p in parts.values())
    return {"per_call": {f"{m} {d}": v for (m, d), v in pc.items()}, "parts": dict(parts), "spent_usd": spent,
            "rest_usd": rest, "total_usd": spent + rest, "margin": margin}


def v2() -> dict:
    _load_key()
    proj = project_v2()
    (OUT / "v2_projection.json").write_text(json.dumps(proj, indent=1) + "\n")
    if proj["total_usd"] > GO_USD:
        raise Abort(f"projected total ${proj['total_usd']:.2f} (incl. ${proj['spent_usd']:.2f} spent) is over "
                    f"${GO_USD:.0f}: not running v2")
    for model in (LUNA, TERRA):
        run_models(model)
        # The extractor eval is per item with no cross-run reuse: v1's result is kept, not re-paid (D37a).
        src, dst = V1 / DIRS[model] / "extractor.json", OUT / DIRS[model] / "extractor.json"
        if src.exists() and not dst.exists():
            dst.write_text(src.read_text())
    spent = llm.CostMeter(cap=CAP_USD).spent()
    (OUT / "spend.json").write_text(json.dumps({"ledger_usd": spent, "by_model": {
        m: usage([r for r in ledger() if r["model"] == m]) for m in (LUNA, TERRA)}}, indent=1) + "\n")
    return {"spent_usd": spent, "projection": proj}


def main(argv: list[str] | None = None) -> None:
    stage = (argv or [None])[0]
    if stage == "v2-plan":
        print(json.dumps(project_v2(), indent=1, default=str))
        return
    if stage == "v2":
        print(json.dumps(v2(), indent=1, default=str))
        return
    if stage == "pilot":
        print(json.dumps(pilot(), indent=1, default=str))
        return
    if stage == "rest":
        print(json.dumps(rest(), indent=1, default=str))
        return
    proj = project(plan(), measured_buyer(), measured_extract_item())
    print(f"E5 Plan B ({len(plan())} items); buyer tokens measured on local gpt-oss runs, margin x{MARGIN}")
    for p in proj["items"]:
        usd = "-" if p["usd"] is None else f"${p['usd']:.3f}"
        what = f"s{p['scenario']} {p['defense']}" if p["kind"] == "run" else f"extractor eval ({p['items']})"
        print(f"  {p['model']:15s} {what:24s} in {p['tokens_in']:>9,} out {p['tokens_out']:>8,}  {usd}")
    total = "unknown (prices missing)" if proj["total_usd"] is None else f"${proj['total_usd']:.2f}"
    print(f"projected total: {total} (go limit ${GO_USD:.0f}; hard stop ${CAP_USD:.0f})")
    try:
        check(proj)
    except Abort as e:
        print(f"ABORT: {e}")
        sys.exit(1)
    print("Not run by this command. Paid stages: OBT_ALLOW_PAID=1 python -m eval.e5_paid pilot | rest")


if __name__ == "__main__":
    main(sys.argv[1:])
