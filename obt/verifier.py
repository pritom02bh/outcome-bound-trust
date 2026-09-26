"""Claim verifier: the only code that changes claim status (I3).

Claim tests are the fixed templates below, keyed by name. Nothing here reads or
runs text from a message or an LLM; slots are already closed-type values.

DELIVERY (F3): every received unit from counterparty c for item i is credited,
as it arrives, to c's PENDING DELIVERY claim for i with the earliest deadline
that still needs units and whose window (created_round, by_round + δ] contains
the arrival. A unit is credited to at most one claim (I7). A claim resolves at
by_round + δ and passes iff its credited units >= what allowed orders consumed
(D11); partial delivery fails. A claim nothing consumed resolves LAPSED.

PRICE: resolves at valid_until; fails iff any invoice from c for i in
[created_round, valid_until) is above the claimed unit price.
"""
from __future__ import annotations

from typing import Callable

from .env.oracles import OracleView
from .ledger import Ledger
from .money import to_money
from .types import Claim



def check_delivery(claim: Claim, oracles: OracleView, grace: int = 0) -> bool:
    """Literal template without allocation (units may back several claims). Kept for comparison (D9)."""
    s = claim.slots
    got = oracles.received(claim.counterparty, s["item"], claim.created_round, s["by_round"] + grace)
    return got >= claim.consumed


def check_price(claim: Claim, oracles: OracleView) -> bool:
    s = claim.slots
    invs = oracles.invoices(claim.counterparty, s["item"], claim.created_round, s["valid_until"])
    # Env invoice prices are floats: they enter the security path through the one rounding rule (D19).
    return all(to_money(i.unit_price) <= s["unit_price"] for i in invs)


TEMPLATES: dict[str, Callable[..., bool]] = {
    "DELIVERY": check_delivery,
    "PRICE": check_price,
}

Listener = Callable[[Claim, int], None]


class Verifier:
    def __init__(self, ledger: Ledger, oracles: OracleView, allocate_receipts: bool = True,
                 grace: int = 0) -> None:
        if grace < 0:
            raise ValueError("grace must be >= 0")
        self._ledger = ledger
        self._key = ledger.bind_verifier()
        self._oracles = oracles
        self._allocate = allocate_receipts
        self.grace = grace
        self._alloc: dict[str, int] = {}                  # claim id -> units credited
        self._credits: list[tuple[int, str, int]] = []    # (receipt index, claim id, units)
        self._seen = 0                                    # receipts already processed
        self._listeners: list[Listener] = []

    def subscribe(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def allocated(self, claim_id: str) -> int:
        return self._alloc.get(claim_id, 0)

    def credits(self) -> tuple[tuple[int, str, int], ...]:
        """Every (receipt index, claim id, units) credit ever made. Read-only, for monitors (I7)."""
        return tuple(self._credits)

    def due_round(self, c: Claim) -> int:
        return c.deadline + self.grace if c.template == "DELIVERY" else c.deadline

    def _allocate_new_receipts(self, now: int) -> None:
        receipts = self._oracles.receipts()
        while self._seen < len(receipts) and receipts[self._seen].round <= now:
            idx, r = self._seen, receipts[self._seen]
            self._seen += 1
            left = r.qty
            open_claims = sorted(
                (c for c in self._ledger.claims_of(r.supplier)
                 if c.status == "PENDING" and c.template == "DELIVERY" and c.slots["item"] == r.item
                 and c.created_round < r.round <= c.slots["by_round"] + self.grace
                 and self.allocated(c.claim_id) < c.consumed),
                key=lambda c: (c.deadline, c.created_round, c.claim_id))
            for c in open_claims:
                if left <= 0:
                    break
                take = min(left, c.consumed - self.allocated(c.claim_id))
                self._alloc[c.claim_id] = self.allocated(c.claim_id) + take
                self._credits.append((idx, c.claim_id, take))
                left -= take

    def _passes(self, c: Claim) -> bool:
        if c.template == "DELIVERY":
            if self._allocate:
                return self.allocated(c.claim_id) >= c.consumed
            return check_delivery(c, self._oracles, self.grace)
        return check_price(c, self._oracles)

    def step(self, now: int) -> list[Claim]:
        """Round phase 2: credit newly arrived units, then resolve every claim due by `now`."""
        if self._allocate:
            self._allocate_new_receipts(now)
        due = sorted((c for c in self._ledger if c.status == "PENDING" and self.due_round(c) <= now),
                     key=lambda c: (c.deadline, c.created_round, c.claim_id))
        out = []
        for c in due:
            if c.consumed == 0:
                # Nobody relied on it: no obligation, no credit, no penalty (D11).
                status = "LAPSED"
            else:
                status = "PASSED" if self._passes(c) else "FAILED"
            new = self._ledger.resolve(c.claim_id, status, now, self._key)
            for fn in self._listeners:
                fn(new, now)
            out.append(new)
        return out
