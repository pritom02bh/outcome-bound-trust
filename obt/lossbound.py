"""The loss bound (DESIGN §6, FIXES F7, DECISIONS D21).

damage(R) = cost(R) - cost(R*), where R* replays R with the same demand and the
same decisions (every executed order and payment, same round, same amounts)
but S_main keeps every promise the gate relied on: the units an order took from
DELIVERY claim k arrive at k's by_round, invoiced at the claimed price, and the
remediation orders R placed because a claim failed don't exist. Holding the
decisions fixed leaves out opportunity cost (backup purchases after blocks),
cool-down reroutes and LLM trajectory noise, which aren't damage from a broken
promise; `decompose` reports them separately, differenced against the honest run.

For every FAILED DELIVERY claim e (shortfall U_e, claimed price u_e, resolved at
t_e = by_round + delta):

    L_e = V_e + U_e*p_b*(delta + l_b + 1) + U_e*(p_bk - u_e) + late_e*h*(T - a_e + 1)

V_e = U_e*u_e is prepaid money committed to undelivered units. The last term is
the surplus when S_main delivers the shortfall after t_e, on top of the
backup replacement (D21). The check is damage <= sum_e L_e, for OBT runs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .env.beer_game import BACKUP, BeerGame, GameConfig, OrderRequest, Supplier, SupplierReply

if TYPE_CHECKING:
    from .sim import Sim

TOL = 1e-6
REROUTE_REASONS = ("OVER_BUDGET", "OVER_CLAIM")


@dataclass(frozen=True)
class FailureEvent:
    claim_id: str
    resolved_round: int
    shortfall: int                # U_e: consumed - allocated at resolution
    unit_price: float             # u_e: claimed price (the highest, if orders at several prices consumed it)
    late_units: int               # units from orders citing e that arrived after t_e, capped at U_e
    late_arrival: int | None      # earliest such arrival round
    B_at_order: float             # B(c) when the last order consuming e was decided

    @property
    def V(self) -> float:
        return self.shortfall * self.unit_price


def surplus_term(e: FailureEvent, g: GameConfig) -> float:
    # Holding is charged at the end of every round from the arrival round through round T.
    return e.late_units * g.holding_cost * (g.rounds - e.late_arrival + 1) if e.late_arrival else 0.0


def event_bound(e: FailureEvent, g: GameConfig, grace: int = 0) -> float:
    return (e.V + e.shortfall * g.backlog_cost * (grace + g.backup_lead + 1)
            + e.shortfall * (g.backup_price - e.unit_price) + surplus_term(e, g))


def apriori_bound(e: FailureEvent, g: GameConfig, grace: int = 0) -> float:
    """Budget form: U_e <= B(c)/u_e, late_e <= U_e and T - a_e + 1 <= T give L_e <= B(c)*(1 + K/u_e)."""
    k = g.backlog_cost * (grace + g.backup_lead + 1) + (g.backup_price - e.unit_price) + g.holding_cost * g.rounds
    return e.B_at_order * (1 + k / e.unit_price) if e.unit_price > 0 else float("inf")


def failure_events(sim: "Sim") -> list[FailureEvent]:
    receipts = sim.game.oracles.receipts()
    by_order: dict[str, list] = defaultdict(list)
    for r in receipts:
        by_order[r.order_id].append(r)
    snap_B = {s.action.action_id: float(s.B) for s in sim.gate.decisions if s.executed}
    out = []
    for c in sim.ledger:
        if c.template != "DELIVERY" or c.status != "FAILED":
            continue
        short = c.consumed - sim.verifier.allocated(c.claim_id)
        if short <= 0:
            continue
        consumers = [a for a in sim.actions.citing(c.claim_id)
                     if a.kind == "ORDER" and a.was_executed
                     and any(cid == c.claim_id for cid, _ in sim.gate.consumption.get(a.action_id, []))]
        # No consuming order only happens in a state the gate never produced (e.g. a monitor tamper test);
        # fall back to the claim's own exposure so metrics still report instead of crashing.
        price = max((float(a.unit_price) for a in consumers),
                    default=float(c.realized_exposure) / c.consumed if c.consumed else 0.0)
        late = [r for a in consumers for r in by_order.get(sim._order_of.get(a.action_id, ""), [])
                if r.round > c.resolved_round]
        late_units = min(short, sum(r.qty for r in late))
        out.append(FailureEvent(
            claim_id=c.claim_id, resolved_round=c.resolved_round, shortfall=short, unit_price=price,
            late_units=late_units, late_arrival=min((r.round for r in late), default=None) if late_units else None,
            B_at_order=max((snap_B.get(a.action_id, 0.0) for a in consumers), default=0.0)))
    return out


# ---------------------------------------------------------------- replay

class _ReplaySupplier(Supplier):
    """Ships and invoices exactly what the replay loop hands it for the next placement."""

    def __init__(self) -> None:
        self.next: tuple[float, tuple[tuple[int, int], ...]] | None = None

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        return None

    def on_order(self, req: OrderRequest) -> SupplierReply:
        price, ships = self.next
        self.next = None
        return SupplierReply(price, ships)


def kept_ships(claim_units: list[tuple[int, int]], actual_ships: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """R*'s arrivals for one order (D21a). `claim_units`: (units, by_round) the order consumed per claim.

    A promise "by round N" is kept by any delivery at or before N. Claims take actual arrivals earliest deadline
    first, earliest arrival first; a claim-backed unit arrives at min(actual arrival, by_round), and a missing unit
    at by_round. Units beyond the claims carry no promise and arrive as they actually did."""
    left = sorted(actual_ships, key=lambda s: s[1])
    out: list[tuple[int, int]] = []
    for units, by in sorted(claim_units, key=lambda c: c[1]):
        need = units
        while need and left:
            q, arr = left[0]
            take = min(q, need)
            out.append((take, min(arr, by)))
            need -= take
            left[0] = (q - take, arr)
            if left[0][0] == 0:
                left.pop(0)
        if need:
            out.append((need, by))
    return out + [s for s in left if s[0] > 0]


def _kept_main(sim: "Sim", p: dict, actual_ships: list[tuple[int, int]], actual_price: float):
    """S_main's delivery and invoice if it kept every promise this order relied on."""
    split = sim.gate.consumption.get(p["action_id"], [])
    a = sim.actions.get(p["action_id"])
    ships = kept_ships([(u, sim.ledger[cid].slots["by_round"]) for cid, u in split], actual_ships)
    prices = [k for k in a.cited_claims if (c := sim.ledger.get(k)) is not None and c.template == "PRICE"]
    price = float(a.unit_price) if len(prices) == 1 else actual_price
    return price, tuple(ships)


