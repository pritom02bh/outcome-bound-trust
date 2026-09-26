"""Runtime invariant monitors (DESIGN §7, FIXES F6).

Checked after every round phase of every run. Violations are recorded, never
raised, so a run always finishes and reports them; the eval fails loudly if the
total is not zero.

I1 is re-derived here from a snapshot the gate takes *before* it commits each
decision. This is a second, independent implementation of the §6 table, so a
bug (or tamper) in `Gate.allow` shows up instead of being trusted.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from .env.beer_game import BACKUP, ROUND_ORDER
from .money import ZERO

if TYPE_CHECKING:
    from .gate import GateSnapshot
    from .sim import Sim

_DEAD = ("FAILED", "UNTESTABLE", "LAPSED")


def table_verdict(snap: "GateSnapshot") -> tuple[bool, str]:
    """Independent re-derivation of the DESIGN §6 table from a pre-commit snapshot."""
    a, now = snap.action, snap.now
    if a.counterparty == BACKUP:
        return True, "OK"
    if not a.cited_claims:
        return False, "NO_CITATION"
    claims = [snap.claims.get(k) for k in dict.fromkeys(a.cited_claims)]
    if any(k is None for k in claims):
        return False, "UNKNOWN_CLAIM"
    if any(k.counterparty != a.counterparty for k in claims):
        return False, "WRONG_COUNTERPARTY"
    if any(k.status in _DEAD for k in claims):
        return False, "BAD_CLAIM"
    inc = a.value
    if a.kind == "ORDER":
        dels = [k for k in claims if k.template == "DELIVERY"]
        live = [k for k in dels if k.status == "PENDING" and k.slots["item"] == a.item]
        if any(k.slots["item"] != a.item for k in claims) or not live \
                or any(k.slots["by_round"] - now < snap.min_lead for k in dels):
            return False, "CLAIM_MISMATCH"
        prices = [k for k in claims if k.template == "PRICE"]
        if not (len(prices) == 1 and prices[0].status == "PENDING" and prices[0].slots["item"] == a.item
                and prices[0].created_round <= now < prices[0].slots["valid_until"]
                and a.unit_price is not None and prices[0].slots["unit_price"] == a.unit_price
                and a.value == a.qty * a.unit_price):
            return False, "PRICE_MISMATCH"
        if a.qty > sum(k.slots["qty"] - k.consumed for k in live):
            return False, "OVER_CLAIM"
    else:
        ref = snap.ref
        if (ref is None or ref.kind != "ORDER" or ref.counterparty != a.counterparty or not ref.was_executed
                or ref.unit_price is None or snap.paid + a.value > ref.qty * ref.unit_price):
            return False, "OVERPAY"
        inc = ZERO
    if snap.P + inc > snap.B:
        return False, "OVER_BUDGET"
    return True, "OK"


class Monitor:
    def __init__(self, sim: "Sim") -> None:
        self.sim = sim
        self.violations: list[dict] = []
        self.checked: list[tuple[str, int]] = []
        self._statuses = self._status_map()
        self._B = self._budgets(0)
        self._events = 0
        self._decisions = 0

    # ---- snapshots
    def _status_map(self) -> dict[str, tuple[str, int]]:
        return {c.claim_id: (c.status, c.consumed) for c in self.sim.ledger}

    def _cps(self) -> set[str]:
        return {c.counterparty for c in self.sim.ledger} | {self.sim.main.name}

    def _budgets(self, now: int) -> dict[str, Decimal]:
        return {cp: self.sim.budget.B(cp, now) for cp in self._cps()}

    def _flag(self, inv: str, phase: str, detail: str) -> None:
        self.violations.append({"round": self.sim.game.round, "phase": phase, "invariant": inv, "detail": detail})

    # ---- the check, called after every phase
    def after(self, phase: str) -> None:
        s, now = self.sim, self.sim.game.round
        self.checked.append((phase, now))
        statuses = self._status_map()
        B = self._budgets(now)
        # I3: only the verifier moves statuses, only PENDING -> PASSED | FAILED | LAPSED (LAPSED iff unconsumed).
        passed_now: set[str] = set()
        for cid, (st, consumed) in statuses.items():
            old = self._statuses.get(cid)
            if old is None or old[0] == st:
                continue
            ok = phase == "verify" and old[0] == "PENDING" and st in ("PASSED", "FAILED", "LAPSED") \
                and (st != "LAPSED" or consumed == 0)
            if not ok:
                self._flag("I3", phase, f"{cid}: {old[0]} -> {st}")
            if st == "PASSED":
                passed_now.add(s.ledger[cid].counterparty)
        events = s.ledger.events
        for e in events[self._events:]:
            if e.kind == "RESOLVE" and phase != "verify":
                self._flag("I3", phase, f"RESOLVE {e.claim_id} outside the verifier")
        self._events = len(events)
        # I2: B rises only in a verifier step that passed a claim of that counterparty.
        for cp, b in B.items():
            if b > self._B.get(cp, b) and not (phase == "verify" and cp in passed_now):
                self._flag("I2", phase, f"B({cp}) {self._B.get(cp):.2f} -> {b:.2f}")
        # I1: every executed decision re-checked against its pre-commit snapshot; P <= B after execution.
        decisions = s.gate.decisions
        for snap in decisions[self._decisions:]:
            if s.gate.enforce and snap.executed:
                ok, why = table_verdict(snap)
                if not ok:
                    self._flag("I1", phase, f"{snap.action.action_id} executed but table says {why}")
        if s.gate.enforce and len(decisions) > self._decisions:
            for cp in {d.action.counterparty for d in decisions[self._decisions:] if d.executed} - {BACKUP}:
                if s.budget.pending(cp) > s.budget.B(cp, now):
                    self._flag("I1", phase, f"P({cp}) > B({cp}) after execution")
        self._decisions = len(decisions)
        # I4: a claim that failed is flagged everywhere by the end of this round's remediate phase.
        past_remediate = ROUND_ORDER.index(phase) >= ROUND_ORDER.index("remediate")
        for c in s.ledger:
            if c.status != "FAILED" or (c.resolved_round == now and not past_remediate):
                continue
            for a in s.actions.citing(c.claim_id):
                if a.was_executed and a.status != "FLAGGED":
                    self._flag("I4", phase, f"{a.action_id} cites failed {c.claim_id} but isn't flagged")
            for n in s.notes.citing(c.claim_id):
                if not n.flagged:
                    self._flag("I4", phase, f"note {n.note_id} cites failed {c.claim_id} but isn't flagged")
        # I6: capacity.
        for c in s.ledger:
            if c.template == "DELIVERY" and c.consumed > c.slots["qty"]:
                self._flag("I6", phase, f"{c.claim_id}: consumed {c.consumed} > qty {c.slots['qty']}")
        # I7: every received unit credited to at most one claim, and only to a claim of the supplier and
        # item that delivered it.
        per_receipt: dict[int, int] = {}
        receipts = s.game.oracles.receipts()
        for idx, cid, n in s.verifier.credits():
            per_receipt[idx] = per_receipt.get(idx, 0) + n
            r, c = receipts[idx], s.ledger.get(cid)
            if c is None or c.counterparty != r.supplier or c.slots.get("item") != r.item:
                self._flag("I7", phase, f"receipt {idx} from {r.supplier} credited to {cid}")
        for idx, n in per_receipt.items():
            if n > receipts[idx].qty:
                self._flag("I7", phase, f"receipt {idx}: {n} units credited, {receipts[idx].qty} received")
        self._statuses = statuses
        self._B = B

    def summary(self, limit: int = 20) -> dict:
        return {"count": len(self.violations), "details": self.violations[:limit]}
