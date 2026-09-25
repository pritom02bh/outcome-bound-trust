"""End-to-end round loop wiring environment, gateway, ledger, verifier, gate and buyer.

Per round t: arrivals/demand/costs -> verifier (+ dependency flags) -> S_main's
message through the gateway -> buyer acts via `BuyerAPI` (every order goes
through the gate) -> trace row.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .budget import BudgetConfig, TrustBudget
from .deps import DependencyTracker
from .env.beer_game import BACKUP, MAIN, BackupSupplier, BeerGame, GameConfig, Supplier
from .extractor import Extractor, RuleExtractor
from .gate import Gate
from .gateway import Gateway
from .ledger import ActionLog, Ledger, NoteLog, OfferBook
from .memory_view import MemoryView, build_view
from .types import Action, Note
from .verifier import Verifier

DEFENSES = ("obt", "none", "provenance", "selfcheck")


@dataclass(frozen=True)
class SimConfig:
    game: GameConfig = field(default_factory=GameConfig)
    b0_frac: float = 0.05
    window: int = 10
    allocate_receipts: bool = True
    defense: str = "obt"
    raw_history: int = 6

    def budget_cfg(self) -> BudgetConfig:
        return BudgetConfig.from_game(self.game, self.b0_frac, self.window)


class Buyer(Protocol):
    def act(self, view: MemoryView, api: "BuyerAPI") -> None: ...


class BuyerAPI:
    """What a buyer may do in a round. Value and quantity for S_main come from the cited claims (D5)."""

    def __init__(self, sim: "Sim") -> None:
        self._sim = sim
        self.round_actions: list[Action] = []
        self.request_qty: int | None = None

    def headroom(self) -> float:
        s = self._sim
        return s.budget.headroom(MAIN, s.game.round)

    def pending(self) -> float:
        return self._sim.budget.pending(MAIN)

    def order(self, counterparty: str, cited_claims=(), qty: int = 0, kind: str = "ORDER") -> Action | None:
        s = self._sim
        t = s.game.round
        cfg = s.cfg.game
        cited = tuple(str(k) for k in cited_claims)
        if counterparty == BACKUP:
            cited = ()
            qty = int(qty)
            price = cfg.backup_price
            promised = t + cfg.backup_lead
        elif counterparty == MAIN:
            found = [s.gate._lookup(k) for k in cited]
            dels = [c for c in found if c is not None and c.template == "DELIVERY"]
            prices = [c.slots["unit_price"] for c in found if c is not None and c.template == "PRICE"]
            if dels:
                qty = sum(c.slots["qty"] for c in dels)
                promised = max(c.slots["by_round"] for c in dels)
            else:
                qty = int(qty)
                promised = t + cfg.main_lead
            # Highest quoted price is the conservative value for the gate.
            price = max(prices) if prices else cfg.main_price
        else:
            return None
        if kind == "ORDER" and qty <= 0:
            return None
        value = round(qty * price, 6) if kind == "ORDER" else float(qty)
        s._n += 1
        a = Action(action_id=f"a{s._n}", kind=kind, counterparty=counterparty, value=value,
                   cited_claims=cited, round=t, qty=qty if kind == "ORDER" else 0)

        def execute(act: Action) -> None:
            if act.kind == "ORDER":
                s.game.place_order(act.counterparty, act.qty, promised)
            else:
                s.game.pay(act.counterparty, act.value)

        rec = s.gate.submit(a, t, execute)
        self.round_actions.append(rec)
        return rec

    def note(self, text: str, cited_claims=()) -> Note:
        s = self._sim
        s._n += 1
        n = Note(note_id=f"n{s._n}", round=s.game.round, text=str(text)[:500],
                 cited_claims=tuple(str(k) for k in cited_claims))
        return s.deps.add_note(n, s.game.round)

    def request(self, qty: int) -> None:
        self.request_qty = max(1, min(int(qty), 10_000))


@dataclass
class SimResult:
    scenario: str
    defense: str
    seed: int
    total_cost: float
    costs: dict[str, float]
    trace: list[dict]
    metrics: dict


class Sim:
    def __init__(self, cfg: SimConfig, seed: int, main: Supplier, buyer: Buyer,
                 extractor: Extractor | None = None, scenario: str = "") -> None:
        if cfg.defense not in DEFENSES:
            raise ValueError(cfg.defense)
        self.cfg = cfg
        self.seed = seed
        self.scenario = scenario
        self.main = main
        self.buyer = buyer
        self.game = BeerGame(cfg.game, seed, {MAIN: main, BACKUP: BackupSupplier(cfg.game)})
        self.ledger = Ledger()
        self.actions = ActionLog()
        self.notes = NoteLog()
        self.offers = OfferBook()
        self.budget = TrustBudget(self.ledger, self.actions, cfg.budget_cfg())
        # Only OBT enforces the gate; selfcheck adds its own LLM veto on top of an open gate.
        self.gate = Gate(self.ledger, self.actions, self.budget, self.offers, enforce=cfg.defense == "obt")
        self.verifier = Verifier(self.ledger, self.game.oracles, cfg.allocate_receipts)
        self.deps = DependencyTracker(self.ledger, self.actions, self.notes, self.verifier)
        self.gateway = Gateway(extractor or RuleExtractor(), self.offers, {MAIN})
        self.trace: list[dict] = []
        self.request_qty = 0
        self._n = 0

    def view(self) -> MemoryView:
        v = build_view(game=self.game, ledger=self.ledger, offers=self.offers, actions=self.actions,
                       notes=self.notes, budget=self.budget, deps=self.deps, defense=self.cfg.defense)
        if self.cfg.defense in ("none", "selfcheck"):
            # Baselines (a)/(b) keep raw supplier messages in memory; OBT never does.
            v.raw_messages = [f"[round {m.round}] {m.text}"
                              for m in self.gateway.audit_log()[-self.cfg.raw_history:]]
        return v

    def step(self) -> dict:
        g = self.game
        st = g.begin_round()
        t = g.round
        resolved = self.verifier.step(t)
        self.offers.expire_before(t)
        text = self.main.offer_message(t, self.request_qty)
        offer_claims = self.gateway.receive(MAIN, t, text) if text else []
        api = BuyerAPI(self)
        self.buyer.act(self.view(), api)
        if api.request_qty is not None:
            self.request_qty = api.request_qty
        row = {
            "round": t, "demand": st.demand, "inventory": g.inventory, "backlog": g.backlog,
            "arrived": dict(sorted(st.arrived.items())),
            "offer": [(c.claim_id, c.template, dict(c.slots)) for c in offer_claims],
            "resolved": [(c.claim_id, c.status) for c in resolved],
            "actions": [(a.kind, a.counterparty, a.qty, a.value, a.status, a.reason, a.cited_claims)
                        for a in api.round_actions],
            "B": round(self.budget.B(MAIN, t), 6), "P": round(self.budget.pending(MAIN), 6),
            "cost": round(g.total_cost, 6),
        }
        self.trace.append(row)
        return row

    def run(self) -> SimResult:
        while not self.game.done:
            self.step()
        return SimResult(self.scenario, self.cfg.defense, self.seed, self.game.total_cost,
                         dict(self.game.costs), self.trace, self.metrics())

    def metrics(self) -> dict:
        acts = list(self.actions)
        main = [a for a in acts if a.counterparty == MAIN]
        blocked: dict[str, int] = {}
        for a in main:
            if a.status == "BLOCKED":
                blocked[a.reason or "?"] = blocked.get(a.reason or "?", 0) + 1
        claims = list(self.ledger)
        only_passed = sum(1 for a in main if a.was_executed and a.cited_claims and all(
            (k := self.ledger.get(c)) is not None and k.status == "PASSED" and (k.resolved_round or 0) <= a.round
            for c in a.cited_claims))
        paid_main = sum(a.value for a in main if a.was_executed)
        received_main = sum(r.qty for r in self.game.oracles.receipts() if r.supplier == MAIN)
        ordered_main = sum(a.qty for a in main if a.was_executed and a.kind == "ORDER")
        return {
            "main_orders_executed": sum(1 for a in main if a.was_executed),
            "main_orders_blocked": sum(blocked.values()),
            "blocked_by_reason": dict(sorted(blocked.items())),
            "main_value_executed": round(paid_main, 6),
            "main_units_ordered": ordered_main,
            "main_units_received": received_main,
            "flagged_actions": sum(1 for a in acts if a.status == "FLAGGED"),
            "flagged_notes": sum(1 for n in self.notes if n.flagged),
            "claims": {s: sum(1 for c in claims if c.status == s)
                       for s in ("PENDING", "PASSED", "FAILED", "UNTESTABLE")},
            "actions_citing_only_passed": only_passed,
            "max_B": max((r["B"] for r in self.trace), default=0.0),
            "max_P": max((r["P"] for r in self.trace), default=0.0),
        }


def loss_from_lies(result: SimResult, honest: SimResult) -> float:
    """DESIGN §8: total cost minus cost on the same seed with an honest S_main."""
    return round(result.total_cost - honest.total_cost, 6)
