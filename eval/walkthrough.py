"""Paper walkthrough (D46): one E2 run followed round by round, from existing logs only (no new runs).

    python -m eval.results ...       # writes results/figdata/walkthrough.json and results/walkthrough/rounds.csv
    python -m eval.paper             # draws paper/figures/walkthrough.{pdf,png} and writes paper/walkthrough.md

Farm-then-lie (scenario 3), seed 1, gpt-oss:20b buyer (E2): defenses obt, none and rep-default, each against its
honest run (scenario 1, same defense and seed). Every value carries its source: the line of runs/e2/results.jsonl
holding the run record, and the trace field (trace[round - 1].<field>) or metrics key it was read from.
"""
from __future__ import annotations

import json
from pathlib import Path

SCENARIO, HONEST, SEED = 3, 1, 1
DEFENSES = ("obt", "none", "rep-default")
LOG = "runs/e2/results.jsonl"


def _records(path: Path) -> dict:
    """(scenario, defense, seed) -> (1-based line number, record), for the runs the walkthrough needs."""
    want = {(n, d, SEED) for n in (SCENARIO, HONEST) for d in DEFENSES}
    out = {}
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        k = (r["scenario"], r["defense"], r["seed"])
        if k in want:
            if k in out:
                raise ValueError(f"{path}: two records for {k} (lines {out[k][0]} and {i})")
            out[k] = (i, r)
    missing = want - set(out)
    if missing:
        raise ValueError(f"{path}: missing runs {sorted(missing)}")
    return out


def _round(t: dict, h: dict) -> dict:
    claims = [{"id": cid, "type": tpl, "qty": s.get("qty"), "deadline": s.get("by_round"),
               "unit_price": s.get("unit_price"), "valid_until": s.get("valid_until")} for cid, tpl, s in t["offer"]]
    orders = [{"supplier": a[1], "qty": a[2], "value": a[3], "status": a[4], "reason": a[5], "cited": a[6]}
              for a in t["actions"] if a[0] == "ORDER"]
    remediation = [{"supplier": a[1], "qty": a[2], "value": a[3], "status": a[4]} for a in t.get("remediation", [])]
    return {"round": t["round"], "claims": claims, "resolved": [{"id": c, "status": s} for c, s in t["resolved"]],
            "B": t.get("B"), "P": t.get("P"), "orders": orders, "remediation": remediation,
            "rerouted_orders": t.get("rerouted_orders", 0), "arrived": t["arrived"], "cost": t["cost"],
            "intent": t.get("intent"),
            "honest_cost": h["cost"], "loss": round(t["cost"] - h["cost"], 6)}


def extract(runs: Path) -> dict:
    recs = _records(runs / "e2" / "results.jsonl")
    out = {"scenario": SCENARIO, "seed": SEED, "log": LOG, "defenses": {}}
    for d in DEFENSES:
        (la, a), (lh, h) = recs[(SCENARIO, d, SEED)], recs[(HONEST, d, SEED)]
        if len(a["trace"]) != len(h["trace"]):
            raise ValueError(f"{d}: attack and honest traces differ in length")
        rounds = [_round(t, u) for t, u in zip(a["trace"], h["trace"])]
        if abs(rounds[-1]["loss"] - (a["total_cost"] - h["total_cost"])) > 1e-6:
            raise ValueError(f"{d}: per-round cost does not end at the run's total cost")
        lb = a["metrics"]["loss_bound"]
        out["defenses"][d] = {
            "line": la, "honest_line": lh, "git_commit": a["meta"]["git_commit"][:7], "model": a.get("model"),
            "total_cost": a["total_cost"], "honest_total_cost": h["total_cost"],
            "loss_from_lies": round(a["total_cost"] - h["total_cost"], 6),
            "damage": lb.get("damage"), "sum_bound": lb.get("sum_bound"), "events": lb.get("events", []),
            "main_orders_blocked": a["metrics"]["main_orders_blocked"],
            "rerouted_units": a["metrics"]["rerouted_units"],
            "shortfall_rerouted_units": a["metrics"]["shortfall_rerouted_units"], "rounds": rounds}
    return out


