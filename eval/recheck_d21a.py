"""D21a recheck: recompute damage and the bound check for every logged run with the fixed counterfactual.

    python -m eval.recheck_d21a         # writes runs/recheck_d21a.json

E1 (scripted buyer): every run is re-driven exactly, in process, with extraction served only from the persistent
cache: the model stub refuses any uncached call and counts it, so a miss can't silently become UNTESTABLE. A rerun
must reproduce the logged total cost; then damage, Σ bound and the bound check are recomputed and compared.

E2 (LLM buyer): the buyer's replies weren't logged verbatim, so its runs can't be re-driven without model calls.
The fix changes damage only where a claim-backed unit arrived before its claim's by_round. Every scripted
supplier ships a lot at the order round + lead or later, and an order at round t can only cite claims made at or
before t, whose by_round is (creation round + lead) <= t + lead. So each OBT run is checked from its trace: every
executed S_main ORDER must cite only DELIVERY claims with by_round <= order round + lead. If that holds, no
claim-backed unit could arrive early and the run's damage is provably unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.run import base_defense, load_results
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import GameConfig
from obt.extractor import ExtractionCache, LLMExtractor, model_digest
from obt.llm import LLM, RUNS
from obt.sim import Sim, SimConfig


class CacheOnly:
    """Stand-in LLM for cached extraction: any real call is a miss, recorded and refused."""

    def __init__(self) -> None:
        self.misses = 0

    def __call__(self, system, user):
        self.misses += 1
        raise RuntimeError("uncached extraction during recheck")


def recheck_e1(root: Path = RUNS / "e1", model: str = "gpt-oss:20b") -> dict:
    cache = ExtractionCache(RUNS / "cache" / "extract", model, model_digest(model))
    stub = CacheOnly()
    changed, cost_mismatch, ok_changed, n, n_obt = [], [], [], 0, 0
    for d in sorted(p for p in root.iterdir() if (p / "results.jsonl").exists()):
        for r in load_results(d):
            g = GameConfig(rounds=r["rounds"])
            sim = Sim(SimConfig(game=g, defense=base_defense(r["defense"]), transport="inproc", **r["meta"]["sim"]),
                      r["seed"], make_supplier(r["scenario"], g, r["seed"]), ScriptedClaimBuyer(g),
                      extractor=LLMExtractor(LLM("fake", model, fake=stub, log_path=RUNS / "recheck_llm.jsonl"),
                                             cache))
            res = sim.run()
            n += 1
            key = (d.name, r["scenario"], r["seed"])
            if abs(res.total_cost - r["total_cost"]) > 1e-9:
                cost_mismatch.append({"run": key, "logged": r["total_cost"], "rerun": res.total_cost})
                continue
            if r["defense"] != "obt":
                continue
            n_obt += 1
            old, new = r["metrics"]["loss_bound"], res.metrics["loss_bound"]
            if (old["damage"], old["sum_bound"]) != (new["damage"], new["sum_bound"]):
                changed.append({"run": key, "old": [old["damage"], old["sum_bound"]],
                                "new": [new["damage"], new["sum_bound"]]})
            if old["ok"] != new["ok"]:
                ok_changed.append({"run": key, "old": old["ok"], "new": new["ok"]})
    return {"runs": n, "obt_runs": n_obt, "cache_misses": stub.misses, "cost_mismatches": cost_mismatch,
            "damage_or_bound_changed": changed, "bound_ok_changed": ok_changed}


def check_e2_trace(root: Path = RUNS / "e2", lead: int = GameConfig().main_lead) -> dict:
    rows = [r for r in load_results(root) if r["defense"] == "obt"]
    early_possible = []
    for r in rows:
        by = {}
        for t in r["trace"]:
            for cid, template, slots in t["offer"]:
                if template == "DELIVERY":
                    by[cid] = slots["by_round"]
        for t in r["trace"]:
            for kind, cp, _qty, _v, status, _reason, cites in t["actions"]:
                if kind == "ORDER" and cp.startswith("S_main") and status == "EXECUTED":
                    bad = [c for c in cites if c in by and by[c] > t["round"] + lead]
                    if bad:
                        early_possible.append({"run": (r["scenario"], r["seed"]), "round": t["round"], "claims": bad})
    return {"obt_runs": len(rows), "runs_where_early_delivery_was_possible": early_possible}


def main() -> None:
    out = {"e1": recheck_e1(), "e2": check_e2_trace()}
    (RUNS / "recheck_d21a.json").write_text(json.dumps(out, indent=1) + "\n")
    e1, e2 = out["e1"], out["e2"]
    print(f"E1: {e1['runs']} runs re-driven ({e1['obt_runs']} OBT), cache misses {e1['cache_misses']}, cost "
          f"mismatches {len(e1['cost_mismatches'])}, damage/bound changed {len(e1['damage_or_bound_changed'])}, "
          f"bound_ok changed {len(e1['bound_ok_changed'])}")
    print(f"E2: {e2['obt_runs']} OBT runs checked from traces; runs where early delivery was possible: "
          f"{len(e2['runs_where_early_delivery_was_possible'])}")


if __name__ == "__main__":
    main()
