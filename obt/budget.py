"""Per-counterparty trust budget B(c) and pending exposure P(c) (DESIGN §6).

Computed from the ledger and action log on every call, never cached or set, so
there is no stored trust value anything could overwrite.
"""
from __future__ import annotations

from dataclasses import dataclass

from .env.beer_game import BACKUP, GameConfig
from .ledger import ActionLog, Ledger


@dataclass(frozen=True)
class BudgetConfig:
    b0: float = 5.0
    window: int = 10
    backup: str = BACKUP

    @classmethod
    def from_game(cls, cfg: GameConfig, frac: float = 0.05, window: int = 10) -> "BudgetConfig":
        # DESIGN §6 default: b0 = 5% of expected per-round spend at the main price.
        return cls(b0=frac * cfg.demand_mean * cfg.main_price, window=window)


class TrustBudget:
    def __init__(self, ledger: Ledger, actions: ActionLog, cfg: BudgetConfig) -> None:
        self.ledger = ledger
        self.actions = actions
        self.cfg = cfg

    def last_failure(self, c: str) -> int | None:
        rounds = [k.resolved_round for k in self.ledger.claims_of(c) if k.status == "FAILED"]
        return max(rounds) if rounds else None

    def B(self, c: str, now: int) -> float:
        f = self.last_failure(c)
        floor = None
        if f is not None:
            if now - f < self.cfg.window:
                return self.cfg.b0
            # DECISIONS D3: passes during the cool-down don't count, so the window
            # expiring never raises B by itself (I2).
            floor = f + self.cfg.window
        earned = [k.realized_exposure for k in self.ledger.claims_of(c)
                  if k.status == "PASSED" and (floor is None or k.resolved_round >= floor)]
        return self.cfg.b0 + max(earned, default=0.0)

    def pending(self, c: str) -> float:
        total = 0.0
        for a in self.actions:
            if a.counterparty != c or not a.was_executed:
                continue
            cited = (self.ledger.get(k) for k in set(a.cited_claims))
            if any(k is not None and k.counterparty == c and k.status == "PENDING" for k in cited):
                total += a.value
        return total

    def headroom(self, c: str, now: int) -> float:
        return max(0.0, self.B(c, now) - self.pending(c))
