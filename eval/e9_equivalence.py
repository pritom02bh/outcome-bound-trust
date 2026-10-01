"""E9 condition (D44): the supply domain is unchanged by the E9 code. Run it under two code versions and compare.

    PYTHONPATH=<code root> python eval/e9_equivalence.py dump <out.json> <extraction cache dir>
    python eval/e9_equivalence.py compare <old.json> <new.json> <report.json>

`dump` uses only APIs that exist in both v1.4.1-results and the E9 code, and records, under whatever code is on
PYTHONPATH:
  - E1's default scripted runs (OBT b0 5%, W 0, delta 0; all 12 scenarios; seed 1; A2A; the frozen gpt-oss:20b
    extractor served from the shared extraction cache): every claim in the ledger, the cost breakdown, and every
    action with its verdict (status and reason), as canonical JSON;
  - the gate differential test (tests/test_conformance.py, derandomized, 10,000 examples): every generated action
    with the gate's and the monitor's verdict.
`compare` reports, per scenario and for the differential set, whether the two dumps are byte-identical (sha256).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _sha(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()


def e1_default(cache: Path, log: Path) -> dict:
    from obt.agent import ScriptedClaimBuyer
    from obt.attacks.suppliers import make_supplier, scenario_name
    from obt.env.beer_game import GameConfig
    from obt.extractor import ExtractionCache, LLMExtractor, model_digest
    from obt.llm import LLM
    from obt.sim import Sim, SimConfig
    m = "gpt-oss:20b"
    out = {}
    for n in range(1, 13):
        cfg = SimConfig(game=GameConfig(rounds=50), b0_frac=0.05, window=0, grace=0, defense="obt", transport="a2a")
        llm = LLM("ollama", m, log_path=log)
        ext = LLMExtractor(llm, ExtractionCache(cache, m, model_digest(m)))
        sim = Sim(cfg, 1, make_supplier(n, cfg.game, 1), ScriptedClaimBuyer(cfg.game), extractor=ext,
                  scenario=scenario_name(n))
        res = sim.run()
        ledger = sorted((c.model_dump(mode="json") for c in sim.ledger), key=lambda c: c["claim_id"])
        verdicts = [{"id": a.action_id, "kind": a.kind, "cp": a.counterparty, "qty": a.qty, "value": str(a.value),
                     "unit_price": str(a.unit_price), "status": a.status, "reason": a.reason,
                     "cited": list(a.cited_claims), "round": a.round} for a in sim.actions]
        costs = {"total": res.total_cost, **{k: round(v, 6) for k, v in res.costs.items()}}
        rec = {"ledger": ledger, "costs": costs, "verdicts": verdicts}
        out[scenario_name(n)] = {**{k: _sha(v) for k, v in rec.items()}, "total_cost": res.total_cost,
                                 "uncached_llm_calls": llm.calls - llm.by_purpose.get("extract", {}).get("cache_hits", 0)}
    return out


def gate_differential(n: int = 10_000) -> dict:
    from hypothesis import given, settings

    import tests.test_conformance as tc
    rows = []

    @settings(max_examples=n, **tc._SETTINGS)
    @given(tc.world_and_action())
    def collect(case):
        gate, a, now = case
        ok, why = gate.allow(a, now)
        mok, mwhy = tc.table_verdict(tc.snapshot(gate, a, now))
        rows.append([a.model_dump(mode="json"), now, ok, why, mok, mwhy])
    collect()
    return {"examples": len(rows), "sha256": _sha(rows), "disagreements": sum(r[2:4] != r[4:6] for r in rows)}


def main(argv: list[str]) -> None:
    if argv[0] == "dump":
        out, cache = Path(argv[1]), Path(argv[2])
        rep = {"e1_default": e1_default(cache, out.with_suffix(".llm_calls.jsonl")), "gate_differential": gate_differential()}
        out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"scenarios": len(rep["e1_default"]), "differential": rep["gate_differential"]}))
        return
    old, new = (json.loads(Path(p).read_text()) for p in argv[1:3])
    per = {s: {k: old["e1_default"][s][k] == new["e1_default"][s][k] for k in ("ledger", "costs", "verdicts")}
           for s in old["e1_default"]}
    rep = {"e1_default": per, "e1_identical": all(all(v.values()) for v in per.values()),
           "uncached_llm_calls": {"old": sum(v["uncached_llm_calls"] for v in old["e1_default"].values()),
                                  "new": sum(v["uncached_llm_calls"] for v in new["e1_default"].values())},
           "gate_differential": {"old": old["gate_differential"], "new": new["gate_differential"],
                                 "identical": old["gate_differential"] == new["gate_differential"]}}
    rep["identical"] = rep["e1_identical"] and rep["gate_differential"]["identical"]
    Path(argv[3]).write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"identical": rep["identical"], "e1_identical": rep["e1_identical"],
                      "differential_identical": rep["gate_differential"]["identical"],
                      "uncached_llm_calls": rep["uncached_llm_calls"]}))
    if not rep["identical"]:
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