def rounds_csv(w: dict) -> list[list]:
    """One row per (defense, round): the per-round extract the figure and the walkthrough read."""
    rows = [["defense", "round", "log line", "claims (id type qty deadline price valid_until)", "resolved",
             "B", "P", "S_main orders (qty value status reason cited)", "backup orders", "remediation (backup)",
             "rerouted after block (orders)", "arrived", "cost", "honest cost", "cumulative loss from lies"]]
    for d, x in w["defenses"].items():
        for r in x["rounds"]:
            main = [o for o in r["orders"] if o["supplier"] != "S_backup"]
            back = [o for o in r["orders"] if o["supplier"] == "S_backup"]
            rows.append([d, r["round"], x["line"],
                         "; ".join(f"{c['id']} {c['type']} {c['qty']} {c['deadline']} {c['unit_price']} "
                                   f"{c['valid_until']}" for c in r["claims"]),
                         "; ".join(f"{c['id']} {c['status']}" for c in r["resolved"]), r["B"], r["P"],
                         "; ".join(f"{o['qty']} {o['value']} {o['status']} {o['reason']} {'+'.join(o['cited'])}"
                                   for o in main),
                         "; ".join(f"{o['qty']} {o['value']} {o['status']}" for o in back),
                         "; ".join(f"{o['qty']} {o['value']} {o['status']}" for o in r["remediation"]),
                         r["rerouted_orders"], "; ".join(f"{k} {v}" for k, v in sorted(r["arrived"].items())),
                         r["cost"], r["honest_cost"], r["loss"]])
    return rows


# ------------------------------------------------------------------ key events (read by eval.paper)

def _u(n: int) -> str:
    return f"{n} unit" + ("" if n == 1 else "s")


def _src(w: dict, d: str, rnd: int | None, field: str) -> str:
    x = w["defenses"][d]
    return f"`{w['log']}:{x['line']}` " + (f"trace[{rnd - 1}].{field}" if rnd else field)


