import pytest

from obt.env.oracles import Invoice, Oracles, Receipt
from obt.ledger import Ledger
from obt.types import Claim
from obt.verifier import TEMPLATES, Verifier, check_delivery, check_price

CP = "S_main"


# Under D11 a claim is owed only what allowed orders consumed. These helpers build claims that
# were fully relied on (DELIVERY: all qty consumed; PRICE: some units ordered at the quote).
def delivery(cid="d", created=5, qty=20, by=7, cp=CP):
    return _delivery(cid, created, qty, by, cp).with_consumption(qty, 5.0)


def owe(led, c):
    """Append a claim as extracted, then record the consumption the gate would have made."""
    led.append(c.model_copy(update={"consumed": 0, "realized_exposure": 0.0}))
    led.consume(c.claim_id, c.consumed, 5.0, c.created_round)


def _delivery(cid, created, qty, by, cp):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                      template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by})


def price(cid="p", created=5, p=5.0, until=7, cp=CP):
    return _price(cid, created, p, until, cp).with_consumption(10, p)


def _price(cid, created, p, until, cp):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                      template="PRICE", slots={"item": "widget", "unit_price": p, "valid_until": until})


def receipt(o, rnd, qty, cp=CP):
    o.record_receipt(Receipt(rnd, cp, "widget", qty, f"o{rnd}"))


def invoice(o, rnd, unit_price, cp=CP):
    o.record_invoice(Invoice(rnd, cp, "widget", 10, unit_price, f"o{rnd}"))


def test_templates_are_a_fixed_registry():
    assert set(TEMPLATES) == {"DELIVERY", "PRICE"}


# DELIVERY: received >= qty in (created_round, by_round]
@pytest.mark.parametrize("rnd,qty,ok", [
    (6, 20, True),      # inside window
    (7, 20, True),      # boundary: by_round is included
    (5, 20, False),     # boundary: created_round is excluded
    (8, 20, False),     # one round late
    (7, 19, False),     # short by one unit
    (6, 25, True),      # over-delivery still passes
])
def test_delivery_boundaries(rnd, qty, ok):
    o = Oracles()
    receipt(o, rnd, qty)
    assert check_delivery(delivery(), o.view) is ok


def test_delivery_sums_partial_receipts_and_ignores_other_suppliers():
    o = Oracles()
    receipt(o, 6, 12)
    receipt(o, 7, 8)
    receipt(o, 6, 100, cp="S_backup")
    assert check_delivery(delivery(), o.view)
    o2 = Oracles()
    receipt(o2, 6, 100, cp="S_backup")
    assert not check_delivery(delivery(), o2.view)


# PRICE: every invoice in [created_round, valid_until) has price <= unit_price
@pytest.mark.parametrize("rnd,unit,ok", [
    (5, 5.00, True),    # boundary: created_round included, equal price passes
    (6, 4.50, True),
    (6, 5.01, False),   # one cent over
    (5, 9.00, False),   # created_round is inside the window
    (7, 9.00, True),    # boundary: valid_until excluded
    (4, 9.00, True),    # before the quote
])
def test_price_boundaries(rnd, unit, ok):
    o = Oracles()
    invoice(o, rnd, unit)
    assert check_price(price(), o.view) is ok


def test_price_vacuous_and_any_violation_fails():
    o = Oracles()
    assert check_price(price(), o.view)
    invoice(o, 5, 4.0)
    invoice(o, 6, 6.0)
    assert not check_price(price(), o.view)


def make(allocate=True):
    o = Oracles()
    led = Ledger()
    return o, led, Verifier(led, o.view, allocate_receipts=allocate)


def test_step_resolves_only_due_claims_and_notifies():
    o, led, v = make()
    seen = []
    v.subscribe(lambda c, now: seen.append((c.claim_id, c.status, now)))
    owe(led, delivery("d1", by=7))
    owe(led, price("p1", until=9))
    led.append(Claim.untestable(claim_id="u", counterparty=CP, source_msg_hash="h", created_round=5))
    receipt(o, 7, 20)
    assert v.step(6) == []
    assert led["d1"].status == "PENDING"
    out = v.step(7)
    assert [c.claim_id for c in out] == ["d1"] and led["d1"].status == "PASSED"
    assert led["d1"].resolved_round == 7
    assert led["p1"].status == "PENDING"
    invoice(o, 8, 6.0)
    v.step(9)
    assert led["p1"].status == "FAILED"
    assert led["u"].status == "UNTESTABLE"
    assert seen == [("d1", "PASSED", 7), ("p1", "FAILED", 9)]
    assert v.step(10) == []


def test_late_step_still_resolves_overdue():
    o, led, v = make()
    owe(led, delivery("d1", by=7))
    receipt(o, 8, 20)   # arrives after the deadline
    v.step(12)
    assert led["d1"].status == "FAILED"


def test_no_double_counting_across_overlapping_windows():
    # One 20-unit shipment at round 7 lies in both claims' windows (D9).
    for allocate, expected in [(True, ("PASSED", "FAILED")), (False, ("PASSED", "PASSED"))]:
        o, led, v = make(allocate)
        owe(led, delivery("a", created=5, by=7))
        owe(led, delivery("b", created=6, by=8))
        receipt(o, 7, 20)
        v.step(7)
        v.step(8)
        assert (led["a"].status, led["b"].status) == expected


def test_allocation_honest_pipeline_all_pass():
    o, led, v = make()
    # Honest supplier: lot made at t arrives exactly at t+2, one lot per round.
    for t in range(1, 10):
        owe(led, delivery(f"d{t}", created=t, qty=10 + t, by=t + 2))
    for now in range(1, 13):
        t = now - 2
        if 1 <= t < 10:
            receipt(o, now, 10 + t)
        v.step(now)
    assert all(c.status == "PASSED" for c in led)


def test_units_credited_at_arrival_even_to_a_claim_that_later_fails():
    # F3 supersedes D9's "failed claims consume nothing": units go to the earliest-deadline
    # claim when they arrive, so the 20 units back "big" (owed 50) and "small" gets none.
    o, led, v = make()
    owe(led, delivery("big", created=5, qty=50, by=7))
    owe(led, delivery("small", created=6, qty=20, by=8))
    receipt(o, 7, 20)
    v.step(7)
    v.step(8)
    assert led["big"].status == "FAILED" and led["small"].status == "FAILED"
    assert v.allocated("big") == 20 and v.allocated("small") == 0
