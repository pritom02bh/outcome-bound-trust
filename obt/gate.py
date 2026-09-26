"""Action gate (DESIGN §6, FIXES F2). Code only; the LLM proposes, this decides.

All money here is exact Decimal cents (DECISIONS D19): every comparison is exact, as in spec/OBT.tla.

`allow` returns the first failing check, in the order of the DESIGN §6 table.
`decide` also commits an allowed action: it consumes claim capacity (earliest
deadline first) and sets realized exposure = consumed units x claimed price.
Nothing else in the system writes exposure.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from .budget import TrustBudget
from .ledger import ActionLog, Ledger
from .money import ZERO
from .types import Action, Claim



@dataclass
class GateSnapshot:
    """What the gate saw just before deciding one action. Read by the I1 runtime monitor."""
    action: Action
    now: int
    claims: dict[str, Claim]
    P: Decimal
    B: Decimal
    paid: Decimal
    ref: Action | None
    min_lead: int
    executed: bool = False
    reason: str = ""


class Gate:
    def __init__(self, ledger: Ledger, actions: ActionLog, budget: TrustBudget, enforce: bool = True,
                 min_lead: dict[str, int] | None = None) -> None:
        self.ledger = ledger
        self.actions = actions
        self.budget = budget
        # enforce=False is the no-defense / provenance baseline: same bookkeeping, no checks.
        self.enforce = enforce
        self.min_lead = dict(min_lead or {})
        self.decisions: list[GateSnapshot] = []

    def lookup(self, k: str) -> Claim | None:
        return self.ledger.get(k)

    def paid_so_far(self, order_id: str) -> Decimal:
        return sum((a.value for a in self.actions
                    if a.kind == "PAYMENT" and a.ref_order == order_id and a.was_executed), ZERO)

    def _cited_deliveries(self, a: Action, claims: list[Claim]) -> list[Claim]:
        return [k for k in claims if k.template == "DELIVERY" and k.status == "PENDING"
                and k.slots["item"] == a.item]

    def allow(self, a: Action, now: int) -> tuple[bool, str]:
        if a.counterparty == self.budget.cfg.backup:
            return True, "OK"  # scripted honest supplier, nothing to check
        if not a.cited_claims:
            return False, "NO_CITATION"
        claims = [self.lookup(k) for k in dict.fromkeys(a.cited_claims)]
        if any(k is None for k in claims):
            return False, "UNKNOWN_CLAIM"
        if any(k.counterparty != a.counterparty for k in claims):
            return False, "WRONG_COUNTERPARTY"
        if any(k.status in ("FAILED", "UNTESTABLE", "LAPSED") for k in claims):
            return False, "BAD_CLAIM"
        increment = a.value
        if a.kind == "ORDER":
            dels = self._cited_deliveries(a, claims)
            lead = self.min_lead.get(a.counterparty, 0)
            # Strict item binding (D18): every cited claim must be for the order's item.
            if any(k.slots["item"] != a.item for k in claims) or not dels or any(k.slots["by_round"] - now < lead for k in claims if k.template == "DELIVERY"):
                return False, "CLAIM_MISMATCH"
            prices = [k for k in claims if k.template == "PRICE"]
            if (len(prices) != 1 or prices[0].status != "PENDING" or prices[0].slots["item"] != a.item
                    or not prices[0].created_round <= now < prices[0].slots["valid_until"]
                    or a.unit_price is None
                    or prices[0].slots["unit_price"] != a.unit_price
                    or a.value != a.qty * a.unit_price):
                return False, "PRICE_MISMATCH"
            if a.qty > sum(k.remaining for k in dels):
                return False, "OVER_CLAIM"
        else:
            ref = self.actions.get(a.ref_order) if a.ref_order else None
            if (ref is None or ref.kind != "ORDER" or ref.counterparty != a.counterparty
                    or not ref.was_executed or ref.unit_price is None
                    or self.paid_so_far(ref.action_id) + a.value > ref.qty * ref.unit_price):
                return False, "OVERPAY"
            # Pays for an order whose value is already in P(c); OVERPAY caps it there (DECISIONS D14).
            increment = ZERO
        if self.budget.pending(a.counterparty) + increment > self.budget.B(a.counterparty, now):
            return False, "OVER_BUDGET"
        return True, "OK"

    def decide(self, a: Action, now: int) -> Action:
        """Round phase 7: log, gate and commit one action. Allowed actions count toward P(c) and use up
        claim capacity at once, so later proposals in the same round see them."""
        ref = self.actions.get(a.ref_order) if a.ref_order else None
        snap = GateSnapshot(action=a, now=now,
                            claims={k: c for k in a.cited_claims if (c := self.ledger.get(k)) is not None},
                            P=self.budget.pending(a.counterparty), B=self.budget.B(a.counterparty, now),
                            paid=self.paid_so_far(ref.action_id) if ref else ZERO, ref=ref,
                            min_lead=self.min_lead.get(a.counterparty, 0))
        self.decisions.append(snap)
        self.actions.append(a)
        ok, reason = self.allow(a, now) if self.enforce else (True, "UNGATED")
        snap.reason = reason
        if not ok:
            return self.actions.transition(a.action_id, "BLOCKED", now, reason)
        if a.kind == "ORDER" and a.counterparty != self.budget.cfg.backup:
            self._consume(a, now)
        snap.executed = True
        return self.actions.transition(a.action_id, "EXECUTED", now, reason)

    def _consume(self, a: Action, now: int) -> None:
        claims = [k for k in (self.lookup(c) for c in dict.fromkeys(a.cited_claims))
                  if k is not None and k.status == "PENDING" and k.counterparty == a.counterparty]
        price = a.unit_price if a.unit_price is not None else ZERO
        left = a.qty
        for k in sorted((k for k in claims if k.template == "DELIVERY"), key=lambda k: (k.deadline, k.claim_id)):
            take = min(left, k.remaining)
            if take > 0:
                self.ledger.consume(k.claim_id, take, price, now)
                left -= take
        for k in claims:
            if k.template == "PRICE":
                self.ledger.consume(k.claim_id, a.qty, price, now)

    def submit(self, a: Action, now: int, execute: Callable[[Action], None] | None = None) -> Action:
        """decide + execute in one call (used outside the round loop, e.g. unit tests)."""
        rec = self.decide(a, now)
        if rec.status == "EXECUTED" and execute is not None:
            execute(rec)
        return rec
