"""Paper walkthrough (D46, D46a): one farm-then-lie run followed round by round, from existing logs only.

    python -m eval.results ...       # results/figdata/walkthrough{,_appendix}.json, results/walkthrough/rounds{,_appendix}.csv
    python -m eval.paper             # paper/figures/walkthrough{,_appendix}.{pdf,png}, paper/walkthrough{,_appendix}.md

Main run (D46a): an OBT farm-then-lie run where the gate blocked an order on the lie. `search` scans every OBT
farm-then-lie log; LLM-buyer experiments are preferred, else E1's scripted buyer at the chosen default config
(obt_b0.05_W0_d0), seed 1. Appendix (D46): E2, gpt-oss:20b buyer, seed 1, where no order was blocked.

Each defense's attack run (scenario 3) is read against its honest run (scenario 1, same defense, config and seed).
Every value carries its source: the log line holding the run record and the trace field (trace[round - 1].<field>)
or metrics key it came from.
"""
from __future__ import annotations

import json
from pathlib import Path

SCENARIO, HONEST = 3, 1
DEFENSES = ("obt", "none", "rep-default")
LLM_EXPERIMENTS = ("e2", "e2b", "e2c", "e3", "e3b", "e5")      # gpt-oss first (E2, E2b, E2c), then qwen3, then paid
# The two runs. Each defense maps to its log (relative to runs/) and the defense name recorded in that log.
APPENDIX = {"name": "E2, gpt-oss:20b buyer", "seed": 1,
            "logs": {d: ("e2/results.jsonl", d) for d in DEFENSES}}
E1_MAIN = {"name": "E1, scripted buyer, default config (b0 5%, W 0, δ 0)", "seed": 1,
           "logs": {"obt": ("e1/obt_b0.05_W0_d0/results.jsonl", "obt"), "none": ("e1/none/results.jsonl", "none"),
                    "rep-default": ("e1/rep_cap200_th0.8/results.jsonl", "reputation")}}


def _lies(r: dict) -> list[dict]:
    return [t for t in r["trace"] if (t.get("intent") or {}).get("truth") is False]


def _blocked_on_lie(r: dict) -> list[tuple[int, int, str]]:
    return [(t["round"], a[2], a[5]) for t in _lies(r) for a in t["actions"]
            if a[0] == "ORDER" and a[1] != "S_backup" and a[4] != "EXECUTED"]


def search(runs: Path) -> dict:
    """Every OBT farm-then-lie run in the logs, and those where the gate blocked an S_main order in a lie round."""
    out = {}
    for f in sorted(set(runs.glob("*/results.jsonl")) | set(runs.glob("*/*/results.jsonl"))):
        exp = f.relative_to(runs).parts[0]
        if exp.startswith("_"):
            continue                                        # invalid or archived runs
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("scenario") != SCENARIO or not str(r.get("defense", "")).startswith("obt") or "trace" not in r:
                continue
            k = f"{exp} ({r.get('buyer')} buyer, {r['defense']})"
            x = out.setdefault(k, {"experiment": exp, "buyer": r.get("buyer"), "runs": 0, "blocked_on_lie": []})
            x["runs"] += 1
            if _blocked_on_lie(r):
                x["blocked_on_lie"].append({"log": str(f.relative_to(runs.parent)), "line": i, "seed": r["seed"]})
    return out


def choose(found: dict) -> dict:
    """D46a rule: an LLM-buyer run if any qualifies (gpt-oss experiments first); else E1's default config, seed 1,
    if it qualifies. Returns the run spec, or raises if nothing qualifies."""
    for exp in LLM_EXPERIMENTS:
        hits = [h for x in found.values() if x["experiment"] == exp and x["buyer"] == "llm" for h in x["blocked_on_lie"]]
        if hits:
            raise NotImplementedError(f"an LLM-buyer run qualifies ({min(hits, key=lambda h: h['seed'])}); add its "
                                      "run spec before using it")
    e1 = [h for x in found.values() if x["experiment"] == "e1" for h in x["blocked_on_lie"]
          if h["log"].endswith("e1/obt_b0.05_W0_d0/results.jsonl") and h["seed"] == E1_MAIN["seed"]]
    if not e1:
        raise ValueError("no OBT farm-then-lie run with a blocked order on the lie qualifies")
    return E1_MAIN


