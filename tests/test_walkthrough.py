"""D46: the paper walkthrough reads run records only, keeps their log lines, and finds its events by rule."""
import json

import pytest

from eval import walkthrough as wt


def _trace(n, lie_round=None, B=10.0):
    out = []
    for t in range(1, n + 1):
        lie = t == lie_round
        claims = [[f"S_main#{t}.1", "DELIVERY", {"item": "widget", "qty": 4 if lie else 2, "by_round": t + 2}],
                  [f"S_main#{t}.2", "PRICE", {"item": "widget", "unit_price": 4.25 if lie else 5.0,
                                              "valid_until": t + 2}]]
        res = []
        if t > 2:
            st = "FAILED" if lie_round and t - 2 == lie_round else "PASSED"
            res = [[f"S_main#{t - 2}.1", st], [f"S_main#{t - 2}.2", st]]
        b = 5.0 if t < 3 or (lie_round and t == lie_round + 2) else B
        out.append({"round": t, "offer": claims, "resolved": res, "B": b, "P": b, "arrived": {"S_main": 1},
                    "actions": [["ORDER", "S_main", 1, 5.0, "EXECUTED", "OK", [f"S_main#{t}.1"]]],
                    "remediation": [], "rerouted_orders": 0, "cost": 10.0 * t + (3 if lie_round and t > lie_round
                                                                                    else 0),
                    "intent": {"kind": "deal" if lie else "offer", "truth": not lie}})
    return out


def _rec(n, d, trace, cost):
    return {"scenario": n, "defense": d, "seed": 1, "model": "m", "total_cost": cost, "trace": trace,
            "meta": {"git_commit": "abcdef0"},
            "metrics": {"loss_bound": {"damage": 1.0, "sum_bound": 14.0,
                                       "events": [{"claim_id": "S_main#5.1", "resolved_round": 7, "shortfall": 1,
                                                   "bound": 14.0, "B_at_order": 10.0}] if n == 3 else []},
                        "main_orders_blocked": 0, "rerouted_units": 0, "shortfall_rerouted_units": 1}}


def test_extract_keeps_log_lines_and_finds_the_events(tmp_path):
    (tmp_path / "e2").mkdir()
    lines = [json.dumps(_rec(9, "obt", _trace(10), 0))]                       # unrelated record
    for d in wt.DEFENSES:
        lines += [json.dumps(_rec(1, d, _trace(10), 100.0)), json.dumps(_rec(3, d, _trace(10, 5), 103.0))]
    (tmp_path / "e2" / "results.jsonl").write_text("\n".join(lines) + "\n")
    w = wt.extract(tmp_path)
    assert (w["defenses"]["obt"]["honest_line"], w["defenses"]["obt"]["line"]) == (2, 3)
    assert w["defenses"]["obt"]["loss_from_lies"] == 3.0 and w["defenses"]["obt"]["rounds"][-1]["loss"] == 3.0
    ev = {e["event"]: e for e in wt.key_events(w)}
    assert ev["The lie and the gate's decision"]["round"] == 5 and ev["The broken claim"]["round"] == 7
    assert ev["First honored claim"]["round"] == 3 and "results.jsonl:3" in ev["The broken claim"]["source"]
    assert len(wt.rounds_csv(w)) == 1 + 3 * 10


def test_extract_refuses_duplicate_or_missing_runs(tmp_path):
    (tmp_path / "e2").mkdir()
    r = json.dumps(_rec(1, "obt", _trace(3), 30.0))
    (tmp_path / "e2" / "results.jsonl").write_text(r + "\n" + r + "\n")
    with pytest.raises(ValueError):
        wt.extract(tmp_path)


def _write_log(path, recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


def _blocked(trace, rnd):
    t = trace[rnd - 1]
    t["actions"] = [["ORDER", "S_main", 20, 85.0, "BLOCKED", "OVER_BUDGET", [f"S_main#{rnd}.1"]]]
    t["rerouted_orders"] = 1
    return trace


def test_choose_prefers_llm_buyer_runs_then_the_e1_default(tmp_path):
    runs = tmp_path / "runs"
    e1 = _rec(3, "obt", _blocked(_trace(10, 5), 5), 0)
    _write_log(runs / "e1" / "obt_b0.05_W0_d0" / "results.jsonl", [e1])
    _write_log(runs / "e2" / "results.jsonl", [{**_rec(3, "obt", _trace(10, 5), 0), "buyer": "llm"}])
    found = wt.search(runs)
    assert found["e1 (None buyer, obt)"]["blocked_on_lie"][0]["seed"] == 1
    assert wt.choose(found) is wt.E1_MAIN                          # no LLM-buyer run blocked on the lie
    _write_log(runs / "e2" / "results.jsonl", [{**_rec(3, "obt", _blocked(_trace(10, 5), 5), 0), "buyer": "llm"}])
    with pytest.raises(NotImplementedError):
        wt.choose(wt.search(runs))                                 # an LLM-buyer run would be preferred
    with pytest.raises(ValueError):
        wt.choose({})


def test_reroutes_must_match_blocked_orders(tmp_path):
    tr = _trace(4)
    tr[1]["rerouted_orders"] = 1                                   # a reroute with no blocked order
    with pytest.raises(ValueError):
        wt._round(tr[1], tr[1])


def test_glance_counts_the_data_files(tmp_path):
    from pathlib import Path

    from eval import glance
    root = Path(__file__).resolve().parent.parent
    for d in ("data", "annotation"):
        (tmp_path / d).symlink_to(root / d)
    t = glance.table(tmp_path)                                    # no runs/: only the simulation and data rows
    rows = {r[1]: r for r in t["rows"]}
    assert not [r for r in t["rows"] if r[0] == "runs"]
    assert rows["extractor dataset"][2].startswith("dev 49 (prompt tuning), test 199 (incl. 29 injection), hard "
                                                   "subset 30")
    assert rows["Enron real text"][2].startswith("100 sentences") and "50 rows (40 v2 + 10 seeded" in \
        rows["independent annotation"][2]
    assert all(r[3] for r in t["rows"])                            # every row names its source
