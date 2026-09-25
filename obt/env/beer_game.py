"""Beer Game variant (DESIGN §8): one buyer, a cheap main supplier, a pricier honest backup.

Round t runs: arrivals -> demand -> holding/backlog cost, then the buyer orders.
Orders are prepaid at the supplier's invoice price, which is what makes a broken
delivery promise a direct loss.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

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

    @property
    def outstanding(self) -> int:
        return max(0, self.qty - self.received)


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
        self.costs = {"purchase": 0.0, "payment": 0.0, "holding": 0.0, "backlog": 0.0}
        self.orders: dict[str, OrderRecord] = {}
        self.history: list[RoundState] = []
        self._transit: list[_Shipment] = []
        self._next_order = 0

    @property
    def done(self) -> bool:
        return self.round >= self.cfg.rounds

    def begin_round(self) -> RoundState:
        t = self.round + 1
        if t > self.cfg.rounds:
            raise RuntimeError("game over")
        self.round = t
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
        # The supplier sets the invoice; the buyer pays it up front.
        self._oracles.record_invoice(Invoice(self.round, supplier, ITEM, qty, reply.unit_price, oid))
        self.costs["purchase"] += qty * reply.unit_price
        for q, arr in reply.shipments:
            if q > 0:
                self._transit.append(_Shipment(supplier, q, max(arr, self.round + 1), oid))
        rec = OrderRecord(oid, supplier, self.round, qty, promised_round, reply.unit_price)
        self.orders[oid] = rec
        return rec

    def pay(self, supplier: str, amount: float) -> None:
        if amount < 0:
            raise ValueError("payment must be non-negative")
        self.costs["payment"] += amount
        self.suppliers[supplier].on_payment(self.round, amount)

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
