"""Reputation baseline (FIXES F9, DECISIONS D22). Code only, no claim binding.

A counterparty's score is a Beta reputation over its past delivery outcomes,
score = (s+1)/(s+f+2). An order to it is allowed iff (it has fewer than n0
resolved outcomes, i.e. is on probation, or score >= theta) and the order's
value <= score x cap. An outcome is one executed order: a success iff all of
its quantity arrived by the promised round (+ grace). Outcomes come from the
order record and the receipt oracle, since the baselines extract no claims.

This scores *who* the counterparty is. OBT instead binds every action to the
specific claims it relies on, with capacity (DESIGN §6, positioning).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from fractions import Fraction
from typing import TYPE_CHECKING

from .money import CENT, to_money
from .types import Action

if TYPE_CHECKING:
    from .sim import Sim


def beta_score(s: int, f: int) -> float:
    return (s + 1) / (s + f + 2)


@dataclass(frozen=True)
class RepConfig:
    theta: float = 0.8
    cap: Decimal = Decimal("200.00")
    n0: int = 3                  # probation: theta applies after this many resolved outcomes (D22)
    grace: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "cap", to_money(self.cap))


class Reputation:
    def __init__(self, sim: "Sim", cfg: RepConfig) -> None:
        self.sim = sim
        self.cfg = cfg

    def outcomes(self, cp: str, now: int) -> tuple[int, int]:
        """(successes, failures) of cp's executed orders whose promised round (+ grace) has passed."""
        s = f = 0
        for p in self.sim.placements:
            if p["supplier"] != cp or p["remediation"] or now < p["promised"] + self.cfg.grace:
                continue
            got = sum(r.qty for r in self.sim.game.oracles.receipts()
                      if r.order_id == p["order_id"] and r.round <= p["promised"] + self.cfg.grace)
            if got >= p["qty"]:
                s += 1
            else:
                f += 1
        return s, f

    def score(self, cp: str, now: int) -> float:
        return beta_score(*self.outcomes(cp, now))

    def allow(self, a: Action, now: int) -> tuple[bool, str]:
        s, f = self.outcomes(a.counterparty, now)
        # Exact arithmetic: value <= (s+1)/(s+f+2) x cap, and score >= theta, with no float rounding.
        score = Fraction(s + 1, s + f + 2)
        if s + f >= self.cfg.n0 and score < Fraction(str(self.cfg.theta)):
            return False, "REP_SCORE"
        if Fraction(a.value) > score * Fraction(self.cfg.cap):
            return False, "REP_CAP"
        return True, "OK"

    def limit(self, cp: str, now: int) -> tuple[float, int, Decimal]:
        """(score, resolved outcomes, largest order value allowed now) for the buyer's view."""
        s, f = self.outcomes(cp, now)
        score = beta_score(s, f)
        blocked = s + f >= self.cfg.n0 and Fraction(s + 1, s + f + 2) < Fraction(str(self.cfg.theta))
        # Rounded down so the shown limit is always one the rule allows.
        limit = (Decimal(s + 1) * self.cfg.cap / Decimal(s + f + 2)).quantize(CENT, rounding=ROUND_FLOOR)
        return score, s + f, Decimal("0.00") if blocked else limit
