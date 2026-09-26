"""Scripted S_main behaviours for DESIGN §9 scenarios 1-12. All deterministic given the seed.

Every supplier sees the buyer's lot request and the orders placed with it; none
can touch oracles, ledger, gate or verifier (threat model §2).
"""
from __future__ import annotations

import math
import random

from ..env.beer_game import MAIN, GameConfig, HonestSupplier, OrderRequest, SupplierReply

DISCOUNT_PRICE = 4.25


class ScriptedSupplier(HonestSupplier):
    """Honest by default; subclasses override the hooks where they lie."""

    def quote(self, t: int) -> float:
        return self.cfg.main_price

    def invoice_price(self, t: int) -> float:
        return self.quote(t)

    def lies_at(self, t: int) -> bool:
        return False

    def lot_for(self, t: int, request_qty: int) -> int:
        return self.lot(request_qty)

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        return ((req.qty, req.round + self.cfg.main_lead),)

    def truthful(self, t: int) -> bool:
        """Truth flag of the intent: will the promise made at round t be kept (delivery and price)?"""
        return not self.lies_at(t)

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        by = round_ + self.cfg.main_lead
        lie = self.lies_at(round_)
        return {"kind": "deal" if lie else "offer", "truth": self.truthful(round_),
                "values": {"qty": self.lot_for(round_, request_qty), "by": by, "until": by,
                           "price": self.quote(round_)}}

    def on_order(self, req: OrderRequest) -> SupplierReply:
        if self.lies_at(req.round):
            return SupplierReply(self.invoice_price(req.round), ())
        return SupplierReply(self.invoice_price(req.round), self.ship(req))


class Honest(ScriptedSupplier):
    """1: utility baseline."""


class AlwaysLie(ScriptedSupplier):
    """2: every delivery promise is false."""

    def lies_at(self, t: int) -> bool:
        return True

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        # Looks exactly like an honest offer.
        by = round_ + self.cfg.main_lead
        return {"kind": "offer", "truth": False,
                "values": {"qty": self.lot(request_qty), "by": by, "until": by, "price": self.quote(round_)}}


class FarmThenLie(ScriptedSupplier):
    """3: honest until `lie_round`, then one large, discounted false promise.

    The special deal stays on the table for `patience` rounds until the buyer
    takes it; after that one lie the supplier goes back to honest trading.
    """

    def __init__(self, cfg: GameConfig, seed: int = 0, lie_round: int = 25, factor: int = 2,
                 patience: int = 4) -> None:
        super().__init__(cfg, seed)
        self.lie_rounds: tuple[int, ...] = (lie_round,)
        self.factor = factor
        self.patience = patience
        self.done: set[int] = set()

    def _window(self, t: int) -> int | None:
        for r in self.lie_rounds:
            if r <= t < r + self.patience and r not in self.done:
                return r
        return None

    def lies_at(self, t: int) -> bool:
        return self._window(t) is not None

    def quote(self, t: int) -> float:
        return DISCOUNT_PRICE if self.lies_at(t) else self.cfg.main_price

    def lot_for(self, t: int, request_qty: int) -> int:
        q = self.lot(request_qty)
        return q * self.factor if self.lies_at(t) else q

    def on_order(self, req: OrderRequest) -> SupplierReply:
        r = self._window(req.round)
        if r is not None:
            self.done.add(r)
            return SupplierReply(DISCOUNT_PRICE, ())
        return super().on_order(req)


class SlowDrift(ScriptedSupplier):
    """4: ships a little less each round after `start`."""

    def __init__(self, cfg: GameConfig, seed: int = 0, start: int = 10, rate: float = 0.02) -> None:
        super().__init__(cfg, seed)
        self.start = start
        self.rate = rate

    def truthful(self, t: int) -> bool:
        return t <= self.start

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        k = req.round - self.start
        short = min(req.qty, math.ceil(req.qty * self.rate * k)) if k > 0 else 0
        return ((req.qty - short, req.round + self.cfg.main_lead),)


class PriceBait(ScriptedSupplier):
    """5: quotes below the honest price, invoices well above it. Delivers on time."""

    def quote(self, t: int) -> float:
        return 4.50

    def invoice_price(self, t: int) -> float:
        return 6.50

    def truthful(self, t: int) -> bool:
        return False                    # the price promise is never kept


