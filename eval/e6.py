"""E6: adaptive attacker search against OBT (user request; DECISIONS D29).

    python -m eval.e6                 # fixed budget and seeds; writes runs/e6/e6.json

Maximizes damage / Σ bound, the share of OBT's per-failure-event loss bound (DESIGN §6) an attacker realizes,
over the 12-parameter attacker in obt/attacks/adaptive.py. Scripted buyer, OBT at the E1 default (b0 5%, W 0,
δ 0), 50 rounds. An attacker's score is its worst seed. Search: uniform random sampling, then hill-climbing
restarts from the best points found (Gaussian steps in the unit cube, step shrinks after failures), all driven by
one seeded RNG with a fixed evaluation budget. Any run whose damage exceeds its bound (ratio > 1), or that breaks
a runtime invariant, is a STOP: the search raises at once.
"""
from __future__ import annotations

import argparse
import json
import random
import time

from obt.agent import ScriptedClaimBuyer
from obt.attacks.adaptive import BOUNDS, AdaptiveAttacker, Params
from obt.env.beer_game import GameConfig
from obt.extractor import RuleExtractor
from obt.llm import RUNS
from obt.sim import Sim, SimConfig

G = GameConfig()
SEEDS = (1, 2, 3)
DEFAULT_SIM = {"b0_frac": 0.05, "window": 0, "grace": 0}      # the E1 default (D27)
OUT = RUNS / "e6"


class BoundViolation(RuntimeError):
    """damage > Σ bound in some run (or a runtime invariant broke). STOP rule."""


def run_one(params: Params, seed: int, sim_kw: dict | None = None) -> dict:
    sim = Sim(SimConfig(game=G, defense="obt", **(sim_kw or DEFAULT_SIM)), seed, AdaptiveAttacker(G, seed, params),
              ScriptedClaimBuyer(G), extractor=RuleExtractor())
    res = sim.run()
    lb = res.metrics["loss_bound"]
    ratio = lb["damage"] / lb["sum_bound"] if lb["sum_bound"] else 0.0
    return {"seed": seed, "ratio": ratio, "damage": lb["damage"], "sum_bound": lb["sum_bound"],
            "events": len(lb["events"]), "bound_ok": lb["ok"],
            "invariant_violations": res.metrics["invariant_violations"]["count"], "total_cost": res.total_cost}


def evaluate(params: Params, seeds=SEEDS, sim_kw: dict | None = None) -> dict:
    per = [run_one(params, s, sim_kw) for s in seeds]
    worst = max(per, key=lambda r: (r["ratio"], r["damage"]))
    return {"ratio": worst["ratio"], "mean_ratio": sum(r["ratio"] for r in per) / len(per),
            "damage": worst["damage"], "sum_bound": worst["sum_bound"], "per_seed": per}


def _check(params: Params, r: dict) -> None:
    bad = [x for x in r["per_seed"] if x.get("invariant_violations") or x.get("bound_ok") is False]
    if r["ratio"] > 1 or bad:
        raise BoundViolation(f"STOP: ratio {r['ratio']:.4f} (damage {r['damage']} vs bound {r['sum_bound']}) "
                             f"for {params.as_dict()}; per seed {r['per_seed']}")


def search(budget: int = 10_000, n_random: int = 2_000, seeds=SEEDS, rng_seed: int = 20260928, restarts: int = 4,
           sigma0: float = 0.15, log=None) -> dict:
    rng = random.Random(rng_seed)
    history: list[dict] = []

    def ev(p: Params) -> dict:
        r = evaluate(p, seeds)
        _check(p, r)
        rec = {"params": p.as_dict(), "ratio": r["ratio"], "mean_ratio": r["mean_ratio"], "damage": r["damage"],
               "sum_bound": r["sum_bound"]}
        history.append(rec)
        if log and len(history) % 100 == 0:
            best = max(history, key=lambda h: (h["ratio"], h["damage"]))
            log(f"{len(history)}/{budget} evaluations, best ratio {best['ratio']:.4f}")
        return rec

    dim = len(BOUNDS)
    for _ in range(min(n_random, budget)):
        ev(Params.from_unit([rng.random() for _ in range(dim)]))
    # Hill-climbing restarts from the best distinct points so far; each gets an equal share of what's left.
    starts = []
    for h in sorted(history, key=lambda h: (-h["ratio"], -h["damage"])):
        if h["params"] not in [s["params"] for s in starts]:
            starts.append(h)
        if len(starts) == restarts:
            break
    left = budget - len(history)
    for i, start in enumerate(starts):
        share = left // len(starts) + (1 if i < left % len(starts) else 0)
        cur, sigma = start, sigma0
        for _ in range(share):
            u = Params(**cur["params"]).to_unit()
            cand = ev(Params.from_unit([x + rng.gauss(0, sigma) for x in u]))
            if (cand["ratio"], cand["damage"]) > (cur["ratio"], cur["damage"]):
                cur, sigma = cand, sigma0
            else:
                sigma = max(0.02, sigma * 0.97)
    best = max(history, key=lambda h: (h["ratio"], h["damage"]))
    top_damage = max(history, key=lambda h: (h["damage"], h["ratio"]))
    return {"evaluations": len(history), "best": best, "max_damage": top_damage, "history": history,
            "budget": budget, "n_random": n_random, "seeds": list(seeds), "rng_seed": rng_seed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=10_000)
    ap.add_argument("--random", type=int, default=2_000)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    out = search(a.budget, a.random, log=lambda m: print(m, flush=True))
    best = Params(**out["best"]["params"])
    # Robustness of the best attacker: more seeds, and the E1 alternatives around the default.
    out["best_on_seeds_1_10"] = evaluate(best, tuple(range(1, 11)))
    out["best_under_variants"] = {name: evaluate(best, SEEDS, kw) for name, kw in {
        "b0.05_W10_d0": {"b0_frac": 0.05, "window": 10, "grace": 0},
        "b0.05_W0_d1": {"b0_frac": 0.05, "window": 0, "grace": 1},
        "b0.1_W0_d0": {"b0_frac": 0.10, "window": 0, "grace": 0}}.items()}
    for r in [out["best_on_seeds_1_10"], *out["best_under_variants"].values()]:
        _check(best, r)
    out["wall_s"] = round(time.time() - t0, 1)
    (OUT / "e6.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("evaluations", "best", "max_damage", "wall_s")}, indent=1))


if __name__ == "__main__":
    main()
