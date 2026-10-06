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
