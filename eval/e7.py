"""E7: budget growth multiplier k (DECISIONS D36). Scripted buyer, local, fast.

    python -m eval.e7            # runs/e7/summary.json

B(c) = b0 + k x max honored exposure, k ∈ {1, 2, 4}; OBT at the E1 default (b0 5%, W 0, δ 0) and `none` (the
utility reference) at 50 and 100 rounds; all 12 scenarios, seeds 1-3. In process with the rule extractor, like E6
(D29): exact on the grounding-filtered run bank, and in-process equals A2A (F11). The k = 1, 50-round runs must
reproduce E1's obt_b0.05_W0_d0 costs exactly (checked, reported). The per-event bound L_e (DESIGN §6) does not
depend on k; the budget-based a-priori bound does (through B(c) at the order), and both ratios are reported.
Any invariant violation or damage above the bound stops the run (STOP rule).
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from eval.stats import main_share
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import GameConfig
from obt.extractor import RuleExtractor
from obt.llm import RUNS
from obt.sim import Sim, SimConfig

DEFAULT_SIM = {"b0_frac": 0.05, "window": 0, "grace": 0}
OUT = RUNS / "e7"


class Violation(RuntimeError):
    pass


def _run(defense: str, k: int, rounds: int, n: int, seed: int) -> dict:
    g = GameConfig(rounds=rounds)
    sim = Sim(SimConfig(game=g, defense=defense, budget_k=k, **DEFAULT_SIM), seed, make_supplier(n, g, seed),
              ScriptedClaimBuyer(g), extractor=RuleExtractor())
    res = sim.run()
    lb = res.metrics["loss_bound"]
    r = {"defense": defense, "k": k, "rounds": rounds, "scenario": n, "seed": seed, "total_cost": res.total_cost,
         "main_share": main_share({"trace": res.trace}),
         "invariant_violations": res.metrics["invariant_violations"]["count"], "damage": lb["damage"],
         "sum_bound": lb["sum_bound"], "sum_apriori": round(sum(e["apriori"] for e in lb["events"]), 4),
         "events": len(lb["events"]), "bound_ok": lb["ok"]}
    if r["invariant_violations"] or r["bound_ok"] is False:
        raise Violation(f"STOP: {r}")
    return r


def run(out: Path = OUT, ks=(1, 2, 4), horizons=(50, 100), scenarios=tuple(range(1, 13)), seeds=(1, 2, 3)) -> dict:
    rows = []
    for T in horizons:
        rows += [_run("none", 1, T, n, s) for n in scenarios for s in seeds]
        rows += [_run("obt", k, T, n, s) for k in ks for n in scenarios for s in seeds]
    points: dict = {}
    for k in ks:
        for T in horizons:
            none = {(r["scenario"], r["seed"]): r["total_cost"] for r in rows if r["defense"] == "none"
                    and r["rounds"] == T}
            ob = [r for r in rows if r["defense"] == "obt" and r["k"] == k and r["rounds"] == T]
            cost = {(r["scenario"], r["seed"]): r["total_cost"] for r in ob}
            util = [cost[(1, s)] - none[(1, s)] for s in seeds if (1, s) in cost]
            ev = [r for r in ob if r["events"]]
            points.setdefault(str(k), {})[str(T)] = {
                "utility_cost": round(mean(util), 4),
                "utility_pct": 100 * mean(util) / mean(none[(1, s)] for s in seeds),
                "attack_loss": round(mean(cost[(n, s)] - cost[(1, s)] for (n, s) in cost if n != 1), 4),
                "main_share": round(mean(r["main_share"] for r in ob if r["scenario"] == 1), 4),
                "max_ratio": max((r["damage"] / r["sum_bound"] for r in ev), default=0.0),
                "max_ratio_apriori": max((r["damage"] / r["sum_apriori"] for r in ev), default=0.0),
                "failure_events": sum(r["events"] for r in ob),
                "invariant_violations": sum(r["invariant_violations"] for r in ob),
                "bound_ok": all(r["bound_ok"] is not False for r in ob)}
    out.mkdir(parents=True, exist_ok=True)
    summary = {"points": points, "ks": list(ks), "horizons": list(horizons), "seeds": list(seeds)}
    # Regression: k = 1 at 50 rounds must reproduce E1's OBT default run for run (different extractor path).
    e1 = RUNS / "e1" / "obt_b0.05_W0_d0" / "results.jsonl"
    if 1 in ks and 50 in horizons and e1.exists():
        logged = {(r["scenario"], r["seed"]): r["total_cost"] for r in map(json.loads, e1.read_text().splitlines())}
        mine = {(r["scenario"], r["seed"]): r["total_cost"] for r in rows
                if r["defense"] == "obt" and r["k"] == 1 and r["rounds"] == 50}
        same = [k for k in mine if k in logged and abs(mine[k] - logged[k]) < 1e-9]
        summary["k1_matches_e1"] = {"identical": len(same), "compared": len([k for k in mine if k in logged])}
    (out / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
