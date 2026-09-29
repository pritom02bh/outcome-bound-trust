"""D33: reputation lock-out fix. Probation length n0 x theta x cap, scripted buyer (user request).

    python -m eval.rep_grid           # runs/rep_grid/<point>/, then runs/rep_grid/summary.json

Grid: n0 ∈ {3, 8, 18}, θ ∈ {0.8, 0.85, 0.9}, cap ∈ {$100, $200, $400}; all 12 scenarios, seeds 1-3, 50 rounds,
scripted buyer, gpt-oss extractor from the persistent cache (every grid message is already cached), A2A. The
utility reference is E1's `none` (same scripted config).

Lock-out: after n0 completed orders and no failure the score is (n0+1)/(n0+2); if that is below θ, an honest
supplier is blocked for good once probation ends and can never earn more completions. A point "locks" if any
honest-scenario run was blocked for REP_SCORE (checked in the runs, and against the analytic rule).

Choice (D22 rule): among non-degenerate points (neither locked nor never trading with an honest supplier, D33), reputation's Pareto front in (utility cost, attack loss); pick the
front point whose utility cost is nearest OBT+planner's. The scripted counterpart of OBT+planner is the scripted
OBT default (the scripted buyer plans exactly like the D32 planner), so the reference is E1's
obt_b0.05_W0_d0 utility cost.
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.e1 import pareto_front, run_point
from eval.run import load_results
from obt.llm import RUNS

N0 = (3, 8, 18)
THETAS = (0.8, 0.85, 0.9)
CAPS = (100.0, 200.0, 400.0)
ROOT = RUNS / "rep_grid"


def grid() -> list[tuple[str, dict]]:
    return [(f"rep_n{n0}_th{t}_cap{int(c)}", {"rep_n0": n0, "rep_theta": t, "rep_cap": c})
            for n0 in N0 for t in THETAS for c in CAPS]


def locks_out(n0: int, theta: float) -> bool:
    return (n0 + 1) / (n0 + 2) < theta - 1e-12


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def choose(points: dict, reference_utility: float) -> tuple[list[str], str | None]:
    # Degenerate points are excluded: locked ones (an honest supplier blocked for REP_SCORE) and, correcting the D22
    # rule's intent (D33), ones that never trade with an honest supplier at all.
    ok = {k: (v["utility_cost"], v["attack_loss"]) for k, v in points.items()
          if not v["locked"] and not v.get("never_trades") and v["utility_cost"] is not None
          and v["attack_loss"] is not None}
    front = pareto_front(ok) if ok else []
    pick = min(front, key=lambda k: (abs(ok[k][0] - reference_utility), ok[k][1], k)) if front else None
    return front, pick


def summarize(root: Path = ROOT, none_dir: Path = RUNS / "e1" / "none", reference_utility: float | None = None,
              read=load_results) -> dict:
    none = {(r["scenario"], r["seed"]): r["total_cost"] for r in read(none_dir)}
    if reference_utility is None:
        obt = {(r["scenario"], r["seed"]): r["total_cost"] for r in read(RUNS / "e1" / "obt_b0.05_W0_d0")}
        reference_utility = _mean([obt[(1, s)] - none[(1, s)] for (n, s) in obt if n == 1 and (1, s) in none])
    points = {}
    for name, sim in grid():
        d = root / name
        if not (d / "results.jsonl").exists():
            continue
        rs = read(d)
        cost = {(r["scenario"], r["seed"]): r["total_cost"] for r in rs}
        seeds = sorted({s for _, s in cost})
        honest = [r for r in rs if r["scenario"] == 1]
        points[name] = {
            **sim, "runs": len(rs),
            "attack_loss": _mean([cost[(n, s)] - cost[(1, s)] for (n, s) in cost if n != 1 and (1, s) in cost]),
            "utility_cost": _mean([cost[(1, s)] - none[(1, s)] for s in seeds if (1, s) in cost and (1, s) in none]),
            "rep_score_blocks_honest": sum(r["metrics"]["blocked_by_reason"].get("REP_SCORE", 0) for r in honest),
            "analytic_lock": locks_out(sim["rep_n0"], sim["rep_theta"]),
            "invariant_violations": sum(r["metrics"]["invariant_violations"]["count"] for r in rs),
        }
        points[name]["locked"] = points[name]["rep_score_blocks_honest"] > 0
        points[name]["never_trades"] = bool(honest) and all(r["metrics"]["main_orders_executed"] == 0
                                                            for r in honest)
    front, pick = choose(points, reference_utility)
    return {"points": points, "front": front, "pick": pick, "reference_utility": reference_utility,
            "analytic_matches_runs": all(p["locked"] == p["analytic_lock"] for p in points.values())}


def main() -> None:
    for i, (name, sim) in enumerate(grid(), 1):
        print(f"== rep grid {i}/27: {name}", flush=True)
        run_point(ROOT, name, "reputation", sim)            # raises on any invariant violation (STOP)
    s = summarize()
    (ROOT / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({k: s[k] for k in ("front", "pick", "reference_utility", "analytic_matches_runs")}, indent=1))


if __name__ == "__main__":
    main()
