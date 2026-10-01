"""Environment-owned outcome records (DESIGN §5 Oracles).

Only the environment holds `Oracles` (the writer). Everything else, the verifier
included, gets an `OracleView`, which exposes queries and nothing that writes.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Receipt:
    round: int
    supplier: str
    item: str
    qty: int
    order_id: str


@dataclass(frozen=True)
class Invoice:
    round: int
    supplier: str
    item: str
    qty: int
    unit_price: float
    order_id: str

    @property
    def total(self) -> float:
        return self.qty * self.unit_price


class Oracles:
    def __init__(self) -> None:
        self._receipts: list[Receipt] = []
        self._invoices: list[Invoice] = []
        self._uptime: dict[tuple[int, str], bool] = {}       # E9 (D44): (round, provider) -> up
        self.view = OracleView(self)

    def record_uptime(self, round_: int, supplier: str, up: bool) -> None:
        self._uptime[(round_, supplier)] = bool(up)

    def record_receipt(self, r: Receipt) -> None:
        self._receipts.append(r)

    def record_invoice(self, inv: Invoice) -> None:
        self._invoices.append(inv)


class OracleView:
    __slots__ = ("__src",)

    def __init__(self, src: Oracles) -> None:
        self.__src = src

    def received(self, supplier: str, item: str, after_round: int, through_round: int) -> int:
        """Units of `item` received from `supplier` in rounds (after_round, through_round]."""
        return sum(r.qty for r in self.__src._receipts
                   if r.supplier == supplier and r.item == item
                   and after_round < r.round <= through_round)

    def invoices(self, supplier: str, item: str, from_round: int, before_round: int) -> tuple[Invoice, ...]:
        """Invoices for `item` from `supplier` issued in rounds [from_round, before_round)."""
        return tuple(i for i in self.__src._invoices
                     if i.supplier == supplier and i.item == item
                     and from_round <= i.round < before_round)

    def receipts(self) -> tuple[Receipt, ...]:
        return tuple(self.__src._receipts)

    def uptime(self, supplier: str, start: int, end: int) -> tuple[int, int]:
        """(up rounds, recorded rounds) of `supplier` in rounds [start, end] (E9, D44)."""
        rec = [self.__src._uptime[(t, supplier)] for t in range(start, end + 1) if (t, supplier) in self.__src._uptime]
        return sum(rec), len(rec)

    def all_invoices(self) -> tuple[Invoice, ...]:
        return tuple(self.__src._invoices)
