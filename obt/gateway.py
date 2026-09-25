"""A2A gateway (DESIGN §5). Raw text stops here: it goes to the audit log and the extractor, nowhere else."""
from __future__ import annotations

import hashlib

from .extractor import Extractor
from .ledger import Ledger
from .types import Claim, Message

# A claim resolving more than H rounds after it was made can't discipline anyone in time (F2).
HORIZON_CAP = 8


class UnauthenticatedSender(Exception):
    pass


class Gateway:
    def __init__(self, extractor: Extractor, ledger: Ledger, authenticated: set[str],
                 horizon_cap: int = HORIZON_CAP) -> None:
        self.extractor = extractor
        self.ledger = ledger
        self.authenticated = frozenset(authenticated)
        self.horizon_cap = horizon_cap
        self._audit: list[Message] = []

    def receive(self, counterparty: str, round_: int, text: str) -> list[Claim]:
        if counterparty not in self.authenticated:
            raise UnauthenticatedSender(counterparty)
        h = hashlib.sha256(f"{counterparty}|{round_}|{text}".encode()).hexdigest()[:16]
        msg = Message(msg_hash=h, counterparty=counterparty, round=round_, text=text)
        self._audit.append(msg)
        claims = []
        for c in self.extractor.extract(msg):
            if c.template is not None and c.deadline - c.created_round > self.horizon_cap:
                c = Claim.untestable(claim_id=c.claim_id, counterparty=c.counterparty,
                                     source_msg_hash=c.source_msg_hash, created_round=c.created_round)
            self.ledger.append(c, round_=round_)
            claims.append(c)
        return claims

    def audit_log(self) -> tuple[Message, ...]:
        """For audit and for the no-defense baseline only; never read by the OBT memory view."""
        return tuple(self._audit)
