"""The only path from counterparty data to the buyer agent (DESIGN §5, I5).

`build_view` reads structured stores only: ledger, offer book, action/note logs,
budget and environment state. It never takes the gateway or a Message, so raw
counterparty text has no way in. Claim slots are closed types (D7), so card
fields can't carry free text either.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .budget import TrustBudget
from .deps import DependencyTracker
from .env.beer_game import BACKUP, MAIN, BeerGame
from .ledger import ActionLog, Ledger, NoteLog, OfferBook
from .types import Claim


@dataclass(frozen=True)
class ClaimCard:
    claim_id: str
    counterparty: str
    template: str | None
    slots: tuple[tuple[str, object], ...]
    status: str
    deadline: int
    created_round: int

    @classmethod
    def of(cls, c: Claim) -> "ClaimCard":
        return cls(c.claim_id, c.counterparty, c.template, tuple(sorted(c.slots.items())),
                   c.status, c.deadline, c.created_round)

    def slot(self, name: str):
        return dict(self.slots).get(name)

    def line(self) -> str:
        if self.template is None:
            return f"[{self.claim_id}] UNTESTABLE (no checkable promise; can't be cited)"
        s = dict(self.slots)
        if self.template == "DELIVERY":
            body = f"DELIVERY {s['qty']} {s['item']} by round {s['by_round']}"
        else:
            body = f"PRICE {s['item']} <= ${s['unit_price']:.2f}/unit until round {s['valid_until']}"
        return f"[{self.claim_id}] {body} | status {self.status} | resolves round {self.deadline}"


@dataclass(frozen=True)
class TrackRecord:
    counterparty: str
    b0: float
    passed: int
    failed: int
    pending: int
    untestable: int
    budget: float
    pending_exposure: float
    headroom: float
    last_failure: int | None


@dataclass
class MemoryView:
    round: int
    horizon: int
    inventory: int
    backlog: int
    pipeline: dict[str, int]
    position: int
    recent_demand: list[int]
    costs: dict[str, float]
    terms: dict[str, dict[str, float]]
    offer: list[ClaimCard]
    ledger_cards: list[ClaimCard]
    track: dict[str, TrackRecord]
    notes: list[tuple[str, str, tuple[str, ...], bool]]
    blocked: list[tuple[str, int, float, str]]
    failures: list[tuple[str, int, tuple[str, ...]]]
    defense: str = "obt"
    raw_messages: list[str] = field(default_factory=list)   # only filled for the no-defense baseline


def build_view(*, game: BeerGame, ledger: Ledger, offers: OfferBook, actions: ActionLog, notes: NoteLog,
               budget: TrustBudget, deps: DependencyTracker, defense: str = "obt",
               history: int = 8) -> MemoryView:
    t = game.round
    cfg = game.cfg
    offer = sorted((ClaimCard.of(c) for c in offers if c.counterparty == MAIN and c.created_round == t),
                   key=lambda c: c.claim_id)
    recent = sorted(ledger, key=lambda c: (c.created_round, c.claim_id))
    ledger_cards = [ClaimCard.of(c) for c in recent if c.status == "PENDING" or
                    (c.resolved_round is not None and c.resolved_round >= t - history)]
    track = {}
    for cp in (MAIN,):
        cs = ledger.claims_of(cp)
        count = lambda s: sum(1 for c in cs if c.status == s)  # noqa: E731
        track[cp] = TrackRecord(cp, budget.cfg.b0, count("PASSED"), count("FAILED"), count("PENDING"), count("UNTESTABLE"),
                                budget.B(cp, t), budget.pending(cp), budget.headroom(cp, t),
                                budget.last_failure(cp))
    blocked = [(a.counterparty, a.qty, a.value, a.reason or "") for a in actions
               if a.status == "BLOCKED" and a.round >= t - 1]
    failures = [(e.claim_id, e.round, e.actions) for e in deps.events if e.round >= t - history]
    note_rows = [(n.note_id, n.text, n.cited_claims, n.flagged) for n in notes][-history:]
    return MemoryView(
        round=t, horizon=cfg.rounds, inventory=game.inventory, backlog=game.backlog,
        pipeline={MAIN: game.pipeline(MAIN), BACKUP: game.pipeline(BACKUP)},
        position=game.inventory_position(), recent_demand=[h.demand for h in game.history[-history:]],
        costs=dict(game.costs),
        terms={BACKUP: {"unit_price": cfg.backup_price, "lead": cfg.backup_lead},
               MAIN: {"nominal_price": cfg.main_price, "lead": cfg.main_lead}},
        offer=offer, ledger_cards=ledger_cards, track=track, notes=note_rows, blocked=blocked,
        failures=failures, defense=defense)
