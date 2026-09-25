"""Message -> claims (DESIGN §5 Extractor).

An extractor only proposes (template, slots) pairs. `Extractor.extract` turns
them into Claim records through the typed slot models; anything that fails
validation becomes UNTESTABLE. Extractors never set status, trust or exposure.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from .types import Claim, Message


class Extractor:
    name = "base"

    def propose(self, msg: Message) -> list[Any]:
        """Return raw candidate specs: dicts like {"template": ..., "slots": {...}}."""
        raise NotImplementedError

    def extract(self, msg: Message) -> list[Claim]:
        try:
            specs = self.propose(msg)
        except Exception:
            specs = []
        if not isinstance(specs, list):
            specs = []
        out: list[Claim] = []
        for i, spec in enumerate(specs, start=1):
            cid = claim_id(msg, i)
            try:
                out.append(Claim.make(claim_id=cid, counterparty=msg.counterparty,
                                      source_msg_hash=msg.msg_hash, created_round=msg.round,
                                      template=spec["template"], slots=spec["slots"]))
            except (ValidationError, KeyError, TypeError, ValueError):
                out.append(Claim.untestable(claim_id=cid, counterparty=msg.counterparty,
                                            source_msg_hash=msg.msg_hash, created_round=msg.round))
        if not out:
            out.append(Claim.untestable(claim_id=claim_id(msg, 1), counterparty=msg.counterparty,
                                        source_msg_hash=msg.msg_hash, created_round=msg.round))
        return out


def claim_id(msg: Message, i: int) -> str:
    # Built from routing metadata only, never from message content.
    return f"{msg.counterparty}#{msg.round}.{i}"


_NUM = r"(\d{1,6})"
_DELIVERY = [
    re.compile(_NUM + r"\s+(?:units of\s+)?widgets?\b[^.;]*?\b(?:by|no later than)\s+round\s+" + _NUM, re.I),
]
_PRICE = re.compile(
    r"\$\s?(\d+(?:\.\d+)?)\s*(?:/\s*unit|per widget|per unit|each)?[^.;]*?"
    r"\b(?:valid until|good until|through)\s+round\s+" + _NUM, re.I)


class RuleExtractor(Extractor):
    """Deterministic regex extractor for scripted runs and as a baseline for the LLM one."""
    name = "rule"

    def propose(self, msg: Message) -> list[dict]:
        text = msg.text
        specs: list[dict] = []
        for pat in _DELIVERY:
            for m in pat.finditer(text):
                specs.append({"template": "DELIVERY",
                              "slots": {"item": "widget", "qty": int(m.group(1)), "by_round": int(m.group(2))}})
        for m in _PRICE.finditer(text):
            specs.append({"template": "PRICE",
                          "slots": {"item": "widget", "unit_price": float(m.group(1)),
                                    "valid_until": int(m.group(2))}})
        return specs