def _records(runs: Path, spec: dict) -> dict:
    """defense -> {scenario: (log, 1-based line, record)} for the attack and honest runs of the spec's seed."""
    out = {}
    for d, (log, recorded) in spec["logs"].items():
        f = runs / log
        got = {}
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["defense"] == recorded and r["seed"] == spec["seed"] and r["scenario"] in (SCENARIO, HONEST):
                if r["scenario"] in got:
                    raise ValueError(f"{f}: two records for {d} scenario {r['scenario']} (lines {got[r['scenario']][1]}"
                                     f" and {i})")
                got[r["scenario"]] = (f"runs/{log}", i, r)
        if set(got) != {SCENARIO, HONEST}:
            raise ValueError(f"{f}: missing runs for {d}")
        out[d] = got
    return out


def _round(t: dict, h: dict) -> dict:
    claims = [{"id": cid, "type": tpl, "qty": s.get("qty"), "deadline": s.get("by_round"),
               "unit_price": s.get("unit_price"), "valid_until": s.get("valid_until")} for cid, tpl, s in t["offer"]]
    orders = [{"supplier": a[1], "qty": a[2], "value": a[3], "status": a[4], "reason": a[5], "cited": a[6]}
              for a in t["actions"] if a[0] == "ORDER"]
    remediation = [{"supplier": a[1], "qty": a[2], "value": a[3], "status": a[4]} for a in t.get("remediation", [])]
    blocked = [o for o in orders if o["supplier"] != "S_backup" and o["status"] != "EXECUTED"]
    n = t.get("rerouted_orders", 0)
    # The sim reroutes each blocked order's whole quantity to S_backup (obt/sim.py); the trace logs only the count.
    if n not in (0, len(blocked)):
        raise ValueError(f"round {t['round']}: {n} reroutes for {len(blocked)} blocked orders")
    return {"round": t["round"], "claims": claims, "resolved": [{"id": c, "status": s} for c, s in t["resolved"]],
            "B": t.get("B"), "P": t.get("P"), "orders": orders, "remediation": remediation, "rerouted_orders": n,
            "rerouted_qty": sum(o["qty"] for o in blocked) if n else 0, "arrived": t["arrived"], "cost": t["cost"],
            "intent": t.get("intent"), "honest_cost": h["cost"], "loss": round(t["cost"] - h["cost"], 6)}


def extract(runs: Path, spec: dict = APPENDIX) -> dict:
    recs = _records(runs, spec)
    out = {"run": spec["name"], "scenario": SCENARIO, "seed": spec["seed"],
           "log": recs["obt"][SCENARIO][0], "defenses": {}}
    for d, got in recs.items():
        (log, la, a), (_, lh, h) = got[SCENARIO], got[HONEST]
        if len(a["trace"]) != len(h["trace"]):
            raise ValueError(f"{d}: attack and honest traces differ in length")
        rounds = [_round(t, u) for t, u in zip(a["trace"], h["trace"])]
        if abs(rounds[-1]["loss"] - (a["total_cost"] - h["total_cost"])) > 1e-6:
            raise ValueError(f"{d}: per-round cost does not end at the run's total cost")
        if sum(r["rerouted_qty"] for r in rounds) != a["metrics"]["rerouted_units"]:
            raise ValueError(f"{d}: per-round rerouted quantity does not sum to metrics.rerouted_units")
        lb = a["metrics"]["loss_bound"]
        out["defenses"][d] = {
            "log": log, "line": la, "honest_line": lh, "git_commit": a["meta"]["git_commit"][:7],
            "model": a.get("model"), "buyer": a.get("buyer"), "total_cost": a["total_cost"],
            "honest_total_cost": h["total_cost"], "loss_from_lies": round(a["total_cost"] - h["total_cost"], 6),
            "damage": lb.get("damage"), "sum_bound": lb.get("sum_bound"), "events": lb.get("events", []),
            "reroute_cost": lb.get("reroute_cost"), "honest_reroute_cost": h["metrics"]["loss_bound"].get("reroute_cost"),
            "main_orders_blocked": a["metrics"]["main_orders_blocked"],
            "rerouted_units": a["metrics"]["rerouted_units"],
            "shortfall_rerouted_units": a["metrics"]["shortfall_rerouted_units"], "rounds": rounds}
    return out