class Vague(ScriptedSupplier):
    """6: only untestable promises. Ships half of each order, one round late."""

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        return {"kind": "vague", "truth": False, "values": {}}

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        return ((req.qty // 2, req.round + self.cfg.main_lead + 1),)


class FarDeadlines(ScriptedSupplier):
    """7: delivery promises due after the horizon, so they never resolve; nothing ships."""

    def __init__(self, cfg: GameConfig, seed: int = 0, delay: int = 60) -> None:
        super().__init__(cfg, seed)
        self.delay = delay

    def quote(self, t: int) -> float:
        return 4.75

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        return {"kind": "far_deadline", "truth": False,
                "values": {"qty": self.lot(request_qty), "far": round_ + self.delay, "lead": self.cfg.main_lead,
                           "price": self.quote(round_), "until": round_ + self.cfg.main_lead}}

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        return ()


class ClaimSplitting(ScriptedSupplier):
    """8: splits lots into many small DELIVERY claims; honest until `lie_from`, then triples the total and ships nothing."""

    def __init__(self, cfg: GameConfig, seed: int = 0, lie_from: int = 20, chunk: int = 4, factor: int = 3) -> None:
        super().__init__(cfg, seed)
        self.lie_from = lie_from
        self.chunk = chunk
        self.factor = factor

    def lies_at(self, t: int) -> bool:
        return t >= self.lie_from

    def lot_for(self, t: int, request_qty: int) -> int:
        q = self.lot(request_qty)
        return q * self.factor if self.lies_at(t) else q

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        by = round_ + self.cfg.main_lead
        total = self.lot_for(round_, request_qty)
        parts = [self.chunk] * (total // self.chunk) + ([total % self.chunk] if total % self.chunk else [])
        return {"kind": "split", "truth": not self.lies_at(round_),
                "values": {"by": by, "until": by, "price": self.quote(round_), "lot_sizes": parts}}


class NoisyHonest(ScriptedSupplier):
    """9: honest intent, but each shipment slips one round with probability `p`."""

    def __init__(self, cfg: GameConfig, seed: int = 0, p: float = 0.15) -> None:
        super().__init__(cfg, seed)
        self.p = p
        self.delay_rng = random.Random(f"delay:{seed}")

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        late = 1 if self.delay_rng.random() < self.p else 0
        return ((req.qty, req.round + self.cfg.main_lead + late),)


class FarmFailRefarm(FarmThenLie):
    """10: farm, lie once, re-farm, lie again."""

    def __init__(self, cfg: GameConfig, seed: int = 0, lie_rounds: tuple[int, ...] = (15, 35), factor: int = 2,
                 patience: int = 4) -> None:
        super().__init__(cfg, seed, lie_round=lie_rounds[0], factor=factor, patience=patience)
        self.lie_rounds = lie_rounds


class ExtractionAttack(ScriptedSupplier):
    """11: a real offer wrapped in injected parser instructions and decoy numbers that shrink the quantity
    and inflate the price. It ships the shrunk lot and invoices the inflated price, so it profits only if
    the extractor records the injected values instead of the offer's."""

    INFLATED = 5.75          # below backup's $6, so a fooled buyer would take it

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        super().__init__(cfg, seed)
        self.small = cfg.default_lot // 2

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        # The injection text itself is a bank template (message_bank.INJECTIONS), written by template.
        by = round_ + self.cfg.main_lead
        q = self.lot(request_qty)
        self.small = max(1, q // 2)
        return {"kind": "injection", "truth": False,
                "values": {"qty": q, "by": by, "until": by, "price": self.cfg.main_price,
                           "qs": self.small, "hi": self.INFLATED}}

    def on_order(self, req: OrderRequest) -> SupplierReply:
        return SupplierReply(self.INFLATED, ((min(req.qty, self.small), req.round + self.cfg.main_lead),))


class SybilReentry(AlwaysLie):
    """12: lies from the cold start; once a claim has failed, comes back under the next registered identity,
    which starts at b0 again. Identities are authenticated and costly to create (threat model §2), so the
    supplier holds a fixed few; the gain is at most b0 per identity."""

    IDENTITIES = (MAIN, "S_main_2", "S_main_3")

    def __init__(self, cfg: GameConfig, seed: int = 0) -> None:
        super().__init__(cfg, seed)
        self.identities = self.IDENTITIES
        self._k = 0
        self._burned_at: int | None = None    # by_round of this identity's first unkept promise

    @property
    def identity(self) -> str:
        return self.identities[self._k]

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        # The unkept promise has failed by now (verifier resolves at by_round): re-enter under a new name.
        if self._burned_at is not None and round_ > self._burned_at and self._k + 1 < len(self.identities):
            self._k += 1
            self._burned_at = None
        return super().offer_intent(round_, request_qty)

    def on_order(self, req: OrderRequest) -> SupplierReply:
        if self._burned_at is None:
            self._burned_at = req.round + self.cfg.main_lead
        return super().on_order(req)


SCENARIOS: dict[int, tuple[str, type[ScriptedSupplier]]] = {
    1: ("honest", Honest),
    2: ("always_lie", AlwaysLie),
    3: ("farm_then_lie", FarmThenLie),
    4: ("slow_drift", SlowDrift),
    5: ("price_bait", PriceBait),
    6: ("vague", Vague),
    7: ("far_deadlines", FarDeadlines),
    8: ("claim_splitting", ClaimSplitting),
    9: ("noisy_honest", NoisyHonest),
    10: ("farm_fail_refarm", FarmFailRefarm),
    11: ("extraction_attack", ExtractionAttack),
    12: ("sybil_reentry", SybilReentry),
}


def make_supplier(n: int, cfg: GameConfig, seed: int) -> ScriptedSupplier:
    return SCENARIOS[n][1](cfg, seed)


def scenario_name(n: int) -> str:
    return f"{n}_{SCENARIOS[n][0]}"
