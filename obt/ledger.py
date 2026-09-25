"""Append-only stores for claims, actions and notes (DESIGN §5, I3).

The ledger has no delete or overwrite API. Claim status can only change through
`resolve`, which needs the capability key handed out once by `bind_verifier`:
whoever binds first (the verifier) is the only party that can resolve claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .types import Action, Claim, IllegalTransition, Note


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Event:
    round: int
    kind: str          # APPEND | RESOLVE | CONSUME
    claim_id: str
    detail: str


class _VerifierKey:
    __slots__ = ()


class Ledger:
    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}
        self._events: list[Event] = []
        self._key: _VerifierKey | None = None

    def bind_verifier(self) -> _VerifierKey:
        if self._key is not None:
            raise LedgerError("a verifier is already bound to this ledger")
        self._key = _VerifierKey()
        return self._key

    def append(self, claim: Claim, round_: int | None = None) -> None:
        if claim.claim_id in self._claims:
            raise LedgerError(f"claim {claim.claim_id} already in ledger")
        if claim.status not in ("PENDING", "UNTESTABLE"):
            raise LedgerError("claims enter the ledger PENDING or UNTESTABLE")
        if claim.resolved_round is not None or claim.realized_exposure != 0.0 or claim.consumed != 0:
            raise LedgerError("new claims start unresolved and unconsumed")
        self._claims[claim.claim_id] = claim
        r = claim.created_round if round_ is None else round_
        self._events.append(Event(r, "APPEND", claim.claim_id, claim.status))

    def resolve(self, claim_id: str, status: str, round_: int, key: _VerifierKey) -> Claim:
        if self._key is None or key is not self._key:
            raise IllegalTransition("only the bound verifier may resolve claims")
        new = self._claims[claim_id].with_status(status, round_)
        self._claims[claim_id] = new
        self._events.append(Event(round_, "RESOLVE", claim_id, status))
        return new

    def consume(self, claim_id: str, qty: int, unit_price: float, round_: int) -> Claim:
        new = self._claims[claim_id].with_consumption(qty, unit_price)
        self._claims[claim_id] = new
        self._events.append(Event(round_, "CONSUME", claim_id, f"{qty}@{unit_price:.4f}"))
        return new

    def remaining(self, claim_id: str) -> int:
        return self._claims[claim_id].remaining

    def __getitem__(self, claim_id: str) -> Claim:
        return self._claims[claim_id]

    def get(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def __contains__(self, claim_id: object) -> bool:
        return claim_id in self._claims

    def __iter__(self) -> Iterator[Claim]:
        return iter(list(self._claims.values()))

    def __len__(self) -> int:
        return len(self._claims)

    def claims_of(self, counterparty: str) -> list[Claim]:
        return [c for c in self._claims.values() if c.counterparty == counterparty]

    def pending_due(self, now: int) -> list[Claim]:
        return [c for c in self._claims.values() if c.status == "PENDING" and c.deadline <= now]

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)


class ActionLog:
    """Append-only action store. Status moves only along Action.with_status."""

    def __init__(self) -> None:
        self._actions: dict[str, Action] = {}
        self._by_claim: dict[str, list[str]] = {}

    def append(self, action: Action) -> None:
        if action.action_id in self._actions:
            raise LedgerError(f"action {action.action_id} already logged")
        if action.status != "PROPOSED":
            raise LedgerError("actions enter the log PROPOSED")
        self._actions[action.action_id] = action
        for k in dict.fromkeys(action.cited_claims):
            self._by_claim.setdefault(k, []).append(action.action_id)

    def transition(self, action_id: str, status: str, round_: int, reason: str | None = None) -> Action:
        new = self._actions[action_id].with_status(status, round_, reason)
        self._actions[action_id] = new
        return new

    def get(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def citing(self, claim_id: str) -> list[Action]:
        return [self._actions[a] for a in self._by_claim.get(claim_id, [])]

    def __getitem__(self, action_id: str) -> Action:
        return self._actions[action_id]

    def __iter__(self) -> Iterator[Action]:
        return iter(list(self._actions.values()))

    def __len__(self) -> int:
        return len(self._actions)


class NoteLog:
    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}
        self._by_claim: dict[str, list[str]] = {}

    def append(self, note: Note) -> None:
        if note.note_id in self._notes:
            raise LedgerError(f"note {note.note_id} already logged")
        self._notes[note.note_id] = note
        for k in dict.fromkeys(note.cited_claims):
            self._by_claim.setdefault(k, []).append(note.note_id)

    def flag(self, note_id: str, round_: int) -> Note:
        new = self._notes[note_id].flag(round_)
        self._notes[note_id] = new
        return new

    def citing(self, claim_id: str) -> list[Note]:
        return [self._notes[n] for n in self._by_claim.get(claim_id, [])]

    def __iter__(self) -> Iterator[Note]:
        return iter(list(self._notes.values()))

    def __len__(self) -> int:
        return len(self._notes)
