"""Scripted S_main behaviours for DESIGN §9 scenarios 1-10. All deterministic given the seed.

Every supplier sees the buyer's lot request and the orders placed with it; none
can touch oracles, ledger, gate or verifier (threat model §2).
"""
from __future__ import annotations

import math
import random

from ..env.beer_game import (GameConfig, HonestSupplier, OrderRequest, SupplierReply, offer_text)

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

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        by = round_ + self.cfg.main_lead
        q = self.lot_for(round_, request_qty)
        if self.lies_at(round_):
            return (f"Special one-time deal for a valued partner: we will deliver {q} widgets by round {by}. "
                    f"Unit price ${self.quote(round_):.2f}, valid until round {by}.")
        return offer_text(self.rng, round_, q, by, self.quote(round_), by)

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

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        # Looks exactly like an honest offer.
        by = round_ + self.cfg.main_lead
        return offer_text(self.rng, round_, self.lot(request_qty), by, self.quote(round_), by)


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


VAGUE_LINES = (
    "Great news, we have plenty of widgets and can get you whatever you need very soon at an unbeatable price!",
    "Don't worry about supply, we've got you covered. Send the order and we'll take care of it quickly.",
    "Our partners always get priority. Expect a big shipment shortly, best pricing in the market.",
    "Trust us, we are your most reliable source. Order as much as you like and it'll be there in no time.",
)


class Vague(ScriptedSupplier):
    """6: only untestable promises. Ships half of each order, one round late."""

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        return self.rng.choice(VAGUE_LINES)

    def ship(self, req: OrderRequest) -> tuple[tuple[int, int], ...]:
        return ((req.qty // 2, req.round + self.cfg.main_lead + 1),)


class FarDeadlines(ScriptedSupplier):
    """7: delivery promises due after the horizon, so they never resolve; nothing ships."""

    def __init__(self, cfg: GameConfig, seed: int = 0, delay: int = 60) -> None:
        super().__init__(cfg, seed)
        self.delay = delay

    def quote(self, t: int) -> float:
        return 4.75

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        q = self.lot(request_qty)
        return (f"Guaranteed: we will deliver {q} widgets by round {round_ + self.delay}. "
                f"We usually ship within {self.cfg.main_lead} rounds. "
                f"Unit price ${self.quote(round_):.2f}, valid until round {round_ + self.cfg.main_lead}.")

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

    def offer_message(self, round_: int, request_qty: int) -> str | None:
        by = round_ + self.cfg.main_lead
        total = self.lot_for(round_, request_qty)
        parts = [self.chunk] * (total // self.chunk) + ([total % self.chunk] if total % self.chunk else [])
        lots = "; ".join(f"Lot {i}: {q} widgets by round {by}" for i, q in enumerate(parts, start=1))
        return f"Split shipment plan. {lots}; Unit price ${self.quote(round_):.2f}, valid until round {by}."


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
}


def make_supplier(n: int, cfg: GameConfig, seed: int) -> ScriptedSupplier:
    return SCENARIOS[n][1](cfg, seed)


def scenario_name(n: int) -> str:
    return f"{n}_{SCENARIOS[n][0]}"
