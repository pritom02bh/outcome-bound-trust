"""E2b support (D30): the E1 scripted-buyer overlay for the trust-over-time figure.

    python -m eval.e2b redrive      # no model calls; writes runs/e2b/e1_scripted.jsonl

E1's logs predate the per-round reputation score in the trace, and the results builder never simulates. So the
E1 scripted runs used for the overlay (honest scenario, seeds 1-3, the OBT default and rep_cap200_th0.9) are
re-driven exactly as in eval/recheck_d21a.py: extraction only from the persistent cache (a miss is refused and
counted) and each rerun must reproduce its logged total cost.
"""
from __future__ import annotations

import json
import sys

from eval.recheck_d21a import CacheOnly
from eval.run import load_results
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import GameConfig
from obt.extractor import ExtractionCache, LLMExtractor, model_digest
from obt.llm import LLM, RUNS
from obt.sim import Sim, SimConfig

POINTS = {"obt": ("obt_b0.05_W0_d0", "obt"), "rep-strict": ("rep_cap200_th0.9", "reputation")}


def redrive(model: str = "gpt-oss:20b") -> list[dict]:
    cache = ExtractionCache(RUNS / "cache" / "extract", model, model_digest(model))
    stub = CacheOnly()
    out = []
    for label, (point, defense) in POINTS.items():
        for r in load_results(RUNS / "e1" / point):
            if r["scenario"] != 1:
                continue
            g = GameConfig(rounds=r["rounds"])
            sim = Sim(SimConfig(game=g, defense=defense, transport="inproc", **r["meta"]["sim"]), r["seed"],
                      make_supplier(1, g, r["seed"]), ScriptedClaimBuyer(g),
                      extractor=LLMExtractor(LLM("fake", model, fake=stub, log_path=RUNS / "recheck_llm.jsonl"),
                                             cache))
            res = sim.run()
            if abs(res.total_cost - r["total_cost"]) > 1e-9 or stub.misses:
                raise RuntimeError(f"re-drive of {point} s{r['seed']} diverged (misses {stub.misses})")
            out.append({"scenario": 1, "defense": label, "seed": r["seed"], "total_cost": res.total_cost,
                        "trace": res.trace, "e1_point": point})
    (RUNS / "e2b").mkdir(parents=True, exist_ok=True)
    (RUNS / "e2b" / "e1_scripted.jsonl").write_text("".join(json.dumps(x) + "\n" for x in out))
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["redrive"]:
        print(f"{len(redrive())} E1 scripted runs re-driven (cache only, costs reproduced)")
