"""End-to-end round loop wiring environment, gateway, ledger, verifier, gate and buyer.

Each round runs `beer_game.step(self)`, i.e. the fixed DESIGN §5 order; this
class supplies one method per phase. The buyer only proposes (phase 6); the
gate decides in proposal order (7); the environment sees allowed actions and
code-rerouted blocked quantity afterwards (8).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from .budget import BudgetConfig, TrustBudget
from .deps import DependencyTracker
from .env.beer_game import BACKUP, MAIN, BackupSupplier, BeerGame, GameConfig, Supplier, step as run_round
from .extractor import Extractor, RuleExtractor
from .gate import Gate
from .gateway import Gateway
from .ledger import ActionLog, Ledger, NoteLog
from .memory_view import MemoryView, build_view
from . import lossbound
from .money import ZERO, to_money
from .monitor import Monitor
from .transport import TRANSPORTS, make_transport
from .reputation import RepConfig, Reputation
from .types import Action, Note
from .verifier import Verifier

DEFENSES = ("obt", "none", "provenance", "reputation", "llm_selfcheck")


@dataclass(frozen=True)
class SimConfig:
    game: GameConfig = field(default_factory=GameConfig)
    b0_frac: float = 0.05
    budget_k: int = 1       # D36: B = b0 + k x max honored exposure (1 = DESIGN §6)
    window: int = 10
    allocate_receipts: bool = True
    defense: str = "obt"
    raw_history: int = 6
    horizon_cap: int = 8
    transport: str = "inproc"   # "a2a": suppliers are A2A servers, the buyer an A2A client (F11, D25)
    grace: int = 0          # δ: DELIVERY claims resolve at by_round + δ (F3)
    rep_theta: float = 0.8  # reputation baseline (F9, D22)
    rep_cap: float = 200.0
    rep_n0: int = 3

    def budget_cfg(self) -> BudgetConfig:
        return BudgetConfig.from_game(self.game, self.b0_frac, self.window, self.budget_k)

    def rep_cfg(self) -> RepConfig:
        return RepConfig(theta=self.rep_theta, cap=self.rep_cap, n0=self.rep_n0, grace=self.grace)


class Buyer(Protocol):
    def act(self, view: MemoryView, api: "BuyerAPI") -> None: ...


class BuyerAPI:
    """What a buyer may do in a round: propose actions. The gate decides them after the buyer is done.

    For S_main the buyer picks the quantity; price comes from the single cited PRICE claim
    (DECISIONS D13), so the value the gate checks is qty x claimed price, never an LLM number.
    """

    def __init__(self, sim: "Sim") -> None:
        self._sim = sim
        self.round_actions: list[Action] = []
        self.request_qty: int | None = None

    def headroom(self) -> Decimal:
        s = self._sim
        return s.budget.headroom(s.main_id, s.game.round)

    def pending(self) -> Decimal:
        return self._sim.budget.pending(self._sim.main_id)

    def order(self, counterparty: str, cited_claims=(), qty: int = 0) -> Action | None:
        """Propose an ORDER. Decided by the gate after the buyer finishes (round phase 7)."""
        s = self._sim
        t = s.game.round
        cfg = s.cfg.game
        cited = tuple(str(k) for k in cited_claims)
        qty = max(0, int(qty))
        if counterparty == BACKUP:
            cited = ()
            price = to_money(cfg.backup_price)
            promised = t + cfg.backup_lead
        elif counterparty in s.main_ids:
            found = [s.ledger.get(k) for k in cited]
            dels = [c for c in found if c is not None and c.template == "DELIVERY"]
            prices = [c.slots["unit_price"] for c in found if c is not None and c.template == "PRICE"]
            promised = max((c.slots["by_round"] for c in dels), default=t + cfg.main_lead)
            # Exactly one quote sets the price; anything else is left for the gate to reject.
            price = prices[0] if len(prices) == 1 else to_money(cfg.main_price)
        else:
            return None
        if qty <= 0 and not cited:
            return None
        return self._propose(Action(action_id=s.next_id("a"), kind="ORDER", counterparty=counterparty,
                                    qty=qty, unit_price=price, value=qty * price,
                                    cited_claims=cited, round=t), promised)

    def _propose(self, a: Action, promised: int | None = None) -> Action:
        self.round_actions.append(a)
        if promised is not None:
            self._sim._promised[a.action_id] = promised
        return a

    def veto(self, counterparty: str, qty: int, reason: str) -> Action:
        """Record an order the buyer's own check refused (llm_selfcheck baseline)."""
        s = self._sim
        price, qty = to_money(s.cfg.game.main_price), max(0, int(qty))
        a = Action(action_id=s.next_id("a"), kind="ORDER", counterparty=counterparty,
                   unit_price=price, value=qty * price, round=s.game.round, qty=qty)
        s.actions.append(a)
        rec = s.actions.transition(a.action_id, "BLOCKED", s.game.round, reason)
        self.round_actions.append(rec)
        return rec

    def note(self, text: str, cited_claims=()) -> Note:
        s = self._sim
        n = Note(note_id=s.next_id("n"), round=s.game.round, text=str(text)[:500],
                 cited_claims=tuple(str(k) for k in cited_claims))
        return s.deps.add_note(n, s.game.round)

    def request(self, qty: int) -> None:
        self.request_qty = max(1, min(int(qty), 10_000))


