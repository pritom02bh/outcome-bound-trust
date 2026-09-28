"""E6: a parameterized S_main attacker for adaptive search against OBT (DECISIONS D29).

Every behaviour the scripted scenarios use, as one bounded parameter vector: how long to farm honestly, when and
how often to lie, how big the claims are, how much of a lying lot ships and how late, invoice markup and offer
discount, how far out the promised deadline is, and how many identities to burn through (re-entering under the
next one after a failed promise, as in scenario 12). Like every scripted supplier it can shape only its own
messages, shipments and invoices; it can't touch the oracles, ledger, gate or verifier (threat model §2).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..env.beer_game import MAIN, GameConfig, OrderRequest, SupplierReply
from .suppliers import ScriptedSupplier

# name -> (low, high, type). Bounds cover every scripted scenario's settings and beyond.
BOUNDS: dict[str, tuple[float, float, type]] = {
    "farm_len": (0, 50, int),           # honest rounds before the first lie
    "lie_period": (1, 10, int),         # after farming, lie in `lie_burst` rounds of every `lie_period`
    "lie_burst": (1, 5, int),
    "claim_factor": (1.0, 4.0, float),  # lot multiplier on lying rounds (bigger false claims)
    "honest_factor": (0.5, 2.0, float),  # lot multiplier on honest rounds (bigger honest claims farm more trust)
    "ship_frac": (0.0, 1.0, float),     # share of a lying lot that ships at all
    "delay": (0, 6, int),               # rounds after the promised round that a lying lot's shipped part arrives
    "honest_delay": (0, 2, int),        # rounds late on honest rounds (noise)
    "price_markup": (0.0, 1.0, float),  # invoice above the quoted price on lying rounds
    "discount": (0.0, 0.3, float),      # offer below the list price on lying rounds (bait)
    "stretch": (0, 5, int),             # promised deadline this many rounds beyond the lead time
    "identities": (1, 3, int),          # registered identities; re-enter under the next after a failed promise
}
IDENTITIES = (MAIN, "S_main_2", "S_main_3")


@dataclass(frozen=True)
class Params:
    farm_len: int = 10
    lie_period: int = 1
    lie_burst: int = 1
    claim_factor: float = 1.0
    honest_factor: float = 1.0
    ship_frac: float = 0.0
    delay: int = 0
    honest_delay: int = 0
    price_markup: float = 0.0
    discount: float = 0.0
    stretch: int = 0
    identities: int = 1

    def to_vector(self) -> list[float]:
        return [float(getattr(self, k)) for k in BOUNDS]

    @classmethod
    def from_vector(cls, v) -> "Params":
        out = {}
        for x, (k, (lo, hi, kind)) in zip(v, BOUNDS.items()):
            x = min(max(float(x), lo), hi)
            out[k] = int(round(x)) if kind is int else round(x, 4)
        return cls(**out)

    def to_unit(self) -> list[float]:
        """Each coordinate scaled to [0, 1] (the search space)."""
        return [(float(getattr(self, k)) - lo) / (hi - lo) for k, (lo, hi, _) in BOUNDS.items()]

    @classmethod
    def from_unit(cls, u) -> "Params":
        return cls.from_vector([lo + min(max(x, 0.0), 1.0) * (hi - lo) for x, (lo, hi, _) in zip(u, BOUNDS.values())])

    def as_dict(self) -> dict:
        return asdict(self)


class AdaptiveAttacker(ScriptedSupplier):
    def __init__(self, cfg: GameConfig, seed: int = 0, params: Params = Params()) -> None:
        super().__init__(cfg, seed)
        self.p = params
        self.identities = IDENTITIES[:params.identities]
        self._k = 0
        self._burned_at: int | None = None    # promised round of this identity's first unkept promise

    @property
    def identity(self) -> str:
        return self.identities[self._k]

    def lies_at(self, t: int) -> bool:
        p = self.p
        return t >= p.farm_len and (t - p.farm_len) % p.lie_period < p.lie_burst

    def quote(self, t: int) -> float:
        return round(self.cfg.main_price * (1 - self.p.discount), 2) if self.lies_at(t) else self.cfg.main_price

    def invoice_price(self, t: int) -> float:
        return round(self.quote(t) * (1 + self.p.price_markup), 2) if self.lies_at(t) else self.quote(t)

    def lot_for(self, t: int, request_qty: int) -> int:
        f = self.p.claim_factor if self.lies_at(t) else self.p.honest_factor
        return max(1, round(self.lot(request_qty) * f))

    def _by(self, t: int) -> int:
        return t + self.cfg.main_lead + self.p.stretch

    def offer_intent(self, round_: int, request_qty: int) -> dict | None:
        # A burned identity's promise has failed by now: re-enter under the next registered identity.
        if self._burned_at is not None and round_ > self._burned_at and self._k + 1 < len(self.identities):
            self._k += 1
            self._burned_at = None
        by = self._by(round_)
        # Every offer looks the same; the lie is only in what ships.
        return {"kind": "offer", "truth": self.truthful(round_),
                "values": {"qty": self.lot_for(round_, request_qty), "by": by, "until": by,
                           "price": self.quote(round_)}}

    def truthful(self, t: int) -> bool:
        return not self.lies_at(t) and self.p.honest_delay == 0

    def on_order(self, req: OrderRequest) -> SupplierReply:
        t, by = req.round, self._by(req.round)
        if not self.lies_at(t):
            arrive = self.cfg.main_lead + t + self.p.honest_delay
            if self.p.honest_delay and self._burned_at is None:
                self._burned_at = by
            return SupplierReply(self.invoice_price(t), ((req.qty, arrive),))
        if self._burned_at is None:
            self._burned_at = by
        shipped = int(req.qty * self.p.ship_frac)
        ships = ((shipped, by + self.p.delay),) if shipped > 0 else ()
        return SupplierReply(self.invoice_price(t), ships)
