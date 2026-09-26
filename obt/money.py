"""Money in the security path (DECISIONS D19).

Claims, actions, the budget, the gate and the monitor hold money as `Decimal`
with exactly two decimal places (whole cents) and compare it exactly, the way
spec/OBT.tla compares integers. There are no tolerances: a value with a
fraction of a cent can't be constructed (pydantic rejects it), so neither side
of any check carries float noise.

Constructing a model field from a float is exact, never rounded: 6.1 is
accepted as 6.10, 5.00000001 is rejected. The environment's cost accounting
stays float, and env amounts cross into the security path through `to_money`,
the one rounding rule:

    to_money(x) = Decimal(repr(x)) rounded half-even to a whole cent

`repr` gives the shortest decimal that round-trips the float, so float noise
(87.55000000000001) disappears; a genuine sub-cent amount is rounded half-even.
Every price in the env is a whole cent, so in practice the rule only strips
noise. Going back out (paying an invoice in the env, reporting), use `float()`.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _exact(x):
    # A float means the decimal its shortest repr shows (6.1 -> 6.1, not 6.0999...). No rounding here:
    # a value with a fraction of a cent (5.00000001) then fails decimal_places and can't be constructed.
    if isinstance(x, bool):
        raise TypeError("bool is not money")
    return Decimal(repr(x)) if isinstance(x, float) else x


Money = Annotated[Decimal, BeforeValidator(_exact), Field(decimal_places=2, max_digits=14)]


def to_money(x: float | int | str | Decimal) -> Decimal:
    if isinstance(x, bool):
        raise TypeError("bool is not money")
    d = x if isinstance(x, Decimal) else Decimal(repr(x)) if isinstance(x, float) else Decimal(str(x))
    if not d.is_finite():
        raise ValueError(f"money must be finite: {x!r}")
    return d.quantize(CENT, rounding=ROUND_HALF_EVEN)
