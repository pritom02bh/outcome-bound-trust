"""Order planner (DECISIONS D32): code, not the LLM, sizes and cites the S_main order.

The LLM buyer states only how many units it wants this round in total. The planner decides how much of that goes
to S_main, sized so that trust can grow under the defense's own rule, and sends the rest to S_backup. It chooses
among orders the buyer could always have proposed, and every order still passes the gate unchanged (the TLA+
model's buyer already proposes any order with any citations, so no spec change is needed; DESIGN §7).

OBT: B(c) grows to b0 + the value of the largest single order delivered in full, so the planner "pulses" like the
scripted buyer (D10): it orders from S_main only when nothing is pending (P = $0), sized to
min(desired, headroom / claimed price, offer capacity), citing the offer's DELIVERY claims and its one PRICE claim,
and asks for a next lot that fits the budget.

Reputation: the score grows with each completed order, whatever its size, so the equivalent growth-optimal policy
orders every round, up to the allowed order value (score x cap) at the nominal price.
"""
from __future__ import annotations

from decimal import Decimal

from .env.beer_game import BACKUP, MAIN, GameConfig
from .money import to_money


def _backup(api, qty: int) -> None:
    if qty > 0:
        api.order(BACKUP, qty=qty)


def plan_obt(view, desired: int, api, cfg: GameConfig) -> int:
    """Returns the S_main quantity proposed."""
    tr = view.track[view.main_id]
    dels = [c for c in view.offer if c.template == "DELIVERY"]
    prices = [c for c in view.offer if c.template == "PRICE"]
    qty = 0
    if dels and len(prices) == 1 and tr.pending_exposure == 0 and desired > 0:
        price = to_money(Decimal(str(prices[0].slot("unit_price"))))
        if price > 0:
            qty = min(desired, int(tr.headroom // price), sum(c.remaining for c in dels))
    if qty > 0:
        api.order(view.main_id, [c.claim_id for c in dels + prices], qty=qty)
    _backup(api, desired - qty)
    nominal = to_money(view.terms[MAIN]["nominal_price"])
    # Ask for a lot that fits the budget expected once what's pending is honored.
    projected = max(tr.budget, tr.b0 + api.pending())
    api.request(max(1, int(projected // nominal)))
    return qty


def plan_reputation(view, desired: int, api, cfg: GameConfig) -> int:
    nominal = to_money(view.terms[MAIN]["nominal_price"])
    limit = view.reputation[2] if view.reputation is not None else Decimal("0")
    qty = min(max(desired, 0), int(limit // nominal)) if nominal > 0 else 0
    if qty > 0:
        api.order(view.main_id, [], qty=qty)
    _backup(api, desired - qty)
    api.request(max(1, int(limit // nominal)) if nominal > 0 else 1)
    return qty