def rounds_csv(w: dict) -> list[list]:
    """One row per (defense, round): the per-round extract the figure and the walkthrough read."""
    rows = [["defense", "round", "log", "log line", "claims (id type qty deadline price valid_until)", "resolved",
             "B", "P", "S_main orders (qty value status reason cited)", "backup orders", "remediation (backup)",
             "rerouted after block (orders)", "rerouted after block (units)", "arrived", "cost", "honest cost",
             "cumulative loss from lies"]]
    for d, x in w["defenses"].items():
        for r in x["rounds"]:
            main = [o for o in r["orders"] if o["supplier"] != "S_backup"]
            back = [o for o in r["orders"] if o["supplier"] == "S_backup"]
            rows.append([d, r["round"], x["log"], x["line"],
                         "; ".join(f"{c['id']} {c['type']} {c['qty']} {c['deadline']} {c['unit_price']} "
                                   f"{c['valid_until']}" for c in r["claims"]),
                         "; ".join(f"{c['id']} {c['status']}" for c in r["resolved"]), r["B"], r["P"],
                         "; ".join(f"{o['qty']} {o['value']} {o['status']} {o['reason']} {'+'.join(o['cited'])}"
                                   for o in main),
                         "; ".join(f"{o['qty']} {o['value']} {o['status']}" for o in back),
                         "; ".join(f"{o['qty']} {o['value']} {o['status']}" for o in r["remediation"]),
                         r["rerouted_orders"], r["rerouted_qty"],
                         "; ".join(f"{k} {v}" for k, v in sorted(r["arrived"].items())),
                         r["cost"], r["honest_cost"], r["loss"]])
    return rows


# ------------------------------------------------------------------ key events (read by eval.paper)

def _u(n: int) -> str:
    return f"{n} unit" + ("" if n == 1 else "s")


def _src(w: dict, d: str, rnd: int | None, field: str) -> str:
    x = w["defenses"][d]
    return f"`{x['log']}:{x['line']}` " + (f"trace[{rnd - 1}].{field}" if rnd else field)


def _split(o: dict) -> str:
    """OBT's loss from lies = damage + reroute premium (vs its honest run) + resid, from the logged reroute costs."""
    if o.get("reroute_cost") is None or o.get("honest_reroute_cost") is None or o.get("damage") is None:
        return ""
    rr = round(o["reroute_cost"] - o["honest_reroute_cost"], 6)
    resid = round(o["loss_from_lies"] - o["damage"] - rr, 6)
    m = lambda x: f"−${-x:.2f}" if x < 0 else f"${x:.2f}"   # noqa: E731
    return (f"; OBT's loss splits into damage {m(o['damage'])} + reroute premium {m(rr)} (vs its honest run) + "
            f"resid {m(resid)}")


def _main(r: dict) -> list[dict]:
    return [o for o in r["orders"] if o["supplier"] != "S_backup"]


