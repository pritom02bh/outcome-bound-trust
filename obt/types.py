"""Core data model (DESIGN §4).

All records are frozen. State changes go through `with_status`, which returns a
new object and raises `IllegalTransition` on anything the design forbids, so a
bug elsewhere can't quietly mutate a claim in place.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .money import ZERO, Money

# Closed item catalog: slot values must never carry free text into agent context (I5).
ITEMS = ("widget",)
Item = Literal["widget"]

Template = Literal["DELIVERY", "PRICE"]
ClaimStatus = Literal["PENDING", "PASSED", "FAILED", "LAPSED", "UNTESTABLE"]
TERMINAL = ("PASSED", "FAILED", "LAPSED", "UNTESTABLE")
ActionKind = Literal["ORDER", "PAYMENT"]
ActionStatus = Literal["PROPOSED", "EXECUTED", "BLOCKED", "FLAGGED"]

MAX_QTY = 100_000
MAX_ROUND = 100_000
MAX_PRICE = 100_000


class IllegalTransition(Exception):
    pass


class FrozenDict(dict):
    """Slots dict that can't be edited after validation (pydantic `frozen` is shallow)."""

    def _ro(self, *a, **k):
        raise TypeError("claim slots are immutable")

    __setitem__ = __delitem__ = update = pop = popitem = clear = setdefault = _ro  # type: ignore
    __ior__ = _ro  # type: ignore

    def __reduce__(self):
        return (FrozenDict, (dict(self),))


_FROZEN = ConfigDict(frozen=True, extra="forbid", strict=False)


class DeliverySlots(BaseModel):
    model_config = _FROZEN
    item: Item
    qty: int = Field(gt=0, le=MAX_QTY)
    by_round: int = Field(ge=0, le=MAX_ROUND)


class PriceSlots(BaseModel):
    model_config = _FROZEN
    item: Item
    unit_price: Money = Field(gt=0, le=MAX_PRICE)
    valid_until: int = Field(ge=0, le=MAX_ROUND)


SLOT_MODELS: dict[str, type[BaseModel]] = {"DELIVERY": DeliverySlots, "PRICE": PriceSlots}


def deadline_for(template: str, slots: dict) -> int:
    return slots["by_round"] if template == "DELIVERY" else slots["valid_until"]