def key_events(w: dict) -> list[dict]:
    """The walkthrough's events, found in the OBT run's rounds by rule (not by hand-picked round numbers)."""
    o = w["defenses"]["obt"]
    R = o["rounds"]
    ev = []
    first = next(r for r in R if r["claims"])
    c = next(x for x in first["claims"] if x["type"] == "DELIVERY")
    od = next(x for x in first["orders"] if x["supplier"] != "S_backup")
    ev.append({"round": first["round"], "event": "First claim",
               "what": f"{c['id']} DELIVERY {_u(c['qty'])} by round {c['deadline']}; the buyer orders {_u(od['qty'])} "
                       f"(${od['value']:.2f}) citing it; gate {od['status']} ({od['reason']}); B ${first['B']:.2f}, "
                       f"P ${first['P']:.2f}",
               "source": _src(w, "obt", first["round"], "offer, actions, B, P")})
    hon = next(r for r in R if any(x["status"] == "PASSED" for x in r["resolved"]))
    ev.append({"round": hon["round"], "event": "First honored claim",
               "what": f"{next(x['id'] for x in hon['resolved'] if x['status'] == 'PASSED')} PASSED "
                       f"(arrived from S_main: {hon['arrived'].get('S_main', 0)}); B steps "
                       f"${R[hon['round'] - 2]['B']:.2f} → ${hon['B']:.2f}",
               "source": _src(w, "obt", hon["round"], "resolved, arrived, B")})
    full = next(r for r in R if r["P"] is not None and r["B"] and r["P"] >= r["B"] and r["round"] > hon["round"])
    ev.append({"round": full["round"], "event": "Budget in use",
               "what": f"committed exposure P reaches B (${full['P']:.2f} = ${full['B']:.2f}); each later S_main order "
                       f"is sized within the headroom",
               "source": _src(w, "obt", full["round"], "B, P")})
    lie = next(r for r in R if r["intent"] and r["intent"].get("truth") is False)     # the scenario's own label
    lc = next(x for x in lie["claims"] if x["type"] == "DELIVERY")
    lp = next(x for x in lie["claims"] if x["type"] == "PRICE")
    lo = next(x for x in lie["orders"] if x["supplier"] != "S_backup")
    big = {d: next((x for x in w["defenses"][d]["rounds"][lie["round"] - 1]["orders"] if x["supplier"] != "S_backup"),
                   None) for d in ("none", "rep-default")}
    largest = max(x["qty"] for r in R for x in r["orders"] if x["supplier"] != "S_backup")
    ev.append({"round": lie["round"], "event": "The lie and the gate's decision",
               "what": f"{lc['id']} DELIVERY {_u(lc['qty'])} by round {lc['deadline']} at ${lp['unit_price']:.2f} "
                       f"(the farm-then-lie defection). OBT's buyer orders {_u(lo['qty'])} (${lo['value']:.2f}); "
                       f"gate {lo['status']} ({lo['reason']}): P ${lie['P']:.2f} ≤ B ${lie['B']:.2f}. "
                       + "; ".join(f"`{d}` orders {_u(x['qty'])} (${x['value']:.2f}, {x['reason']})"
                                   for d, x in big.items() if x)
                       + f". No OBT order in the run exceeds the headroom: the largest S_main order is "
                         f"{_u(largest)} and {o['main_orders_blocked']} orders are blocked, so the gate never clips.",
               "source": _src(w, "obt", lie["round"], "offer, intent, actions, B, P") + "; "
                         + "; ".join(_src(w, d, lie["round"], "actions") for d in big)})
    fail = next(r for r in R if any(x["status"] == "FAILED" and x["id"] == lc["id"] for x in r["resolved"]))
    e = next(x for x in o["events"] if x["claim_id"] == lc["id"])
    rem = sum(x["qty"] for x in fail["remediation"])
    ev.append({"round": fail["round"], "event": "The broken claim",
               "what": f"{lc['id']} FAILED (shortfall {_u(e['shortfall'])}); B drops ${R[fail['round'] - 2]['B']:.2f} "
                       f"→ ${fail['B']:.2f}; {_u(rem)} re-ordered from backup; per-event bound L_e = "
                       f"${e['bound']:.2f} (B at order ${e['B_at_order']:.2f})",
               "source": _src(w, "obt", fail["round"], "resolved, B, remediation") + "; "
                         + _src(w, "obt", None, f"metrics.loss_bound.events[{lc['id']}]")})
    back = next(r for r in R[fail["round"]:] if r["B"] > fail["B"])
    ev.append({"round": back["round"], "event": "Budget step back",
               "what": f"{next(x['id'] for x in back['resolved'] if x['status'] == 'PASSED')} PASSED; B "
                       f"${fail['B']:.2f} → ${back['B']:.2f}",
               "source": _src(w, "obt", back["round"], "resolved, B")})
    last = R[-1]
    ev.append({"round": last["round"], "event": "Final loss vs bound",
               "what": "loss from lies " + ", ".join(f"`{d}` ${x['loss_from_lies']:.2f}"
                                                     for d, x in w["defenses"].items())
                       + f"; OBT damage ${o['damage']:.2f} ≤ Σ L_e ${o['sum_bound']:.2f}",
               "source": "; ".join(f"`{w['log']}:{x['line']}` − `{w['log']}:{x['honest_line']}` "
                                   f"trace[{last['round'] - 1}].cost" for d, x in w["defenses"].items())
                         + "; " + _src(w, "obt", None, "metrics.loss_bound.damage, sum_bound")})
    return ev
