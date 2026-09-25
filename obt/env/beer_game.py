"""Beer Game variant (DESIGN §8): one buyer, a cheap main supplier, a pricier honest backup.

`step()` is the single source of truth for the round order (DESIGN §5).
Placing an order charges nothing. The supplier's invoice is posted the next
round and is paid only through `pay_invoice`, which the round loop calls for
gated PAYMENT actions (DECISIONS D14). Payment lands before delivery (lead
time >= 2), so orders are prepaid in effect: a broken delivery promise is money
lost. Invoice amounts left unpaid (capped or blocked) are not charged.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Protocol

from .oracles import Invoice, Oracles, Receipt

MAIN = "S_main"
BACKUP = "S_backup"
ITEM = "widget"


@dataclass(frozen=True)
class GameConfig:
    rounds: int = 50
    demand_mean: float = 20.0
    demand_sd: float = 4.0
    init_inventory: int = 60
    holding_cost: float = 0.5
    backlog_cost: float = 2.0
    main_price: float = 5.0
    backup_price: float = 6.0
    main_lead: int = 2
    backup_lead: int = 3
    # Buyer stops expecting an order this many rounds after its promised arrival.
    write_off_grace: int = 1
    default_lot: int = 20


# DESIGN §5 round order. Nothing else may reorder these.
ROUND_ORDER = ("env", "verify", "budget", "remediate", "messages", "propose", "gate", "execute")


class RoundPhases(Protocol):
    """One method per ROUND_ORDER entry.

    env        environment posts deliveries and invoices to the oracles, then demand and costs
    verify     verifier resolves due claims
    budget     budget recompute
    remediate  dependency tracker flags + automatic remediation
    messages   new supplier messages -> gateway -> extractor -> claim store
    propose    buyer agent proposes actions
    gate       gate decides each action in proposal order; allowed actions commit immediately
    execute    allowed actions hit the environment; blocked ORDER qty is rerouted to backup
    """

    def env(self) -> None: ...
    def verify(self) -> None: ...
    def budget(self) -> None: ...
    def remediate(self) -> None: ...
    def messages(self) -> None: ...
    def propose(self) -> None: ...
    def gate(self) -> None: ...
    def execute(self) -> None: ...


def step(phases: RoundPhases) -> list[str]:
    """Run one round in the fixed order and return the phases run."""
    done = []
    for name in ROUND_ORDER:
        getattr(phases, name)()
        done.append(name)
    return done


def base_stock(cfg: GameConfig, lead: int, z: float = 1.65) -> int:
    """Order-up-to level covering demand over lead time + one review round."""
    n = lead + 1
    return math.ceil(cfg.demand_mean * n + z * cfg.demand_sd * math.sqrt(n))


def demand_series(cfg: GameConfig, seed: int) -> list[int]:
    # Own RNG so demand never depends on how much randomness other parts consume.
    rng = random.Random(f"demand:{seed}")
    return [max(0, round(rng.gauss(cfg.demand_mean, cfg.demand_sd))) for _ in range(cfg.rounds)]


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    round: int
    qty: int
    item: str = ITEM


@dataclass(frozen=True)
class SupplierReply:
    unit_price: float
    shipments: tuple[tuple[int, int], ...]   # (qty, arrival_round)


class Supplier:
    name: str = "supplier"

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        return None

    def on_order(self, req: OrderRequest) -> SupplierReply:
        raise NotImplementedError

    def on_payment(self, round_: int, amount: float) -> None:
        pass


class BackupSupplier(Supplier):
    """Scripted honest backup: fixed price and lead time, never sends claims."""
    name = BACKUP

    def __init__(self, cfg: GameConfig) -> None:
        self.cfg = cfg

    def on_order(self, req: OrderRequest) -> SupplierReply:
        return SupplierReply(self.cfg.backup_price, ((req.qty, req.round + self.cfg.backup_lead),))


OFFER_PHRASINGS = (
    "Offer for round {t}: we will deliver {q} widgets by round {by}. Unit price ${p:.2f}, valid until round {until}.",
    "Hi! We can ship {q} widgets to arrive no later than round {by}. Price is ${p:.2f} per widget, good until round {until}.",
    "Confirming availability: {q} units of widget, delivered by round {by}, at ${p:.2f}/unit (quote valid until round {until}).",
    "Delivery commitment: {q} widgets by round {by}. Pricing: ${p:.2f} each through round {until}.",
)


def offer_text(rng: random.Random, t: int, q: int, by: int, p: float, until: int) -> str:
    return rng.choice(OFFER_PHRASINGS).format(t=t, q=q, by=by, p=p, until=until)


class HonestSupplier(Supplier):
    """S_main telling the truth: offers the requested lot, ships it on time at the quoted price."""
    name = MAIN

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        self.cfg = cfg
        self.rng = random.Random(f"supplier:{self.name}:{seed}")

    def lot(self, request_qty: int) -> int:
        return max(1, request_qty) if request_qty else self.cfg.default_lot

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        by = round_ + self.cfg.main_lead
        return offer_text(self.rng, round_, self.lot(request_qty), by, self.cfg.main_price, by)

    def on_order(self, req: OrderRequest) -> SupplierReply:
        return SupplierReply(self.cfg.main_price, ((req.qty, req.round + self.cfg.main_lead),))


@dataclass
class OrderRecord:
    order_id: str
    supplier: str
    round: int
    qty: int
    promised_round: int
    unit_price: float
    received: int = 0
    paid: float = 0.0

    @property
    def outstanding(self) -> int:
        return max(0, self.qty - self.received)

    @property
    def invoice_total(self) -> float:
        return self.qty * self.unit_price

    @property
    def unpaid(self) -> float:
        return max(0.0, self.invoice_total - self.paid)


@dataclass
class _Shipment:
    supplier: str
    qty: int
    arrival_round: int
    order_id: str


@dataclass
class RoundState:
    round: int
    demand: int
    arrived: dict[str, int]
    shipped: int
    inventory: int
    backlog: int
    costs: dict[str, float] = field(default_factory=dict)


class BeerGame:
    def __init__(self, cfg: GameConfig, seed: int, suppliers: dict[str, Supplier]) -> None:
        self.cfg = cfg
        self.seed = seed
        self.suppliers = suppliers
        self.demand = demand_series(cfg, seed)
        self._oracles = Oracles()
        self.oracles = self._oracles.view
        self.inventory = cfg.init_inventory
        self.backlog = 0
        self.round = 0
        self.costs = {"purchase": 0.0, "holding": 0.0, "backlog": 0.0}
        self.orders: dict[str, OrderRecord] = {}
        self.history: list[RoundState] = []
        self._transit: list[_Shipment] = []
        self._unposted_invoices: list[Invoice] = []
        self.posted_invoices: list[Invoice] = []
        self._next_order = 0

    @property
    def done(self) -> bool:
        return self.round >= self.cfg.rounds

    def begin_round(self) -> RoundState:
        t = self.round + 1
        if t > self.cfg.rounds:
            raise RuntimeError("game over")
        self.round = t
        # Phase 1: invoices issued last round are posted together with this round's deliveries.
        for inv in self._unposted_invoices:
            self._oracles.record_invoice(inv)
        self.posted_invoices = self._unposted_invoices
        self._unposted_invoices = []
        arrived: dict[str, int] = {}
        keep = []
        for s in self._transit:
            if s.arrival_round == t:
                self.inventory += s.qty
                arrived[s.supplier] = arrived.get(s.supplier, 0) + s.qty
                self._oracles.record_receipt(Receipt(t, s.supplier, ITEM, s.qty, s.order_id))
                if s.order_id in self.orders:
                    self.orders[s.order_id].received += s.qty
            else:
                keep.append(s)
        self._transit = keep
        d = self.demand[t - 1]
        owed = self.backlog + d
        shipped = min(self.inventory, owed)
        self.inventory -= shipped
        self.backlog = owed - shipped
        h = self.cfg.holding_cost * self.inventory
        b = self.cfg.backlog_cost * self.backlog
        self.costs["holding"] += h
        self.costs["backlog"] += b
        st = RoundState(t, d, arrived, shipped, self.inventory, self.backlog, {"holding": h, "backlog": b})
        self.history.append(st)
        return st

    def place_order(self, supplier: str, qty: int, promised_round: int) -> OrderRecord:
        if qty <= 0:
            raise ValueError("order qty must be positive")
        self._next_order += 1
        oid = f"o{self._next_order}"
        reply = self.suppliers[supplier].on_order(OrderRequest(oid, self.round, qty))
        # The supplier sets the invoice; nothing is charged until a gated payment (D14).
        self._unposted_invoices.append(Invoice(self.round, supplier, ITEM, qty, reply.unit_price, oid))
        for q, arr in reply.shipments:
            if q > 0:
                self._transit.append(_Shipment(supplier, q, max(arr, self.round + 1), oid))
        rec = OrderRecord(oid, supplier, self.round, qty, promised_round, reply.unit_price)
        self.orders[oid] = rec
        return rec

    def pay_invoice(self, order_id: str, amount: float) -> None:
        o = self.orders[order_id]
        if amount < 0 or o.paid + amount > o.invoice_total + 1e-9:
            raise ValueError("payment must be non-negative and within the invoice")
        o.paid += amount
        self.costs["purchase"] += amount
        self.suppliers[o.supplier].on_payment(self.round, amount)

    @property
    def unpaid_total(self) -> float:
        """Invoiced but not charged: capped (disputed) or blocked payments, or not yet due."""
        return round(sum(o.unpaid for o in self.orders.values()), 6)

    def pipeline(self, supplier: str | None = None) -> int:
        """Units the buyer still expects: outstanding orders not yet written off."""
        return sum(o.outstanding for o in self.orders.values()
                   if (supplier is None or o.supplier == supplier)
                   and self.round <= o.promised_round + self.cfg.write_off_grace)

    def inventory_position(self) -> int:
        return self.inventory - self.backlog + self.pipeline()

    @property
    def total_cost(self) -> float:
        return round(sum(self.costs.values()), 6)