class Claim(BaseModel):
    model_config = _FROZEN

    claim_id: str
    counterparty: str
    source_msg_hash: str
    created_round: int = Field(ge=0)
    # None only for UNTESTABLE claims: nothing mapped to a template.
    template: Template | None
    slots: dict
    deadline: int
    status: ClaimStatus = "PENDING"
    resolved_round: int | None = None
    realized_exposure: Money = Field(default=ZERO, ge=0)
    # DELIVERY: units of capacity consumed by allowed orders (what the supplier owes).
    # PRICE: units ordered at this quote. Zero at resolution -> LAPSED (DECISIONS D11).
    consumed: int = Field(default=0, ge=0)

    @field_validator("slots", mode="after")
    @classmethod
    def _freeze_slots(cls, v: dict) -> dict:
        return FrozenDict(v)

    @model_validator(mode="after")
    def _check(self) -> "Claim":
        if self.status == "UNTESTABLE":
            if self.template is not None or self.slots:
                raise ValueError("UNTESTABLE claims carry no template or slots")
            return self
        if self.template is None:
            raise ValueError("testable claim needs a template")
        # Round-trip through the typed slot model so only closed-type values survive.
        typed = SLOT_MODELS[self.template].model_validate(self.slots)
        if typed.model_dump() != self.slots:
            raise ValueError("slots must be exactly the typed template fields")
        if self.deadline != deadline_for(self.template, self.slots):
            raise ValueError("deadline must match the template's deadline slot")
        if self.status == "PENDING" and self.resolved_round is not None:
            raise ValueError("PENDING claim can't have resolved_round")
        if self.template == "DELIVERY" and self.consumed > self.slots["qty"]:
            raise ValueError("consumed exceeds claimed qty")
        return self

    @classmethod
    def make(cls, *, claim_id: str, counterparty: str, source_msg_hash: str,
             created_round: int, template: str, slots: dict) -> "Claim":
        typed = SLOT_MODELS[template].model_validate(slots).model_dump()
        return cls(claim_id=claim_id, counterparty=counterparty, source_msg_hash=source_msg_hash,
                   created_round=created_round, template=template, slots=typed,
                   deadline=deadline_for(template, typed))

    @classmethod
    def untestable(cls, *, claim_id: str, counterparty: str, source_msg_hash: str,
                   created_round: int) -> "Claim":
        return cls(claim_id=claim_id, counterparty=counterparty, source_msg_hash=source_msg_hash,
                   created_round=created_round, template=None, slots={},
                   deadline=created_round, status="UNTESTABLE")

    def with_status(self, new: str, round_: int) -> "Claim":
        # I3: PENDING -> PASSED | FAILED | LAPSED only; LAPSED only if nothing was consumed.
        if self.status != "PENDING" or new not in ("PASSED", "FAILED", "LAPSED"):
            raise IllegalTransition(f"claim {self.claim_id}: {self.status} -> {new}")
        if new == "LAPSED" and self.consumed != 0:
            raise IllegalTransition(f"claim {self.claim_id}: LAPSED with consumed={self.consumed}")
        return self.model_copy(update={"status": new, "resolved_round": round_})

    @property
    def remaining(self) -> int:
        return self.slots["qty"] - self.consumed if self.template == "DELIVERY" else 0

    def with_consumption(self, qty: int, unit_price: Decimal) -> "Claim":
        """Record an allowed order against this claim. Exposure = consumed units x claimed price (F2)."""
        if not isinstance(unit_price, Decimal):
            # model_copy skips validation, so a float here would put float money into the ledger (D19).
            raise TypeError("unit_price must be Decimal money")
        if self.status != "PENDING":
            raise IllegalTransition(f"claim {self.claim_id}: consumption on {self.status} claim")
        if qty < 0 or unit_price < 0:
            raise ValueError("consumption is non-negative")
        if self.template == "DELIVERY":
            if qty > self.remaining:
                raise IllegalTransition(f"claim {self.claim_id}: capacity {self.remaining} < {qty}")
            return self.model_copy(update={"consumed": self.consumed + qty,
                                           "realized_exposure": self.realized_exposure + qty * unit_price})
        return self.model_copy(update={"consumed": self.consumed + qty})


_ACTION_MOVES = {
    "PROPOSED": {"EXECUTED", "BLOCKED", "FLAGGED"},
    "EXECUTED": {"FLAGGED"},
    "BLOCKED": set(),
    "FLAGGED": set(),
}


class Action(BaseModel):
    model_config = _FROZEN

    action_id: str
    kind: ActionKind
    counterparty: str
    value: Money = Field(ge=0)
    cited_claims: tuple[str, ...] = ()
    status: ActionStatus = "PROPOSED"
    round: int = 0
    item: Item = "widget"
    qty: int = Field(default=0, ge=0, le=MAX_QTY)
    # Code sets this from the single cited PRICE claim (DECISIONS D13); value = qty x unit_price.
    unit_price: Money | None = None
    # PAYMENT only: the executed ORDER this pays for.
    ref_order: str | None = None
    # Kept so a FLAGGED action still records whether money actually moved.
    executed_round: int | None = None
    reason: str | None = None

    def with_status(self, new: str, round_: int, reason: str | None = None) -> "Action":
        if new not in _ACTION_MOVES[self.status]:
            raise IllegalTransition(f"action {self.action_id}: {self.status} -> {new}")
        update: dict = {"status": new}
        if new == "EXECUTED":
            update["executed_round"] = round_
        if reason is not None:
            update["reason"] = reason
        return self.model_copy(update=update)

    @property
    def was_executed(self) -> bool:
        return self.executed_round is not None


class Note(BaseModel):
    """Agent's own working note. Text is agent-written, never counterparty text."""
    model_config = _FROZEN

    note_id: str
    round: int
    text: str
    cited_claims: tuple[str, ...] = ()
    flagged: bool = False
    flagged_round: int | None = None

    def flag(self, round_: int) -> "Note":
        if self.flagged:
            return self
        return self.model_copy(update={"flagged": True, "flagged_round": round_})


class Message(BaseModel):
    """Raw A2A message. Lives in the gateway's audit log only."""
    model_config = _FROZEN

    msg_hash: str
    counterparty: str
    round: int
    text: str
