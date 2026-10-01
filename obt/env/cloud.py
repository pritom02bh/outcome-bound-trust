"""E9 (DECISIONS D44, docs/E9_PLAN.md): a second domain, an agent buying cloud/API capacity. Domain flag "cloud".

Capacity is reserved for a term of TERM rounds: an order for q units provisioned at round r gives q units in
each round r .. r+TERM-1 while the provider is up. Each round the buyer must serve D_t requests (the Beer Game's
seeded demand); reserved capacity serves min(D_t, available) and the rest is served on demand at ON_DEMAND per
unit (never down, instant). Capacity is perishable: unused capacity is lost, with no holding cost. Prices are per
unit for the whole term (main $5.00 = $1.00/unit-round, backup $6.00, as GameConfig), invoiced the round after
the order and paid through gated PAYMENTs before provisioning (prepaid in effect, DESIGN §8).

The environment owns two oracles: a provisioning log (receipts, item "capacity") and an uptime log (round,
provider) -> up. Suppliers emit structured intents (JSON claims), turned into claims by `StructuredExtractor`
with no natural-language extraction: E9 says nothing about the extractor.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Callable

from ..extractor import Extractor, claim_id
from ..types import CLOUD_ITEMS, Claim, Message
from .beer_game import (BACKUP, MAIN, BackupSupplier, BeerGame, GameConfig, OrderRecord, OrderRequest, RoundState, Supplier,
                        SupplierReply, _Shipment)
from .oracles import Invoice, Receipt

CAPACITY = "capacity"
TERM = 5
ON_DEMAND = 2.00
DISCOUNT = 4.25


@dataclass(frozen=True)
class Lot:
    supplier: str
    qty: int
    start: int
    order_id: str


class CloudGame(BeerGame):
    """Same interface as BeerGame (the Sim drives it unchanged); capacity instead of inventory.

    `uptime`: optional (round, provider) -> up source (the kept-promise replay feeds the original run's log);
    `up_override`: (env order id, round) pairs whose units are up regardless (the replay's restored SLA rounds)."""

    def __init__(self, cfg: GameConfig, seed: int, suppliers: dict[str, Supplier],
                 uptime: Callable[[int, str], bool] | None = None,
                 up_override: set[tuple[str, int]] | None = None) -> None:
        super().__init__(cfg, seed, suppliers)
        self.costs = {"purchase": 0.0, "on_demand": 0.0}
        self.inventory = 0          # capacity available this round
        self.backlog = 0            # requests served on demand this round
        self.lots: list[Lot] = []
        self._uptime_src = uptime
        self.up_override = set(up_override or ())

    def is_up(self, supplier: str, t: int) -> bool:
        if supplier == BACKUP:
            return True
        if self._uptime_src is not None:
            return self._uptime_src(t, supplier)
        up = getattr(self.suppliers[supplier], "up", None)
        return True if up is None else bool(up(t, supplier))

    def begin_round(self) -> RoundState:
        t = self.round + 1
        if t > self.cfg.rounds:
            raise RuntimeError("game over")
        self.round = t
        for inv in self._unposted_invoices:
            self._oracles.record_invoice(inv)
        self.posted_invoices = self._unposted_invoices
        self._unposted_invoices = []
        up = {s: self.is_up(s, t) for s in self.suppliers if s != BACKUP}
        for s, u in up.items():
            self._oracles.record_uptime(t, s, u)
        arrived: dict[str, int] = {}
        keep = []
        for s in self._transit:
            if s.arrival_round == t:
                self.lots.append(Lot(s.supplier, s.qty, t, s.order_id))
                arrived[s.supplier] = arrived.get(s.supplier, 0) + s.qty
                self._oracles.record_receipt(Receipt(t, s.supplier, CAPACITY, s.qty, s.order_id))
                if s.order_id in self.orders:
                    self.orders[s.order_id].received += s.qty
            else:
                keep.append(s)
        self._transit = keep
        avail = sum(lot.qty for lot in self.lots if lot.start <= t < lot.start + TERM
                    and (lot.supplier == BACKUP or up.get(lot.supplier, True) or (lot.order_id, t) in self.up_override))
        d = self.demand[t - 1]
        od = max(0, d - avail)
        cost = ON_DEMAND * od
        self.costs["on_demand"] += cost
        self.inventory, self.backlog = avail, od
        st = RoundState(t, d, arrived, d - od, avail, od, {"on_demand": cost})
        self.history.append(st)
        return st

    def place_order(self, supplier: str, qty: int, promised_round: int) -> OrderRecord:
        if qty <= 0:
            raise ValueError("order qty must be positive")
        self._next_order += 1
        oid = f"o{self._next_order}"
        reply = self.suppliers[supplier].on_order(OrderRequest(oid, self.round, qty, CAPACITY))
        self._unposted_invoices.append(Invoice(self.round, supplier, CAPACITY, qty, reply.unit_price, oid))
        for q, arr in reply.shipments:
            if q > 0:
                self._transit.append(_Shipment(supplier, q, max(arr, self.round + 1), oid))
        rec = OrderRecord(oid, supplier, self.round, qty, promised_round, reply.unit_price)
        self.orders[oid] = rec
        return rec

    def inventory_position(self) -> int:
        """Capacity the buyer can count on main_lead rounds from now: lots still running then + what's pending."""
        t = self.round + self.cfg.main_lead
        running = sum(lot.qty for lot in self.lots if lot.start + TERM > t)
        return running + self.pipeline()


# ---------------------------------------------------------------- structured intents -> claims

class StructuredExtractor(Extractor):
    """E9's suppliers send JSON claims, not prose: {"claims": [{"template", "slots"}]}. No natural-language
    extraction and no grounding; anything that fails validation, or names an item outside the cloud catalog,
    is UNTESTABLE (fail closed)."""
    name = "structured"

    def extract(self, msg: Message) -> list[Claim]:
        try:
            specs = json.loads(msg.text)["claims"]
        except (ValueError, KeyError, TypeError):
            specs = []
        out = []
        for i, spec in enumerate(specs if isinstance(specs, list) else [], start=1):
            cid = claim_id(msg, i)
            try:
                c = Claim.make(claim_id=cid, counterparty=msg.counterparty, source_msg_hash=msg.msg_hash,
                               created_round=msg.round, template=spec["template"], slots=spec["slots"])
                if c.slots.get("item") not in CLOUD_ITEMS:
                    raise ValueError("item outside the cloud catalog")
                out.append(c)
            except Exception:                                   # noqa: BLE001 - fail closed
                out.append(Claim.untestable(claim_id=cid, counterparty=msg.counterparty,
                                            source_msg_hash=msg.msg_hash, created_round=msg.round))
        if not out:
            out.append(Claim.untestable(claim_id=claim_id(msg, 1), counterparty=msg.counterparty,
                                        source_msg_hash=msg.msg_hash, created_round=msg.round))
        return out


# ---------------------------------------------------------------- scripted providers (E9 scenarios)

class CloudSupplier(Supplier):
    """Honest by default: offers QUOTA(q by t+2) + PRICE($5.00 until t+2) + SLA(0.8 over the term), provisions
    on time, always up. Subclasses override the hooks where they lie."""
    name = MAIN
    PROMISE = "0.8"

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        self.cfg = cfg
        self.seed = seed
        self.rng = random.Random(f"cloud:{type(self).__name__}:{seed}")
        self.identities: tuple[str, ...] = (MAIN,)
        self.last_intent: dict | None = None

    @property
    def identity(self) -> str:
        return MAIN

    def lot(self, request_qty: int) -> int:
        return max(1, request_qty) if request_qty else self.cfg.default_lot

    def price(self, t: int) -> float:
        return self.cfg.main_price

    def promise(self, t: int) -> str:
        return self.PROMISE

    def lots_for(self, t: int, request_qty: int) -> list[int]:
        return [self.lot(request_qty)]

    def lies_at(self, t: int) -> bool:
        return False

    def up(self, t: int, identity: str) -> bool:
        return True

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        by = round_ + self.cfg.main_lead
        claims = [{"template": "DELIVERY", "slots": {"item": CAPACITY, "qty": q, "by_round": by}}
                  for q in self.lots_for(round_, request_qty)]
        claims.append({"template": "PRICE", "slots": {"item": CAPACITY, "unit_price": f"{self.price(round_):.2f}",
                                                       "valid_until": by}})
        claims.append({"template": "SLA", "slots": {"item": CAPACITY, "min_availability": self.promise(round_),
                                                     "start": by, "end": by + TERM - 1}})
        self.last_intent = {"kind": "structured", "truth": not self.lies_at(round_)}
        return json.dumps({"claims": claims}, sort_keys=True)

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        return ((req.qty, req.round + self.cfg.main_lead),)

    def on_order(self, req: OrderRequest) -> SupplierReply:
        return SupplierReply(self.price(req.round), () if self.lies_at(req.round) else self.ship(req))


def _outages(seed: str, rounds: int, p: Callable[[int], float]) -> set[int]:
    rng = random.Random(seed)
    return {t for t in range(1, rounds + 1) if rng.random() < p(t)}


class Honest(CloudSupplier):
    """1: provisions on time, always up (promises 0.8)."""


class AlwaysLie(CloudSupplier):
    """2: offers like an honest provider, provisions nothing and is never up (promises 0.99)."""

    def lies_at(self, t: int) -> bool:
        return True

    def promise(self, t: int) -> str:
        return "0.99"

    def up(self, t: int, identity: str) -> bool:
        return False


class FarmThenLie(CloudSupplier):
    """3: honest until round 25, then one large discounted QUOTA it doesn't provision (taken within 4 rounds),
    with 0.99 promised and half its rounds down from 25 to 40; honest again afterwards."""

    def __init__(self, cfg: GameConfig, seed: int = 0, lie_round: int = 25, patience: int = 4) -> None:
        super().__init__(cfg, seed)
        self.lie_round, self.patience, self.done = lie_round, patience, False
        self.down = _outages(f"farm:{seed}", cfg.rounds, lambda t: 0.5 if lie_round <= t <= lie_round + 15 else 0.0)

    def lies_at(self, t: int) -> bool:
        return not self.done and self.lie_round <= t < self.lie_round + self.patience

    def price(self, t: int) -> float:
        return DISCOUNT if self.lies_at(t) else self.cfg.main_price

    def promise(self, t: int) -> str:
        return "0.99" if self.lies_at(t) else self.PROMISE

    def lots_for(self, t: int, request_qty: int) -> list[int]:
        return [2 * self.lot(request_qty)] if self.lies_at(t) else [self.lot(request_qty)]

    def up(self, t: int, identity: str) -> bool:
        return t not in self.down

    def on_order(self, req: OrderRequest) -> SupplierReply:
        if self.lies_at(req.round):
            self.done = True
            return SupplierReply(DISCOUNT, ())
        return super().on_order(req)


class SlowDrift(CloudSupplier):
    """4: after round 10 provisions 2% less per round, and its outage chance grows 1% per round (promises 0.8)."""

    def __init__(self, cfg: GameConfig, seed: int = 0, start: int = 10) -> None:
        super().__init__(cfg, seed)
        self.start = start
        self.down = _outages(f"drift:{seed}", cfg.rounds, lambda t: max(0.0, 0.01 * (t - start)))

    def lies_at(self, t: int) -> bool:
        return False

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        k = req.round - self.start
        short = min(req.qty, math.ceil(req.qty * 0.02 * k)) if k > 0 else 0
        return ((req.qty - short, req.round + self.cfg.main_lead),) if req.qty > short else ()

    def up(self, t: int, identity: str) -> bool:
        return t not in self.down


class ClaimSplitting(CloudSupplier):
    """5: splits each lot into QUOTA claims of 4; from round 20 triples the total and provisions nothing."""

    def __init__(self, cfg: GameConfig, seed: int = 0, lie_from: int = 20, chunk: int = 4) -> None:
        super().__init__(cfg, seed)
        self.lie_from, self.chunk = lie_from, chunk

    def lies_at(self, t: int) -> bool:
        return t >= self.lie_from

    def lots_for(self, t: int, request_qty: int) -> list[int]:
        total = self.lot(request_qty) * (3 if self.lies_at(t) else 1)
        return [self.chunk] * (total // self.chunk) + ([total % self.chunk] if total % self.chunk else [])


class NoisyHonest(CloudSupplier):
    """6: honest intent; 15% of lots slip one round, and 5% of rounds are down (promises 0.8). Any failure here is a
    false positive of the defense."""

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        super().__init__(cfg, seed)
        self.slip = random.Random(f"slip:{seed}")
        self.down = _outages(f"noisy:{seed}", cfg.rounds, lambda t: 0.05)

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        late = 1 if self.slip.random() < 0.15 else 0
        return ((req.qty, req.round + self.cfg.main_lead + late),)

    def up(self, t: int, identity: str) -> bool:
        return t not in self.down


class Sybil(AlwaysLie):
    """7: always-lie, re-entering under its next identity once its first unkept promise has failed (as scenario 12)."""

    IDENTITIES = (MAIN, "S_main_2", "S_main_3")

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        super().__init__(cfg, seed)
        self.identities = self.IDENTITIES
        self._k = 0
        self._burned_at: int | None = None

    @property
    def identity(self) -> str:
        return self.identities[self._k]

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        if self._burned_at is not None and round_ > self._burned_at and self._k + 1 < len(self.identities):
            self._k += 1
            self._burned_at = None
        return super().offer_message(round_, request_qty)

    def on_order(self, req: OrderRequest) -> SupplierReply:
        if self._burned_at is None:
            self._burned_at = req.round + self.cfg.main_lead + TERM - 1     # its SLA window closes then
        return super().on_order(req)


SCENARIOS: dict[int, tuple[str, type[CloudSupplier]]] = {
    1: ("honest", Honest), 2: ("always_lie", AlwaysLie), 3: ("farm_then_lie", FarmThenLie),
    4: ("slow_drift", SlowDrift), 5: ("claim_splitting", ClaimSplitting), 6: ("noisy_honest", NoisyHonest),
    7: ("sybil", Sybil),
}


def make_cloud_supplier(n: int, cfg: GameConfig, seed: int) -> CloudSupplier:
    return SCENARIOS[n][1](cfg, seed)


def cloud_scenario_name(n: int) -> str:
    return f"{n}_{SCENARIOS[n][0]}"


# ---------------------------------------------------------------- scripted capacity buyer

class CapacityBuyer:
    """Deterministic buyer working from claim cards, like ScriptedClaimBuyer: keeps enough reserved capacity for
    demand + 1.65 sd, takes the main provider's offer (citing its QUOTA, PRICE and SLA claims) when it's no
    pricier than backup, and covers the rest from backup. Under OBT it pulses (D10): it accepts only when
    nothing from the provider is pending. It never checks claim status itself; the gate decides."""

    def __init__(self, cfg: GameConfig) -> None:
        self.cfg = cfg
        self.target = math.ceil(cfg.demand_mean + 1.65 * cfg.demand_sd)

    def act(self, view, api) -> None:
        cfg = self.cfg
        obt = view.defense == "obt"
        need = max(0, self.target - view.position)
        dels = [c for c in view.offer if c.template == "DELIVERY"]
        prices = [c for c in view.offer if c.template == "PRICE"]
        slas = [c for c in view.offer if c.template == "SLA"]
        got = 0
        if dels and need > 0:
            p = max((float(c.slot("unit_price")) for c in prices), default=cfg.main_price)
            qty = min(need, sum(c.remaining for c in dels))
            ok = qty > 0 and p <= cfg.backup_price
            if obt:
                ok = ok and view.track[view.main_id].pending_exposure == 0
            if ok:
                rec = api.order(view.main_id, [c.claim_id for c in dels + prices + slas], qty=qty)
                if rec is not None:
                    got = rec.qty
        if need - got > 0:
            api.order(BACKUP, qty=need - got)
        usual = int(cfg.demand_mean)
        if obt:
            tr = view.track[view.main_id]
            projected = max(tr.budget, tr.b0 + tr.k * api.pending())
            api.request(max(1, min(2 * usual, int(float(projected) // cfg.main_price))))
        else:
            api.request(usual)
