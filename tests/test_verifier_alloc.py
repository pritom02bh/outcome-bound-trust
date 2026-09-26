"""F3: receipts are allocated to PENDING DELIVERY claims earliest-deadline first; grace δ."""
from decimal import Decimal
import pytest

from obt.env.oracles import Invoice, Oracles, Receipt
from obt.ledger import Ledger
from obt.types import Claim
from obt.verifier import Verifier

CP = "S_main"


def world(delta=0):
    o, led = Oracles(), Ledger()
    return o, led, Verifier(led, o.view, grace=delta)


def owe(led, cid, qty, by, created=1, consumed=None, cp=CP):
    led.append(Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                          template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by}))
    n = qty if consumed is None else consumed
    if n:
        led.consume(cid, n, Decimal("5.00"), created)


def rcv(o, rnd, qty, cp=CP):
    o.record_receipt(Receipt(rnd, cp, "widget", qty, f"o{rnd}"))


def run_to(v, until):
    for t in range(1, until + 1):
        v.step(t)


def test_overlapping_claims_units_not_double_credited():
    o, led, v = world()
    owe(led, "a", 20, by=7, created=5)
    owe(led, "b", 20, by=8, created=6)
    rcv(o, 7, 20)
    run_to(v, 8)
    assert (led["a"].status, led["b"].status) == ("PASSED", "FAILED")
    assert v.allocated("a") == 20 and v.allocated("b") == 0
    credited = {}
    for idx, cid, n in v.credits():
        credited[idx] = credited.get(idx, 0) + n
    assert all(n <= o.view.receipts()[i].qty for i, n in credited.items())


def test_units_go_to_earliest_deadline_first():
    o, led, v = world()
    owe(led, "late", 10, by=9, created=1)
    owe(led, "early", 10, by=5, created=2)
    rcv(o, 4, 10)
    run_to(v, 9)
    assert (led["early"].status, led["late"].status) == ("PASSED", "FAILED")


def test_surplus_units_flow_to_next_claim():
    o, led, v = world()
    owe(led, "a", 5, by=5)
    owe(led, "b", 5, by=6)
    rcv(o, 4, 10)          # one shipment covers both
    run_to(v, 6)
    assert (led["a"].status, led["b"].status) == ("PASSED", "PASSED")
    assert v.allocated("a") == v.allocated("b") == 5


def test_partial_delivery_fails():
    o, led, v = world()
    owe(led, "a", 10, by=5)
    rcv(o, 5, 9)
    run_to(v, 5)
    assert led["a"].status == "FAILED" and v.allocated("a") == 9


def test_obligation_is_consumed_not_offered():
    o, led, v = world()
    owe(led, "a", 50, by=5, consumed=10)
    rcv(o, 5, 10)
    run_to(v, 5)
    assert led["a"].status == "PASSED"


@pytest.mark.parametrize("delta,arrive,resolve_at,status", [
    (0, 5, 5, "PASSED"),       # on time, no grace
    (0, 6, 5, "FAILED"),       # one late, no grace
    (1, 6, 6, "PASSED"),       # one late, grace 1
    (1, 7, 6, "FAILED"),       # two late, grace 1
    (2, 7, 7, "PASSED"),       # two late, grace 2
    (2, 8, 7, "FAILED"),       # three late, grace 2
])
def test_grace_boundaries(delta, arrive, resolve_at, status):
    o, led, v = world(delta)
    owe(led, "a", 10, by=5)
    rcv(o, arrive, 10)
    for t in range(1, resolve_at):
        v.step(t)
        assert led["a"].status == "PENDING"
    v.step(resolve_at)
    assert led["a"].status == status and led["a"].resolved_round == resolve_at


def test_late_delivery_after_resolution_not_credited():
    o, led, v = world()
    owe(led, "a", 10, by=5)
    run_to(v, 5)
    rcv(o, 6, 10)
    v.step(6)
    assert led["a"].status == "FAILED" and v.allocated("a") == 0


def test_receipt_before_or_at_creation_not_credited():
    o, led, v = world()
    rcv(o, 3, 10)
    owe(led, "a", 10, by=6, created=3)
    run_to(v, 6)
    assert led["a"].status == "FAILED"


def test_other_supplier_units_not_credited():
    o, led, v = world()
    owe(led, "a", 10, by=5)
    rcv(o, 4, 10, cp="S_backup")
    run_to(v, 5)
    assert led["a"].status == "FAILED"


def test_price_fails_iff_invoice_exceeds_claim_in_window():
    o, led, v = world(delta=2)
    for cid, created, until in (("ok", 1, 5), ("bad", 1, 5), ("outside", 1, 3)):
        led.append(Claim.make(claim_id=cid, counterparty=CP, source_msg_hash="h", created_round=created,
                              template="PRICE", slots={"item": "widget", "unit_price": 5.0, "valid_until": until}))
        led.consume(cid, 1, Decimal("5.00"), 1)
    o.record_invoice(Invoice(4, CP, "widget", 1, 5.0, "o1"))       # equal: fine for everyone
    run_to(v, 3)
    o.record_invoice(Invoice(4, "S_backup", "widget", 1, 9.0, "o2"))
    o.record_invoice(Invoice(4, CP, "widget", 1, 5.5, "o3"))       # after "outside" resolved
    run_to(v, 5)
    assert led["outside"].status == "PASSED"
    # "ok" and "bad" share the window, so both see the 5.50 invoice.
    assert led["ok"].status == "FAILED" and led["bad"].status == "FAILED"
    assert led["ok"].resolved_round == 5          # PRICE gets no grace