def key_events(w: dict) -> list[dict]:
    """The walkthrough's events, found in the OBT run's rounds by rule (not by hand-picked round numbers)."""
    o = w["defenses"]["obt"]
    R = o["rounds"]
    ev = []
    first = next(r for r in R if r["claims"])
    c = next(x for x in first["claims"] if x["type"] == "DELIVERY")
    od = next(iter(_main(first)), None)
    ev.append({"round": first["round"], "event": "First claim",
               "what": f"{c['id']} DELIVERY {_u(c['qty'])} by round {c['deadline']}; "
                       + (f"the buyer orders {_u(od['qty'])} (${od['value']:.2f}) citing it; gate {od['status']} "
                          f"({od['reason']})" if od else "no S_main order")
                       + (f", {_u(first['rerouted_qty'])} rerouted to S_backup" if first["rerouted_qty"] else "")
                       + f"; B ${first['B']:.2f}, P ${first['P']:.2f}",
               "source": _src(w, "obt", first["round"], "offer, actions, rerouted_orders, B, P")})
    hon = next(r for r in R if any(x["status"] == "PASSED" for x in r["resolved"]))
    ev.append({"round": hon["round"], "event": "First honored claim",
               "what": f"{next(x['id'] for x in hon['resolved'] if x['status'] == 'PASSED')} PASSED "
                       f"(arrived from S_main: {hon['arrived'].get('S_main', 0)}); B steps "
                       f"${R[hon['round'] - 2]['B']:.2f} → ${hon['B']:.2f}",
               "source": _src(w, "obt", hon["round"], "resolved, arrived, B")})
    full = next((r for r in R if r["round"] > hon["round"] and r["P"] is not None and r["B"] and r["P"] >= r["B"]),
                None)
    if full:
        ev.append({"round": full["round"], "event": "Budget in use",
                   "what": f"committed exposure P reaches B (${full['P']:.2f} = ${full['B']:.2f})",
                   "source": _src(w, "obt", full["round"], "B, P")})
    lies = [r for r in R if r["intent"] and r["intent"].get("truth") is False]
    lie = lies[0]
    lie_ids = {x["id"] for r in lies for x in r["claims"]}
    lc = next(x for x in lie["claims"] if x["type"] == "DELIVERY")
    lp = next(x for x in lie["claims"] if x["type"] == "PRICE")
    span = f"rounds {lies[0]['round']}-{lies[-1]['round']}" if len(lies) > 1 else f"round {lie['round']}"
    # The gate's decision: the first S_main order citing a lie claim.
    dec = next(((r, x) for r in R for x in _main(r) if set(x["cited"]) & lie_ids), (None, None))
    others = {d: next(iter(_main(w["defenses"][d]["rounds"][lie["round"] - 1])), None)
              for d in ("none", "rep-default")}
    blocked_lie = [(r, x) for r in R for x in _main(r) if set(x["cited"]) & lie_ids and x["status"] != "EXECUTED"]
    largest = max((x["qty"] for r in R for x in _main(r)), default=0)
    others_txt = "; ".join(f"`{d}` orders {_u(x['qty'])} on it (${x['value']:.2f}, {x['reason']})"
                           for d, x in others.items() if x)
    lie_txt = (f"{lc['id']} DELIVERY {_u(lc['qty'])} by round {lc['deadline']} at ${lp['unit_price']:.2f} (the "
               f"farm-then-lie defection; the supplier lies in {span}). ")
    if dec[0] is not None and dec[0]["round"] == lie["round"]:
        r, x = dec
        ev.append({"round": lie["round"], "event": "The lie and the gate's decision",
                   "what": lie_txt + f"OBT's buyer orders {_u(x['qty'])} (${x['value']:.2f}); gate {x['status']} "
                           f"({x['reason']}): P ${r['P']:.2f} ≤ B ${r['B']:.2f}. {others_txt}. "
                           f"No OBT order on the lie exceeds the headroom: the largest S_main order in the run is "
                           f"{_u(largest)} and {o['main_orders_blocked']} orders are blocked.",
                   "source": _src(w, "obt", lie["round"], "offer, intent, actions, B, P") + "; "
                             + "; ".join(_src(w, d, lie["round"], "actions") for d in others)})
    else:
        own = next(iter(_main(lie)), None)
        ev.append({"round": lie["round"], "event": "The lie",
                   "what": lie_txt + ("OBT's buyer places no S_main order this round. " if own is None else
                                      f"OBT's buyer orders {_u(own['qty'])} ({own['status']}, {own['reason']}). ")
                           + others_txt + ".",
                   "source": _src(w, "obt", lie["round"], "offer, intent, actions") + "; "
                             + "; ".join(_src(w, d, lie["round"], "actions") for d in others)})
        if dec[0] is not None:
            r, x = dec
            ev.append({"round": r["round"], "event": "The gate's decision on the lie",
                       "what": f"OBT's buyer proposes {_u(x['qty'])} citing {'+'.join(x['cited'])} "
                               f"(${x['value']:.2f}); gate {x['status']} ({x['reason']}): ${x['value']:.2f} exceeds "
                               f"B ${r['B']:.2f} − P ${r['P']:.2f}; {_u(r['rerouted_qty'])} rerouted to S_backup. "
                               f"Over the lie, {len(blocked_lie)} S_main orders citing lie claims are blocked "
                               f"({_u(sum(x['qty'] for _, x in blocked_lie))} rerouted) and none executes.",
                       "source": _src(w, "obt", r["round"], "actions, rerouted_orders, B, P")
                                 + "".join(f"; {_src(w, 'obt', rr['round'], 'actions')}" for rr, _ in blocked_lie[1:])})
    res = next((r for r in R for x in r["resolved"] if x["id"] == lc["id"]), None)
    st = next(x["status"] for x in res["resolved"] if x["id"] == lc["id"]) if res else None
    if st == "FAILED":
        e = next(x for x in o["events"] if x["claim_id"] == lc["id"])
        rem = sum(x["qty"] for x in res["remediation"])
        ev.append({"round": res["round"], "event": "The broken claim",
                   "what": f"{lc['id']} FAILED (shortfall {_u(e['shortfall'])}); B drops "
                           f"${R[res['round'] - 2]['B']:.2f} → ${res['B']:.2f}; {_u(rem)} re-ordered from backup; "
                           f"per-event bound L_e = ${e['bound']:.2f} (B at order ${e['B_at_order']:.2f})",
                   "source": _src(w, "obt", res["round"], "resolved, B, remediation") + "; "
                             + _src(w, "obt", None, f"metrics.loss_bound.events[{lc['id']}]")})
        back = next((r for r in R[res["round"]:] if r["B"] > res["B"]), None)
        if back:
            ev.append({"round": back["round"], "event": "Budget step back",
                       "what": f"{next(x['id'] for x in back['resolved'] if x['status'] == 'PASSED')} PASSED; B "
                               f"${res['B']:.2f} → ${back['B']:.2f}",
                       "source": _src(w, "obt", back["round"], "resolved, B")})
    elif st == "LAPSED":
        lapsed = [r["round"] for r in R for x in r["resolved"] if x["id"] in lie_ids and x["id"].endswith(".1")
                  and x["status"] == "LAPSED"]
        ev.append({"round": res["round"], "event": "The lie's claims lapse",
                   "what": f"{lc['id']} LAPSED: no executed order relied on it, so it costs nothing beyond the "
                           f"reroutes and B is unchanged (${res['B']:.2f}). All {len(lapsed)} lie DELIVERY claims "
                           f"lapse (resolved in rounds {lapsed[0]}-{lapsed[-1]}); failure events: {len(o['events'])}.",
                   "source": "; ".join(_src(w, "obt", rr, "resolved") for rr in lapsed) + "; "
                             + _src(w, "obt", None, "metrics.loss_bound.events")})
    last = R[-1]
    same = w["defenses"]["none"]["rounds"] == w["defenses"]["rep-default"]["rounds"]
    ev.append({"round": last["round"], "event": "Final loss vs bound",
               "what": "loss from lies " + ", ".join(f"`{d}` ${x['loss_from_lies']:.2f}"
                                                     for d, x in w["defenses"].items())
                       + (" (`rep-default` never blocks here, so its run is identical to `none`)" if same else "")
                       + f"; OBT damage ${o['damage']:.2f} ≤ Σ L_e ${o['sum_bound']:.2f}"
                       + _split(o),
               "source": "; ".join(f"`{x['log']}:{x['line']}` − `{x['log']}:{x['honest_line']}` "
                                   f"trace[{last['round'] - 1}].cost" for d, x in w["defenses"].items())
                         + "; " + _src(w, "obt", None, "metrics.loss_bound.damage, sum_bound, reroute_cost")
                         + f"; `{o['log']}:{o['honest_line']}` metrics.loss_bound.reroute_cost"})
    return ev
