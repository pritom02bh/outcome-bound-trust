"""E9 loss bound (docs/E9_PLAN.md §4, DECISIONS D44): damage counterfactual and per-event bounds, cloud domain.

damage(R) = cost(R) - cost(R*), where R* replays R with the same workload and the same decisions (every executed
order and payment, same round, same amounts) while the provider keeps every promise the gate relied on:
  - QUOTA (DELIVERY over "capacity"): the units an order took from claim e are provisioned at e's by_round, at
    the claimed price, and R's remediation orders don't exist (as the Beer Game, lossbound.kept_ships);
  - SLA: for each relied-on SLA claim e that FAILED, the k_e = ceil(a_e n_e) - m_e down rounds of its window with
    the largest workload (ties: earliest) are restored, for the units of the orders that cited e only. Restoring
    the provider as a whole would also bring back capacity no order relied on for that promise.

Per FAILED QUOTA claim e (shortfall U_e, claimed price u_e per unit-term, resolved at t_e = by_round + delta):
    L_e = V_e + U_e * p_od * (delta + l_b + 1) + U_e * (u_b - u_e),   V_e = U_e * u_e
Per FAILED SLA claim e (window n_e rounds, promised a_e, up rounds m_e, relied-on units C_e = consumed):
    L_e = k_e * C_e * p_od
Capacity is perishable with no holding cost, so late provisioning only lowers cost: there is no late-surplus term.
The check is damage <= sum_e L_e for OBT runs (the STOP rule).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

from ..lossbound import REROUTE_REASONS, TOL, _ReplaySupplier, kept_ships
from .beer_game import BACKUP
from .cloud import ON_DEMAND, CloudGame

if TYPE_CHECKING:
    from ..sim import Sim


def _consumers(sim: "Sim", cid: str) -> list:
    return [a for a in sim.actions.citing(cid) if a.kind == "ORDER" and a.was_executed]


def _up_log(sim: "Sim"):
    o = sim.game.oracles
    return lambda t, s: bool(o.uptime(s, t, t)[0])


def sla_restored(sim: "Sim", c) -> list[int]:
    """The k_e rounds R* restores for FAILED SLA claim c: its window's down rounds with the largest workload."""
    s = c.slots
    n = s["end"] - s["start"] + 1
    up = _up_log(sim)
    down = [t for t in range(s["start"], min(s["end"], sim.game.round) + 1) if not up(t, c.counterparty)]
    m = n - len(down) - max(0, s["end"] - sim.game.round)      # rounds past the game's end were never up
    k = max(0, math.ceil(s["min_availability"] * n) - m)
    return sorted(down, key=lambda t: (-sim.game.demand[t - 1], t))[:k]


def events(sim: "Sim") -> list[dict]:
    g, grace = sim.cfg.game, sim.cfg.grace
    snap_B = {x.action.action_id: float(x.B) for x in sim.gate.decisions if x.executed}
    out = []
    for c in sim.ledger:
        if c.status != "FAILED":
            continue
        cons = _consumers(sim, c.claim_id)
        B = max((snap_B.get(a.action_id, 0.0) for a in cons), default=0.0)
        if c.template == "DELIVERY":
            short = c.consumed - sim.verifier.allocated(c.claim_id)
            if short <= 0:
                continue
            u = max((float(a.unit_price) for a in cons), default=float(c.realized_exposure) / c.consumed)
            bound = short * u + short * ON_DEMAND * (grace + g.backup_lead + 1) + short * (g.backup_price - u)
            apriori = B * (1 + (ON_DEMAND * (grace + g.backup_lead + 1) + (g.backup_price - u)) / u)
            out.append({"claim_id": c.claim_id, "template": "QUOTA", "resolved_round": c.resolved_round,
                        "shortfall": short, "unit_price": u, "V": short * u, "B_at_order": B,
                        "bound": bound, "apriori": apriori})
        elif c.template == "SLA" and c.consumed > 0:
            k = len(sla_restored(sim, c))
            u = max((float(a.unit_price) for a in cons), default=g.main_price)
            bound = k * c.consumed * ON_DEMAND
            n = c.slots["end"] - c.slots["start"] + 1
            out.append({"claim_id": c.claim_id, "template": "SLA", "resolved_round": c.resolved_round,
                        "excess_down_rounds": k, "relied_units": c.consumed, "B_at_order": B,
                        "bound": bound, "apriori": B * n * ON_DEMAND / u})
    return out


def replay_game(sim: "Sim", kept: bool) -> CloudGame:
    g = sim.cfg.game
    main, backup = _ReplaySupplier(), _ReplaySupplier()
    override: set[tuple[str, int]] = set()
    restore: dict[str, list[int]] = {}
    if kept:
        for c in sim.ledger:
            if c.template == "SLA" and c.status == "FAILED" and c.consumed > 0:
                rounds = sla_restored(sim, c)
                for a in _consumers(sim, c.claim_id):
                    restore.setdefault(a.action_id, []).extend(rounds)
    game = CloudGame(g, sim.seed, {**{i: main for i in sim.main_ids}, BACKUP: backup}, uptime=_up_log(sim))
    ships: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for r in sim.game.oracles.receipts():
        ships[r.order_id].append((r.qty, r.round))
    places, pays = defaultdict(list), defaultdict(list)
    for p in sim.placements:
        places[p["round"]].append(p)
    for p in sim.payments_made:
        pays[p["round"]].append(p)
    oid, skipped = {}, set()
    for t in range(1, sim.game.round + 1):
        game.begin_round()
        for p in places[t]:
            if kept and p["remediation"]:
                skipped.add(p["order_id"])
                continue
            actual_price = sim.game.orders[p["order_id"]].unit_price
            nxt = (actual_price, tuple(ships[p["order_id"]]))
            if kept and p["supplier"] in sim.main_ids:
                split = sim.gate.consumption.get(p["action_id"], [])
                a = sim.actions.get(p["action_id"])
                kept_s = kept_ships([(u, sim.ledger[cid].slots["by_round"]) for cid, u in split], ships[p["order_id"]])
                prices = [k for k in a.cited_claims if (c := sim.ledger.get(k)) is not None and c.template == "PRICE"]
                nxt = (float(a.unit_price) if len(prices) == 1 else actual_price, tuple(kept_s))
            (main if p["supplier"] in sim.main_ids else backup).next = nxt
            new = game.place_order(p["supplier"], p["qty"], p["promised"]).order_id
            oid[p["order_id"]] = new
            for r in restore.get(p["action_id"], []):
                game.up_override.add((new, r))
        for p in pays[t]:
            if p["order_id"] in skipped:
                continue
            o = game.orders[oid[p["order_id"]]]
            amount = min(p["amount"], o.invoice_total - o.paid) if kept else p["amount"]
            if amount > 0:
                game.pay_invoice(o.order_id, amount)
    return game


def replay_cost(sim: "Sim", kept: bool) -> float:
    return replay_game(sim, kept).total_cost


def loss_bound(sim: "Sim") -> dict:
    g = sim.cfg.game
    reroute = round(sum(r["qty"] * (g.backup_price - float(r["blocked_unit_price"]))
                        for r in sim.reroutes if r["reason"] in REROUTE_REASONS), 6)
    if sim.cfg.defense != "obt":
        return {"events": [], "sum_bound": None, "damage": None, "ok": None, "reroute_cost": reroute}
    damage = round(sim.game.total_cost - replay_cost(sim, kept=True), 6)
    ev = events(sim)
    total = round(sum(e["bound"] for e in ev), 6)
    return {"events": ev, "sum_bound": total, "damage": damage, "ok": damage <= total + TOL, "reroute_cost": reroute}
