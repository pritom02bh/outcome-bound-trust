"""Action gate (DESIGN §6). Code only; the LLM proposes, this decides."""
from __future__ import annotations

from typing import Callable

from .budget import TrustBudget
from .ledger import ActionLog, Ledger, OfferBook
from .types import Action, Claim


class Gate:
    def __init__(self, ledger: Ledger, actions: ActionLog, budget: TrustBudget,
                 offers: OfferBook | None = None, enforce: bool = True) -> None:
        self.ledger = ledger
        self.actions = actions
        self.budget = budget
        self.offers = offers if offers is not None else OfferBook()
        # enforce=False is the no-defense / provenance baseline: same bookkeeping, no checks.
        self.enforce = enforce

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

    def decide(self, a: Action, now: int) -> Action:
        """Round phase 7: log, gate and commit one action. Allowed actions count toward P(c) at once,
        so later proposals in the same round see them. Environment effects happen in phase 8."""
        self.actions.append(a)
        ok, reason = self.allow(a, now) if self.enforce else (True, "UNGATED")
        if not ok:
            return self.actions.transition(a.action_id, "BLOCKED", now, reason)
        cited = list(dict.fromkeys(a.cited_claims))
        backup = a.counterparty == self.budget.cfg.backup
        if not backup:
            # D4: the offer is now relied on, so it becomes a ledger claim the verifier will test.
            for k in cited:
                if k not in self.ledger and k in self.offers:
                    self.ledger.append(self.offers.take(k), round_=now)
        done = self.actions.transition(a.action_id, "EXECUTED", now, reason)
        if not backup:
            for k in cited:
                # D1: only PENDING claims take on exposure.
                if k in self.ledger and self.ledger[k].status == "PENDING":
                    self.ledger.add_exposure(k, a.value, now)
        return done

    def submit(self, a: Action, now: int, execute: Callable[[Action], None] | None = None) -> Action:
        """decide + execute in one call (used outside the round loop, e.g. unit tests)."""
        rec = self.decide(a, now)
        if rec.status == "EXECUTED" and execute is not None:
            execute(rec)
        return rec