class _Phases:
    """Adapter so beer_game.step() drives Sim.phase_* in ROUND_ORDER, with the runtime
    invariant monitor checked after every phase (F6)."""

    def __init__(self, sim: "Sim") -> None:
        self._sim = sim

    def __getattr__(self, name: str):
        sim = self._sim

        def run() -> None:
            getattr(sim, f"phase_{name}")()
            sim.monitor.after(name)
        return run


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
        if cfg.transport not in TRANSPORTS:
            raise ValueError(cfg.transport)
        self.cfg = cfg
        self.seed = seed
        self.scenario = scenario
        self.main = main
        # A supplier may hold several authenticated identities (scenario 12). Each has its own ledger
        # history and budget; `main_id` is the one it currently speaks as, as the transport reports it.
        self.transport = make_transport(cfg.transport, main, cfg.game)
        self.main_ids: tuple[str, ...] = self.transport.identities
        self.buyer = buyer
        self.game = BeerGame(cfg.game, seed, self.transport.suppliers())
        self.ledger = Ledger()
        self.actions = ActionLog()
        self.notes = NoteLog()
        self.budget = TrustBudget(self.ledger, self.actions, cfg.budget_cfg())
        # Only OBT enforces the gate; llm_selfcheck adds its own LLM veto on top of an open gate, and
        # reputation its own code check (obt/reputation.py) in `gate_decide`.
        self.gate = Gate(self.ledger, self.actions, self.budget, enforce=cfg.defense == "obt",
                         min_lead={i: cfg.game.main_lead for i in self.main_ids})
        self.verifier = Verifier(self.ledger, self.game.oracles, cfg.allocate_receipts, grace=cfg.grace)
        self.deps = DependencyTracker(self.ledger, self.actions, self.notes, self.verifier, auto=False)
        self.gateway = Gateway(extractor or RuleExtractor(), self.ledger, set(self.main_ids),
                               horizon_cap=cfg.horizon_cap)
        self.trace: list[dict] = []
        self.request_qty = 0
        self._n = 0
        self._promised: dict[str, int] = {}
        self._order_of: dict[str, str] = {}      # ORDER action id -> env order id
        self._action_of: dict[str, str] = {}     # env order id -> ORDER action id
        self._pay_order: dict[str, str] = {}     # PAYMENT action id -> env order id
        self.phase_log: list[tuple[str, int]] = []
        self.rerouted_qty = 0
        self.shortfall_qty = 0
        # Env-level record of every placement, payment and reroute, for the loss-bound replay (F7).
        self.placements: list[dict] = []
        self.payments_made: list[dict] = []
        self.reroutes: list[dict] = []
        self.reputation = Reputation(self, cfg.rep_cfg())
        self.monitor = Monitor(self)

    @property
    def main_id(self) -> str:
        return self.transport.speaker

    def next_id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def view(self) -> MemoryView:
        v = build_view(game=self.game, ledger=self.ledger, actions=self.actions,
                       notes=self.notes, budget=self.budget, deps=self.deps, defense=self.cfg.defense,
                       main_id=self.main_id, main_ids=self.main_ids)
        if self.cfg.defense == "reputation":
            v.reputation = self.reputation.limit(self.main_id, self.game.round)
            s, f = self.reputation.outcomes(self.main_id, self.game.round)
            rc = self.reputation.cfg
            v.rep_detail = (s, f, rc.theta, rc.cap, rc.n0)
        if self.cfg.defense != "obt":
            # Every baseline keeps raw supplier messages in memory; OBT never does.
            v.raw_messages = [f"[round {m.round}] {m.text}"
                              for m in self.gateway.audit_log()[-self.cfg.raw_history:]]
        return v

    # ---- round phases (order fixed by beer_game.ROUND_ORDER) ----

    def _log(self, name: str) -> None:
        self.phase_log.append((name, self.game.round))

    def phase_env(self) -> None:
        self._st = self.game.begin_round()
        self._log("env")

    def phase_verify(self) -> None:
        self._resolved = self.verifier.step(self.game.round)
        self._log("verify")

    def phase_budget(self) -> None:
        # B and P are pure functions of the stores; snapshot them for the trace.
        t = self.game.round
        self._B0, self._P0 = self.budget_state(t)
        self._log("budget")

    def budget_state(self, t: int) -> tuple[Decimal, Decimal]:
        return self.budget.B(self.main_id, t), self.budget.pending(self.main_id)

    def phase_remediate(self) -> None:
        """Phase 4 (F4): order each failed DELIVERY claim's unallocated shortfall from backup, then
        flag everything citing it (I4). Code does this, whatever the buyer does afterwards."""
        g = self.game
        self._remediation: list[Action] = []
        if self.cfg.defense == "obt":
            for c in self._resolved:
                if c.status != "FAILED" or c.template != "DELIVERY":
                    continue
                short = c.consumed - self.verifier.allocated(c.claim_id)
                if short <= 0:
                    continue
                price = to_money(self.cfg.game.backup_price)
                a = Action(action_id=self.next_id("a"), kind="ORDER", counterparty=BACKUP, qty=short,
                           unit_price=price, value=short * price, round=g.round)
                rec = self.gate.decide(a, g.round)
                self._place(rec, g.round + self.cfg.game.backup_lead, remediation=True)
                self._remediation.append(rec)
                self.shortfall_qty += short
        self.deps.process(self._resolved, g.round)
        self._log("remediate")

    def phase_messages(self) -> None:
        t = self.game.round
        offers = self.transport.fetch_offers(t, self.request_qty)
        intent = self.transport.intent()
        # The intent's truth flag is ground truth for analysis only; nothing in the defense reads it.
        self._intent = None if intent is None else {"kind": intent["kind"], "truth": intent["truth"]}
        # The counterparty is the identity the transport authenticated, never read from the text.
        self._offer_claims = [c for who, text in offers if text for c in self.gateway.receive(who, t, text)]
        self._log("messages")

    def phase_propose(self) -> None:
        self._api = BuyerAPI(self)
        self.buyer.act(self.view(), self._api)
        self._propose_payments()
        self._log("propose")

    def _propose_payments(self) -> None:
        """Code, not the buyer, proposes paying each invoice posted this round (DECISIONS D14).
        Under OBT the amount is capped at qty x the order's claimed price; the excess stays unpaid."""
        g = self.game
        for inv in g.posted_invoices:
            ref = self._action_of.get(inv.order_id)
            order = self.actions.get(ref) if ref else None
            # The env's float invoice enters the security path through the one rounding rule (D19).
            amount = to_money(inv.total)
            if self.cfg.defense == "obt" and inv.supplier in self.main_ids and order is not None and order.unit_price:
                amount = min(amount, order.qty * order.unit_price)
            a = Action(action_id=self.next_id("a"), kind="PAYMENT", counterparty=inv.supplier,
                       value=amount, round=g.round, ref_order=ref,
                       cited_claims=order.cited_claims if order is not None else ())
            self._api._propose(a)
            self._pay_order[a.action_id] = inv.order_id

    def phase_gate(self) -> None:
        t = self.game.round
        api = self._api
        done = []
        for a in api.round_actions:
            if a.status != "PROPOSED":          # llm_selfcheck vetoes are already recorded
                done.append(a)
                continue
            done.append(self.gate_decide(a, t))
        api.round_actions = done
        self._log("gate")

    def gate_decide(self, a: Action, t: int) -> Action:
        if self.cfg.defense == "reputation" and a.kind == "ORDER" and a.counterparty in self.main_ids:
            ok, why = self.reputation.allow(a, t)
            if not ok:
                self.actions.append(a)
                return self.actions.transition(a.action_id, "BLOCKED", t, why)
        return self.gate.decide(a, t)

    def phase_execute(self) -> None:
        g = self.game
        self._rerouted = 0
        reroutes = []
        for a in self._api.round_actions:
            if a.status == "EXECUTED":
                if a.kind == "ORDER":
                    if a.qty > 0:
                        self._place(a, self._promised[a.action_id])
                else:
                    g.pay_invoice(self._pay_order[a.action_id], float(a.value))
                    self.payments_made.append({"round": g.round, "order_id": self._pay_order[a.action_id],
                                               "amount": float(a.value)})
            elif a.status == "BLOCKED" and a.kind == "ORDER" and a.counterparty in self.main_ids and a.qty > 0 \
                    and a.reason not in ("SELF_CHECK",):
                reroutes.append(a)
        for a in reroutes:
            # Remediation is code's job, not the LLM's: blocked quantity goes to backup now (F4).
            price = to_money(self.cfg.game.backup_price)
            rr = Action(action_id=self.next_id("a"), kind="ORDER", counterparty=BACKUP, qty=a.qty,
                        unit_price=price, value=a.qty * price, round=g.round)
            rec = self.gate.decide(rr, g.round)
            self._api.round_actions.append(rec)
            self._place(rec, g.round + self.cfg.game.backup_lead)
            self._rerouted += 1
            self.rerouted_qty += a.qty
            self.reroutes.append({"round": g.round, "qty": a.qty, "reason": a.reason,
                                  "blocked_unit_price": a.unit_price, "action_id": rec.action_id})
        if self._api.request_qty is not None:
            self.request_qty = self._api.request_qty
        self._log("execute")

    def _place(self, a: Action, promised: int, remediation: bool = False) -> None:
        rec = self.game.place_order(a.counterparty, a.qty, promised)
        self._order_of[a.action_id] = rec.order_id
        self._action_of[rec.order_id] = a.action_id
        self.placements.append({"round": self.game.round, "supplier": a.counterparty, "qty": a.qty,
                                "promised": promised, "order_id": rec.order_id, "action_id": a.action_id,
                                "remediation": remediation})

    def step(self) -> dict:
        phases = run_round(_Phases(self))
        g = self.game
        st = self._st
        t = g.round
        api = self._api
        row = {
            "round": t, "demand": st.demand, "inventory": g.inventory, "backlog": g.backlog,
            "arrived": dict(sorted(st.arrived.items())),
            "offer": [(c.claim_id, c.template, {k: float(v) if isinstance(v, Decimal) else v for k, v in c.slots.items()})
                      for c in self._offer_claims],
            "intent": getattr(self, "_intent", None),
            "resolved": [(c.claim_id, c.status) for c in self._resolved],
            # Reports leave the security path as floats.
            "actions": [(a.kind, a.counterparty, a.qty, float(a.value), a.status, a.reason, a.cited_claims)
                        for a in api.round_actions],
            "rerouted_orders": self._rerouted,
            "remediation": [(a.kind, a.counterparty, a.qty, float(a.value), a.status, a.reason, a.cited_claims)
                            for a in self._remediation],
            "B": float(self.budget.B(self.main_id, t)), "P": float(self.budget.pending(self.main_id)),
            "main_id": self.main_id,
            "cost": round(g.total_cost, 6),
            "phases": phases,
        }
        if self.cfg.defense == "reputation":
            # Reputation's trust state per round, for the trust-over-time figure (E2b).
            score, resolved, limit = self.reputation.limit(self.main_id, t)
            row["rep"] = {"score": score, "resolved": resolved, "limit": float(limit)}
        self.trace.append(row)
        return row

    def run(self) -> SimResult:
        try:
            while not self.game.done:
                self.step()
        finally:
            self.transport.close()
        m = self.metrics()
        if hasattr(self.buyer, "stats"):
            m["buyer"] = dict(self.buyer.stats)
        return SimResult(self.scenario, self.cfg.defense, self.seed, self.game.total_cost,
                         dict(self.game.costs), self.trace, m)

    def metrics(self) -> dict:
        acts = list(self.actions)
        main = [a for a in acts if a.counterparty in self.main_ids and a.kind == "ORDER"]
        blocked: dict[str, int] = {}
        for a in main:
            if a.status == "BLOCKED":
                blocked[a.reason or "?"] = blocked.get(a.reason or "?", 0) + 1
        claims = list(self.ledger)
        only_passed = sum(1 for a in main if a.was_executed and a.cited_claims and all(
            (k := self.ledger.get(c)) is not None and k.status == "PASSED" and (k.resolved_round or 0) <= a.round
            for c in a.cited_claims))
        paid_main = float(sum((a.value for a in main if a.was_executed), ZERO))
        received_main = sum(r.qty for r in self.game.oracles.receipts() if r.supplier in self.main_ids)
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
                       for s in ("PENDING", "PASSED", "FAILED", "LAPSED", "UNTESTABLE")},
            "unpaid_invoices": self.game.unpaid_total,
            "payments_blocked": sum(1 for a in acts if a.kind == "PAYMENT" and a.status == "BLOCKED"),
            "actions_citing_only_passed": only_passed,
            "max_B": max((r["B"] for r in self.trace), default=0.0),
            "max_P": max((r["P"] for r in self.trace), default=0.0),
            "rerouted_units": self.rerouted_qty,
            "shortfall_rerouted_units": self.shortfall_qty,
            "invariant_violations": self.monitor.summary(),
            "loss_bound": lossbound.loss_bound(self),
        }


def loss_from_lies(result: SimResult, honest: SimResult) -> float:
    """DESIGN §8: total cost minus cost on the same seed with an honest S_main."""
    return round(result.total_cost - honest.total_cost, 6)
