"""A2A gateway (DESIGN §5). Raw text stops here: it goes to the audit log and the extractor, nowhere else."""
from __future__ import annotations

import hashlib

from .extractor import Extractor
from .ledger import OfferBook
from .types import Claim, Message


class UnauthenticatedSender(Exception):
    pass


class Gateway:
    def __init__(self, extractor: Extractor, offers: OfferBook, authenticated: set[str]) -> None:
        self.extractor = extractor
        self.offers = offers
        self.authenticated = frozenset(authenticated)
        self._audit: list[Message] = []

    def receive(self, counterparty: str, round_: int, text: str) -> list[Claim]:
        if counterparty not in self.authenticated:
            raise UnauthenticatedSender(counterparty)
        h = hashlib.sha256(f"{counterparty}|{round_}|{text}".encode()).hexdigest()[:16]
        msg = Message(msg_hash=h, counterparty=counterparty, round=round_, text=text)
        self._audit.append(msg)
        claims = self.extractor.extract(msg)
        for c in claims:
            self.offers.add(c)
        return claims

    def audit_log(self) -> tuple[Message, ...]:
        """For audit and for the no-defense baseline only; never read by the OBT memory view."""
        return tuple(self._audit)
