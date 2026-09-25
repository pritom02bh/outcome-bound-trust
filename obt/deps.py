"""Failure propagation (DESIGN §5, I4).

In the round loop the tracker runs as phase 4 (`process`), right after the
verifier and before anything else can act on the failed claim. Standalone
(auto=True) it listens to the verifier directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .ledger import ActionLog, Ledger, NoteLog
from .types import Claim, Note
from .verifier import Verifier


@dataclass(frozen=True)
class FailureEvent:
    claim_id: str
    counterparty: str
    round: int
    actions: tuple[str, ...]
    notes: tuple[str, ...]


class DependencyTracker:
    def __init__(self, ledger: Ledger, actions: ActionLog, notes: NoteLog, verifier: Verifier,
                 auto: bool = True) -> None:
        self.ledger = ledger
        self.actions = actions
        self.notes = notes
        self.events: list[FailureEvent] = []
        self._hooks: list[Callable[[FailureEvent], None]] = []
        if auto:
            verifier.subscribe(self._on_resolved)

    def on_failure(self, hook: Callable[[FailureEvent], None]) -> None:
        """Register a replan hook, called once per failed claim."""
        self._hooks.append(hook)

    def process(self, resolved: list[Claim], now: int) -> list[FailureEvent]:
        """Phase 4: flag everything citing the claims that just failed."""
        before = len(self.events)
        for c in resolved:
            self._on_resolved(c, now)
        return self.events[before:]

    def _on_resolved(self, claim: Claim, now: int) -> None:
        if claim.status != "FAILED":
            return
        flagged_actions = []
        for a in self.actions.citing(claim.claim_id):
            if a.status in ("EXECUTED", "PROPOSED"):
                self.actions.transition(a.action_id, "FLAGGED", now, f"CITED_FAILED:{claim.claim_id}")
                flagged_actions.append(a.action_id)
            elif a.status == "FLAGGED":
                flagged_actions.append(a.action_id)
        flagged_notes = []
        for n in self.notes.citing(claim.claim_id):
            self.notes.flag(n.note_id, now)
            flagged_notes.append(n.note_id)
        ev = FailureEvent(claim.claim_id, claim.counterparty, now, tuple(flagged_actions), tuple(flagged_notes))
        self.events.append(ev)
        for hook in self._hooks:
            hook(ev)

    def add_note(self, note: Note, now: int) -> Note:
        """Store an agent note; one citing an already-FAILED claim is flagged on entry."""
        self.notes.append(note)
        if any((k := self.ledger.get(c)) is not None and k.status == "FAILED" for c in note.cited_claims):
            return self.notes.flag(note.note_id, now)
        return note
