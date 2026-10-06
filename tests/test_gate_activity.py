"""D47: gate activity is counted from the trace, reroutes must match the metrics, and only LLM-buyer OBT runs count."""
import json

import pytest

from eval import gate_activity as ga


def _run(defense="obt", buyer="llm", blocked=((5, "OVER_BUDGET"),), rerouted=None, scenario=3, seed=1):
    trace = []
    for t in range(1, 4):
        acts = [["ORDER", "S_main", 2, 10.0, "EXECUTED", "OK", ["S_main#1.1"]], ["ORDER", "S_backup", 3, 18.0,
                                                                                "EXECUTED", "OK", []]]
        n = 0
        if t == 2:
            for q, why in blocked:
                acts.append(["ORDER", "S_main", q, 5.0 * q, "BLOCKED", why, ["S_main#2.1"]])
                acts.append(["ORDER", "S_backup", q, 6.0 * q, "EXECUTED", "OK", []])       # the code's reroute
                n += 1
        trace.append({"round": t, "actions": acts, "rerouted_orders": n})
    units = sum(q for q, _ in blocked)
    return {"scenario": scenario, "defense": defense, "seed": seed, "model": "m", "buyer": buyer, "trace": trace,
            "metrics": {"rerouted_units": units if rerouted is None else rerouted}}


def _write(root, recs, log="e2/results.jsonl"):
    f = root / "runs" / log
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def test_counts_per_run_and_totals(tmp_path):
    _write(tmp_path, [_run(), _run(seed=2, blocked=()), _run(defense="none"), _run(buyer="scripted", seed=3),
                      _run(defense="obt+planner", blocked=((4, "CLAIM_MISMATCH"), (1, "OVER_CLAIM")))])
    rs = ga.runs(tmp_path)
    assert [(r["defense"], r["seed"], r["proposed"], r["blocked"], r["rerouted_units"], r["backup_own"]) for r in rs] \
        == [("obt", 1, 4, 1, 5, 3), ("obt", 2, 3, 0, 0, 3), ("obt+planner", 1, 5, 2, 5, 3)]
    t = ga.tables(tmp_path)
    allrow = dict(zip(t["gate_activity"]["columns"], t["gate_activity"]["rows"][-1]))
    assert (allrow["runs"], allrow["runs with ≥1 block"], allrow["blocked"], allrow["OVER_BUDGET"],
            allrow["CLAIM_MISMATCH"], allrow["OVER_CLAIM"]) == (3, 2, 3, 1, 1, 1)
    assert "OVER_BUDGET" in ga.report_md(t)


def test_rerouted_units_must_match_the_metrics(tmp_path):
    _write(tmp_path, [_run(rerouted=4)])
    with pytest.raises(ValueError):
        ga.runs(tmp_path)


def test_unknown_reason_or_duplicate_run_refused(tmp_path):
    _write(tmp_path, [_run(blocked=((2, "SOMETHING_NEW"),))])
    with pytest.raises(ValueError):
        ga.tables(tmp_path)
    _write(tmp_path, [_run(), _run()])
    with pytest.raises(ValueError):
        ga.runs(tmp_path)
