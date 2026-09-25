"""Claim verifier: the only code that changes claim status (I3).

Claim tests are the fixed templates below, keyed by name. Nothing here reads or
runs text from a message or an LLM; slots are already closed-type values.
"""
from __future__ import annotations

from typing import Callable

from .env.oracles import OracleView
from .ledger import Ledger
from .types import Claim

PRICE_EPS = 1e-9


def check_delivery(claim: Claim, oracles: OracleView) -> bool:
    s = claim.slots
    return oracles.received(claim.counterparty, s["item"], claim.created_round, s["by_round"]) >= s["qty"]


def check_price(claim: Claim, oracles: OracleView) -> bool:
    s = claim.slots
    invs = oracles.invoices(claim.counterparty, s["item"], claim.created_round, s["valid_until"])
    return all(i.unit_price <= s["unit_price"] + PRICE_EPS for i in invs)


TEMPLATES: dict[str, Callable[[Claim, OracleView], bool]] = {
    "DELIVERY": check_delivery,
    "PRICE": check_price,
}

Listener = Callable[[Claim, int], None]


class Verifier:
    def __init__(self, ledger: Ledger, oracles: OracleView, allocate_receipts: bool = True) -> None:
        self._ledger = ledger
        self._key = ledger.bind_verifier()
        self._oracles = oracles
        self._allocate = allocate_receipts
        # Units of each receipt (by index in the oracle log) already credited to a PASSED claim.
        self._used: dict[int, int] = {}
        self._listeners: list[Listener] = []

    def subscribe(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def _delivery_allocated(self, claim: Claim) -> bool:
        s = claim.slots
        need = s["qty"]
        take: list[tuple[int, int]] = []
        for idx, r in enumerate(self._oracles.receipts()):
            if need <= 0:
                break
            if (r.supplier != claim.counterparty or r.item != s["item"]
                    or not claim.created_round < r.round <= s["by_round"]):
                continue
            free = r.qty - self._used.get(idx, 0)
            if free > 0:
                n = min(free, need)
                take.append((idx, n))
                need -= n
        if need > 0:
            return False
        for idx, n in take:
            self._used[idx] = self._used.get(idx, 0) + n
        return True

    def _passes(self, claim: Claim) -> bool:
        if claim.template == "DELIVERY" and self._allocate:
            return self._delivery_allocated(claim)
        return TEMPLATES[claim.template](claim, self._oracles)

    def step(self, now: int) -> list[Claim]:
        """Resolve every PENDING claim with deadline <= now. Listeners run before this returns (I4)."""
        due = sorted(self._ledger.pending_due(now), key=lambda c: (c.deadline, c.created_round, c.claim_id))
        out = []
        for c in due:
            status = "PASSED" if self._passes(c) else "FAILED"
            new = self._ledger.resolve(c.claim_id, status, now, self._key)
            for fn in self._listeners:
                fn(new, now)
            out.append(new)
        return out
