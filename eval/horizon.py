"""Horizon check (DECISIONS D35): is OBT's utility cost mostly cold start?

    python -m eval.horizon            # runs/horizon/t100/<point>/, then runs/horizon/summary.json

Scripted buyer, gpt-oss extractor (cache; new rounds' messages are extracted locally), A2A, all 12 scenarios,
seeds 1-3, at 100 rounds: `none` (the utility reference), the OBT default (b0 5%, W 0, δ 0) and the chosen
reputation config (n0 18, θ 0.9, cap $200). The 50-round numbers are E1's and the D33 grid's runs of the same
configs. If OBT's cost is mostly the cold start (trust not yet earned), its utility cost as a % of the honest run's
total cost should fall as the horizon doubles. Any invariant or loss-bound violation stops the run (STOP rule).
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from eval.e1 import run_point
from eval.run import load_results
from obt.llm import RUNS

POINTS = (("none", "none", {}), ("obt", "obt", {"b0_frac": 0.05, "window": 0, "grace": 0}),
          ("rep-n18", "reputation", {"rep_n0": 18, "rep_theta": 0.9, "rep_cap": 200.0}))
ROOT = RUNS / "horizon"
T50 = {"none": RUNS / "e1" / "none", "obt": RUNS / "e1" / "obt_b0.05_W0_d0",
       "rep-n18": RUNS / "rep_grid" / "rep_n18_th0.9_cap200"}


def run(root: Path = ROOT / "t100", rounds: int = 100, meter=None, fake=None, rounds_override: int | None = None,
        **overrides) -> None:
    for name, d, sim in POINTS:
        run_point(root, name, d, sim, meter=meter, fake=fake, rounds=rounds_override or rounds, **overrides)


def _summ(dirs: dict[str, Path]) -> dict:
    none = {(r["scenario"], r["seed"]): r["total_cost"] for r in load_results(dirs["none"])}
    out = {}
    for name in ("obt", "rep-n18"):
        cost = {(r["scenario"], r["seed"]): r["total_cost"] for r in load_results(dirs[name])}
        seeds = sorted({s for n, s in cost if n == 1 and (1, s) in none})
        uc = [cost[(1, s)] - none[(1, s)] for s in seeds]
        base = [none[(1, s)] for s in seeds]
        out[name] = {"utility_cost": round(mean(uc), 4), "honest_cost_none": round(mean(base), 4),
                     "utility_pct": 100 * mean(uc) / mean(base),
                     "attack_loss": round(mean(cost[(n, s)] - cost[(1, s)] for (n, s) in cost
                                               if n != 1 and (1, s) in cost), 4),
                     "seeds": seeds}
    return out


def summarize(roots: dict[int, Path] | None = None) -> dict:
    """roots: horizon -> a directory holding one run dir per point (default: E1/D33 runs at 50, ROOT/t100 at 100)."""
    if roots is None:
        dirs = {50: T50, 100: {n: ROOT / "t100" / n for n, _, _ in POINTS}}
    else:
        dirs = {T: {n: root / n for n, _, _ in POINTS} for T, root in roots.items()}
    per = {T: _summ(d) for T, d in dirs.items()}
    return {"defenses": {name: {str(T): per[T][name] for T in sorted(per)} for name in ("obt", "rep-n18")},
            "note": "utility_pct = utility cost / total cost of the honest run without a defense (same seed)"}


def main() -> None:
    run()
    s = summarize()
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