def replay_game(sim: "Sim", kept: bool) -> BeerGame:
    g = sim.cfg.game
    main, backup = _ReplaySupplier(), _ReplaySupplier()
    game = BeerGame(g, sim.seed, {**{i: main for i in sim.main_ids}, BACKUP: backup})
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
                nxt = _kept_main(sim, p, ships[p["order_id"]], actual_price)
            (main if p["supplier"] in sim.main_ids else backup).next = nxt
            oid[p["order_id"]] = game.place_order(p["supplier"], p["qty"], p["promised"]).order_id
        for p in pays[t]:
            if p["order_id"] in skipped:
                continue
            o = game.orders[oid[p["order_id"]]]
            # A kept promise is invoiced at the claimed price, so a baseline's overpayment can't be replayed.
            amount = min(p["amount"], o.invoice_total - o.paid) if kept else p["amount"]
            if amount > 0:
                game.pay_invoice(o.order_id, amount)
    return game


def replay_cost(sim: "Sim", kept: bool) -> float:
    return replay_game(sim, kept).total_cost


# ---------------------------------------------------------------- per-run summary

def loss_bound(sim: "Sim") -> dict:
    g, grace = sim.cfg.game, sim.cfg.grace
    reroute = round(sum(r["qty"] * (g.backup_price - float(r["blocked_unit_price"]))
                        for r in sim.reroutes if r["reason"] in REROUTE_REASONS), 6)
    if sim.cfg.defense != "obt":
        # Baselines never replace a missing unit, so "same decisions, promises kept" leaves R* with every
        # promised unit on top of whatever the buyer re-ordered: an overstock artifact, not damage (D21).
        return {"events": [], "sum_bound": None, "damage": None, "ok": None, "reroute_cost": reroute}
    damage = round(sim.game.total_cost - replay_cost(sim, kept=True), 6)
    events = []
    for e in failure_events(sim):
        events.append({"claim_id": e.claim_id, "resolved_round": e.resolved_round, "shortfall": e.shortfall,
                       "unit_price": e.unit_price, "V": e.V, "late_units": e.late_units,
                       "late_arrival": e.late_arrival, "B_at_order": e.B_at_order,
                       "surplus_term": surplus_term(e, g), "bound": event_bound(e, g, grace),
                       "apriori": apriori_bound(e, g, grace)})
    total = round(sum(e["bound"] for e in events), 6)
    return {"events": events, "sum_bound": total, "damage": damage, "ok": damage <= total + TOL,
            "reroute_cost": reroute}


def decompose(loss_from_lies: float | None, lb: dict, honest_lb: dict | None) -> dict:
    """loss_from_lies = damage + reroute_cost_diff + resid, every term differenced against the honest run
    (same defense, same seed). damage is already differenced by construction (0 for the honest run).
    reroute_cost_diff = reroute_cost(R) - reroute_cost(honest). resid is what's left: blocks for other
    reasons and trajectory differences; it is reported, not hidden. The honest run's absolute reroute_cost
    is the defense's reroute premium, reported separately."""
    diff = None if honest_lb is None else round(lb["reroute_cost"] - honest_lb["reroute_cost"], 6)
    if loss_from_lies is None or lb["damage"] is None or diff is None:
        return {"damage": lb["damage"], "reroute_cost_diff": diff, "resid": None}
    return {"damage": lb["damage"], "reroute_cost_diff": diff,
            "resid": round(loss_from_lies - lb["damage"] - diff, 6)}
