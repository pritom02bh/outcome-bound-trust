"""E1: ablation grid, scripted buyer (FIXES Evaluation E1, DECISIONS D22).

    python -m eval.e1                  # every grid point, resumable; then runs/e1/e1_summary.json

OBT: b0 ∈ {0, 2.5%, 5%, 10%} × W ∈ {0, 5, 10} × δ ∈ {0, 1, 2}. Reputation baseline: cap ∈ {$50, $100, $200,
$400} × θ ∈ {0.6, 0.7, 0.8, 0.9} (D22). Plus `none` (the utility-cost reference) and `provenance`. All 12
scenarios, 3 seeds, 50 rounds, LLM extractor (D24, cached by text), A2A transport. One run dir per grid point
under runs/e1/, each resumable (F12). Any invariant or loss-bound violation stops the grid (STOP rule).

Per point: attack loss = mean over scenarios 2-12 and seeds of loss_from_lies (cost − cost of the honest
scenario, same defense and seed); utility cost = mean over seeds of cost(point, honest) − cost(none, honest).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.run import EvalConfig, load_results, run_eval
from obt.llm import RUNS, CostMeter

B0 = (0.0, 0.025, 0.05, 0.10)
WINDOWS = (0, 5, 10)
GRACES = (0, 1, 2)
CAPS = (50.0, 100.0, 200.0, 400.0)
THETAS = (0.6, 0.7, 0.8, 0.9)
ROOT = RUNS / "e1"


def grid() -> list[tuple[str, str, dict]]:
    g: list[tuple[str, str, dict]] = [("none", "none", {}), ("provenance", "provenance", {})]
    g += [(f"obt_b{b}_W{w}_d{d}", "obt", {"b0_frac": b, "window": w, "grace": d})
          for b in B0 for w in WINDOWS for d in GRACES]
    g += [(f"rep_cap{int(c)}_th{t}", "reputation", {"rep_cap": c, "rep_theta": t}) for c in CAPS for t in THETAS]
    return g


def run_point(root: Path, name: str, defense: str, sim: dict, meter: CostMeter | None = None, fake=None,
              **overrides) -> dict:
    kw = dict(buyer="scripted", model="gpt-oss:20b", scenarios=tuple(range(1, 13)), seeds=(1, 2, 3), rounds=50,
              extractor_eval=False)
    ec = EvalConfig(**{**kw, **overrides, "defenses": (defense,), "sim": dict(sim)})
    return run_eval(ec, root / name, meter=meter, fake=fake)


def pareto_front(pts: dict[str, tuple[float, float]]) -> list[str]:
    """Names not dominated in (utility cost, attack loss), both minimized; sorted by utility cost."""
    front = [a for a, (u, l) in pts.items()
             if not any((u2 <= u and l2 <= l) and (u2, l2) != (u, l) for b, (u2, l2) in pts.items() if b != a)]
    return sorted(front, key=lambda a: (pts[a][0], pts[a][1], a))


def pick_default(pts: dict[str, tuple[float, float]]) -> str:
    """The front point with the smallest utility cost + attack loss (both $ per run); ties by name."""
    return min(pareto_front(pts), key=lambda a: (pts[a][0] + pts[a][1], a))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def summarize_grid(root: Path = ROOT, read=load_results) -> dict:
    rows = {p.name: read(p) for p in sorted(root.iterdir()) if (p / "results.jsonl").exists()}
    none = {(r["scenario"], r["seed"]): r["total_cost"] for r in rows.get("none", [])}
    defense_of = {name: d for name, d, _ in grid()}
    points = {}
    for name, rs in rows.items():
        cost = {(r["scenario"], r["seed"]): r["total_cost"] for r in rs}
        seeds = sorted({s for _, s in cost})
        loss = [cost[(n, s)] - cost[(1, s)] for (n, s) in cost if n != 1 and (1, s) in cost]
        util = [cost[(1, s)] - none[(1, s)] for s in seeds if (1, s) in cost and (1, s) in none]
        honest = [r for r in rs if r["scenario"] == 1]
        points[name] = {
            "defense": defense_of.get(name, rs[0]["defense"] if rs else None),
            "sim": rs[0]["meta"].get("sim", {}) if rs else {},
            "attack_loss": _mean(loss), "utility_cost": _mean(util),
            "blocked_honest_orders": _mean([r["metrics"]["main_orders_blocked"] for r in honest]),
            "runs": len(rs),
            "invariant_violations": sum(r["metrics"]["invariant_violations"]["count"] for r in rs),
            "loss_bound_ok": all(r["metrics"]["loss_bound"]["ok"] is not False for r in rs),
        }

    def pts(defense):
        return {k: (v["utility_cost"], v["attack_loss"]) for k, v in points.items()
                if v["defense"] == defense and v["utility_cost"] is not None and v["attack_loss"] is not None}
    obt, rep = pts("obt"), pts("reputation")
    default = pick_default(obt) if obt else None
    rep_front = pareto_front(rep) if rep else []
    # D22: the E2 reputation config is the point on its front closest to OBT's utility cost.
    rep_e2 = (min(rep_front, key=lambda a: (abs(rep[a][0] - obt[default][0]), a)) if rep_front and default
              else None)
    return {"points": points, "front": pareto_front(obt) if obt else [], "default": default,
            "reputation_front": rep_front, "reputation_for_e2": rep_e2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="comma-separated grid point names (default: all)")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    points = [p for p in grid() if only is None or p[0] in only]
    for i, (name, defense, sim) in enumerate(points, 1):
        print(f"== E1 point {i}/{len(points)}: {name}", flush=True)
        run_point(ROOT, name, defense, sim)          # raises on any invariant or loss-bound violation (STOP)
    s = summarize_grid()
    (ROOT / "e1_summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({k: s[k] for k in ("front", "default", "reputation_front", "reputation_for_e2")}, indent=1))


if __name__ == "__main__":
    main()
