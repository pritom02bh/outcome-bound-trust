"""Gate activity (D47): what the OBT gate decided in every OBT and obt+planner run with an LLM buyer, from the run
logs only (no new runs). Called by eval.results: results/gate_activity.md, results/gate_activity/*.csv and the
tables gate_activity (per experiment) and gate_activity_by_scenario (per scenario, all experiments pooled).

Counted per run from trace[*].actions (the gate's own record of every decision):
  - proposed: ORDER actions to S_main (any of its identities); approved = EXECUTED, blocked = BLOCKED, by reason;
  - rerouted: every blocked S_main order's quantity goes to S_backup by code (obt/sim.py phase_execute); the
    units are checked against the run's metrics.rerouted_units;
  - backup orders the buyer placed itself (S_backup orders minus the code's reroutes), and blocked payments.
Remediation orders (code re-orders after a FAILED claim) are not buyer proposals and are not counted.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from obt.attacks.suppliers import EXTRA, scenario_name

EXPERIMENTS = [("E2", ("e2/results.jsonl",)), ("E2b", ("e2b/results.jsonl",)), ("E2c", ("e2c/results.jsonl",)),
               ("E3", ("e3/results.jsonl",)), ("E3b", ("e3b/results.jsonl",)),
               ("E5", ("e5/luna/results.jsonl", "e5/terra/results.jsonl")), ("E8", ("e8/results.jsonl",))]
# Gate reason codes (obt/gate.py allow), in the order the gate checks them.
REASONS = {
    "NO_CITATION": "no claim cited",
    "UNKNOWN_CLAIM": "cited claim not in the ledger",
    "WRONG_COUNTERPARTY": "cited claim belongs to another supplier",
    "BAD_CLAIM": "cited claim FAILED, UNTESTABLE or LAPSED",
    "CLAIM_MISMATCH": "no pending DELIVERY claim for the item, or its deadline is closer than the lead time",
    "PRICE_MISMATCH": "not exactly one valid PRICE claim matching the order's unit price and value",
    "OVER_CLAIM": "quantity above the cited claims' remaining capacity",
    "OVER_BUDGET": "exposure would exceed the trust budget, P(c) + value > B(c)",
}
BACKUP = "S_backup"


def _scenario(n: int) -> str:
    return f"{n}_{EXTRA[n][0]}" if n in EXTRA else scenario_name(n)


def runs(root: Path) -> list[dict]:
    """One record per OBT / obt+planner LLM-buyer run: its experiment, scenario and gate counts."""
    out = []
    for exp, logs in EXPERIMENTS:
        for log in logs:
            f = root / "runs" / log
            if not f.exists():
                continue
            seen = set()
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                r = json.loads(line)
                if not str(r["defense"]).startswith("obt") or r.get("buyer") != "llm":
                    continue
                key = (r["scenario"], r["defense"], r["seed"], r.get("model"))
                if key in seen:
                    raise ValueError(f"{f}:{i}: duplicate run {key}")
                seen.add(key)
                c = Counter()
                reasons = Counter()
                blocked_units = 0
                for t in r["trace"]:
                    main = [a for a in t["actions"] if a[0] == "ORDER" and a[1] != BACKUP]
                    blocked = [a for a in main if a[4] == "BLOCKED"]
                    c["proposed"] += len(main)
                    c["approved"] += sum(a[4] == "EXECUTED" for a in main)
                    c["blocked"] += len(blocked)
                    reasons.update(a[5] for a in blocked)
                    blocked_units += sum(a[2] for a in blocked if a[2] > 0)
                    c["rerouted_orders"] += t.get("rerouted_orders", 0)
                    c["backup_own"] += sum(1 for a in t["actions"] if a[0] == "ORDER" and a[1] == BACKUP) \
                        - t.get("rerouted_orders", 0)
                    c["payments_blocked"] += sum(1 for a in t["actions"] if a[0] == "PAYMENT" and a[4] == "BLOCKED")
                if c["approved"] + c["blocked"] != c["proposed"]:
                    raise ValueError(f"{f}:{i}: an S_main order is neither EXECUTED nor BLOCKED")
                if blocked_units != r["metrics"]["rerouted_units"]:
                    raise ValueError(f"{f}:{i}: blocked units {blocked_units} != metrics.rerouted_units "
                                     f"{r['metrics']['rerouted_units']}")
                out.append({"experiment": exp, "log": f"runs/{log}", "line": i, "scenario": r["scenario"],
                            "defense": r["defense"], "seed": r["seed"], "model": r.get("model"), **c,
                            "rerouted_units": r["metrics"]["rerouted_units"], "reasons": dict(reasons)})
    return out


def _total(rs: list[dict]) -> dict:
    t = Counter()
    reasons = Counter()
    for r in rs:
        t.update({k: r[k] for k in ("proposed", "approved", "blocked", "rerouted_orders", "rerouted_units",
                                    "backup_own", "payments_blocked")})
        reasons.update(r["reasons"])
    return {**t, "runs": len(rs), "runs_with_block": sum(1 for r in rs if r["blocked"]), "reasons": dict(reasons)}


def _pct(a: int, b: int) -> str:
    return "-" if not b else f"{100 * a / b:.1f}"


def tables(root: Path) -> dict:
    rs = runs(root)
    if not rs:
        return {}
    codes = [k for k in REASONS if any(k in r["reasons"] for r in rs)]
    unknown = sorted({k for r in rs for k in r["reasons"]} - set(REASONS))
    if unknown:
        raise ValueError(f"unexpected block reasons: {unknown}")
    cols = ["runs", "runs with ≥1 block", "share of runs with a block (%)", "S_main orders proposed", "approved",
            "blocked", "blocked (%)", *codes, "units rerouted to backup", "blocked payments"]

    def row(label, sub):
        t = _total(sub)
        return [*label, t["runs"], t["runs_with_block"], _pct(t["runs_with_block"], t["runs"]), t["proposed"],
                t["approved"], t["blocked"], _pct(t["blocked"], t["proposed"]),
                *[t["reasons"].get(k, 0) for k in codes], t["rerouted_units"], t["payments_blocked"]]
    by_exp = []
    for exp, _ in EXPERIMENTS:
        for d in sorted({r["defense"] for r in rs if r["experiment"] == exp}):
            sub = [r for r in rs if r["experiment"] == exp and r["defense"] == d]
            models = sorted({r["model"] for r in sub})
            by_exp.append(row([exp, d, ", ".join(models), _seeds(sub)], sub))
    by_exp.append(row(["all", "obt, obt+planner", "-", "-"], rs))
    by_sc = [row([_scenario(n)], [r for r in rs if r["scenario"] == n]) for n in sorted({r["scenario"] for r in rs})]
    by_sc.append(row(["all"], rs))
    return {
        "gate_activity": {
            "caption": "Gate activity in every OBT and obt+planner run with an LLM buyer (from the run logs; D47). "
                       "Proposed = buyer orders to S_main; every blocked order's quantity is rerouted to S_backup by "
                       "code. Reason codes as in obt/gate.py.",
            "columns": ["experiment", "defense", "buyer model", "seeds", *cols], "rows": by_exp},
        "gate_activity_by_scenario": {
            "caption": "Gate activity per scenario, all experiments in the gate_activity table pooled (D47).",
            "columns": ["scenario", *cols], "rows": by_sc},
        "_runs": rs, "_codes": codes}


def _seeds(sub: list[dict]) -> str:
    s = sorted({r["seed"] for r in sub})
    return f"{s[0]}" if len(s) == 1 else f"{s[0]}-{s[-1]}" if s == list(range(s[0], s[-1] + 1)) else ", ".join(map(str, s))


def report_md(t: dict) -> str:
    def md(name):
        x = t[name]
        return ["| " + " | ".join(map(str, x["columns"])) + " |", "|" + "---|" * len(x["columns"])] + \
               ["| " + " | ".join(map(str, r)) + " |" for r in x["rows"]]
    rs = t["_runs"]
    a = _total(rs)
    planner = _total([r for r in rs if r["defense"] == "obt+planner"])
    plain = _total([r for r in rs if r["defense"] == "obt"])
    L = ["# Gate activity: OBT and obt+planner runs with an LLM buyer (D47)", "",
         "From the run logs only (no new runs): every gate decision recorded in `trace[*].actions` of every `obt` and "
         "`obt+planner` run whose buyer is an LLM (E2, E2b, E2c, E3, E3b, E5, E8). Proposed = the buyer's orders to "
         "S_main (any identity); approved = EXECUTED; blocked = BLOCKED with the gate's reason code. Each blocked "
         "order's quantity is rerouted to S_backup by code; rerouted units are checked against each run's "
         "`metrics.rerouted_units`. Remediation orders after a FAILED claim are code's, not proposals, and are not "
         "counted. Backup orders the buyer placed itself are always approved (the backup is trusted).", "",
         f"**Headline.** {a['runs']} runs, {a['proposed']:,} S_main orders proposed, {a['blocked']:,} blocked "
         f"({_pct(a['blocked'], a['proposed'])}%), {a['runs_with_block']} runs with at least one block "
         f"({_pct(a['runs_with_block'], a['runs'])}%), {a['rerouted_units']:,} units rerouted. `obt`: "
         f"{plain['blocked']:,} of {plain['proposed']:,} blocked in {plain['runs_with_block']} of {plain['runs']} runs; "
         f"`obt+planner`: {planner['blocked']:,} of {planner['proposed']:,} blocked in {planner['runs_with_block']} of "
         f"{planner['runs']} runs" + _where(rs, "obt+planner") + ".",
         "", "## Reason codes (obt/gate.py, in the order the gate checks them)", ""]
    L += [f"- `{k}`: {v}" + ("" if k in t["_codes"] else " (not observed)") for k, v in REASONS.items()]
    L += ["", "## Per experiment", "", *md("gate_activity"), "", "## Per scenario (all experiments pooled)", "",
          *md("gate_activity_by_scenario"), "",
          "Per-run counts with their log lines: `results/gate_activity/runs.csv`.", ""]
    return "\n".join(L)


def _where(rs: list[dict], defense: str) -> str:
    """Where a defense's blocks happened: experiments and scenarios with blocks, and those with none."""
    sub = [r for r in rs if r["defense"] == defense]
    hit = Counter((r["experiment"], _scenario(r["scenario"])) for r in sub if r["blocked"])
    if not hit:
        return " (none)"
    exps = sorted({e for e, _ in hit})
    clean = sorted({r["experiment"] for r in sub} - set(exps))
    codes = Counter()
    for r in sub:
        codes.update(r["reasons"])
    return (" (all in " + ", ".join(f"{e} {sc}" for e, sc in sorted(hit)) + "; reasons "
            + ", ".join(f"{k} {v}" for k, v in codes.most_common()) + (f"; 0 in {', '.join(clean)}" if clean else "")
            + ")")


def runs_csv(t: dict) -> list[list]:
    codes = list(REASONS)
    rows = [["experiment", "log", "line", "scenario", "defense", "seed", "model", "proposed", "approved", "blocked",
             *codes, "rerouted_orders", "rerouted_units", "backup_own", "payments_blocked"]]
    rows += [[r["experiment"], r["log"], r["line"], _scenario(r["scenario"]), r["defense"], r["seed"], r["model"],
              r["proposed"], r["approved"], r["blocked"], *[r["reasons"].get(k, 0) for k in codes],
              r["rerouted_orders"], r["rerouted_units"], r["backup_own"], r["payments_blocked"]] for r in t["_runs"]]
    return rows
