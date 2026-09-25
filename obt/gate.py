"""Action gate (DESIGN §6). Code only; the LLM proposes, this decides."""
from __future__ import annotations

from typing import Callable

from .budget import TrustBudget
from .ledger import ActionLog, Ledger, OfferBook
from .types import Action, Claim


class Gate:
    def __init__(self, ledger: Ledger, actions: ActionLog, budget: TrustBudget,
                 offers: OfferBook | None = None) -> None:
        self.ledger = ledger
        self.actions = actions
        self.budget = budget
        self.offers = offers if offers is not None else OfferBook()

    def _lookup(self, k: str) -> Claim | None:
        return self.ledger.get(k) or self.offers.get(k)

    def allow(self, a: Action, now: int) -> tuple[bool, str]:
        if a.counterparty == self.budget.cfg.backup:
            return True, "OK"  # scripted honest supplier, nothing to check
        if not a.cited_claims:
            return False, "NO_CITATION"
        claims = [self._lookup(k) for k in a.cited_claims]
        if any(k is None for k in claims):
            return False, "UNKNOWN_CLAIM"
        if any(k.counterparty != a.counterparty for k in claims):
            return False, "WRONG_COUNTERPARTY"
        if any(k.status in ("FAILED", "UNTESTABLE") for k in claims):
            return False, "BAD_CLAIM"
        if self.budget.pending(a.counterparty) + a.value > self.budget.B(a.counterparty, now):
            return False, "OVER_BUDGET"
        return True, "OK"

    def submit(self, a: Action, now: int, execute: Callable[[Action], None] | None = None) -> Action:
        """Log, gate, and (if allowed) execute one action. Returns its final record."""
        self.actions.append(a)
        ok, reason = self.allow(a, now)
        if not ok:
            return self.actions.transition(a.action_id, "BLOCKED", now, reason)
        cited = list(dict.fromkeys(a.cited_claims))
        if a.counterparty != self.budget.cfg.backup:
            # D4: the offer is now relied on, so it becomes a ledger claim the verifier will test.
            for k in cited:
                if k not in self.ledger:
                    self.ledger.append(self.offers.take(k), round_=now)
        if execute is not None:
            execute(a)
        done = self.actions.transition(a.action_id, "EXECUTED", now, "OK")
        if a.counterparty != self.budget.cfg.backup:
            for k in cited:
                # D1: only PENDING claims take on exposure.
                if self.ledger[k].status == "PENDING":
                    self.ledger.add_exposure(k, a.value, now)
        return done
