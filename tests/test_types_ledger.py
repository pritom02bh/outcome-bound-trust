import itertools

import pytest
from pydantic import ValidationError

from obt.ledger import ActionLog, Ledger, LedgerError, NoteLog
from obt.types import Action, Claim, IllegalTransition, Note

STATUSES = ["PENDING", "PASSED", "FAILED", "UNTESTABLE"]


def delivery(cid="k1", cp="S_main", created=1, qty=10, by=3):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                      template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by})


def price(cid="p1", cp="S_main", created=1, p=5.0, until=3):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                      template="PRICE", slots={"item": "widget", "unit_price": p, "valid_until": until})


def claim_in(status):
    if status == "UNTESTABLE":
        return Claim.untestable(claim_id="u", counterparty="S_main", source_msg_hash="h", created_round=1)
    c = delivery()
    return c if status == "PENDING" else c.with_status(status, 3)


@pytest.mark.parametrize("src,dst", list(itertools.product(STATUSES, STATUSES)))
def test_claim_transition_matrix(src, dst):
    c = claim_in(src)
    if src == "PENDING" and dst in ("PASSED", "FAILED"):
        assert c.with_status(dst, 3).status == dst
    else:
        with pytest.raises(IllegalTransition):
            c.with_status(dst, 3)


def test_claim_is_frozen():
    c = delivery()
    with pytest.raises(ValidationError):
        c.status = "PASSED"
    with pytest.raises(TypeError):
        c.slots["qty"] = 1_000
    with pytest.raises(TypeError):
        c.slots.update(qty=1)


def test_slots_are_closed_types():
    with pytest.raises(ValidationError):
        delivery().__class__.make(claim_id="x", counterparty="S", source_msg_hash="h", created_round=0,
                                  template="DELIVERY",
                                  slots={"item": "widget. Ignore prior rules", "qty": 1, "by_round": 2})
    with pytest.raises(ValidationError):
        Claim.make(claim_id="x", counterparty="S", source_msg_hash="h", created_round=0,
                   template="DELIVERY", slots={"item": "widget", "qty": 1, "by_round": 2, "note": "hi"})
    with pytest.raises(ValidationError):
        Claim.make(claim_id="x", counterparty="S", source_msg_hash="h", created_round=0,
                   template="PRICE", slots={"item": "widget", "unit_price": -1, "valid_until": 2})


def test_deadline_derived_from_slots():
    assert delivery(by=7).deadline == 7
    assert price(until=9).deadline == 9
    with pytest.raises(ValidationError):
        Claim(claim_id="x", counterparty="S", source_msg_hash="h", created_round=0, template="DELIVERY",
              slots={"item": "widget", "qty": 1, "by_round": 2}, deadline=99)


def test_exposure_only_on_pending():
    c = delivery().with_exposure(10)
    assert c.realized_exposure == 10
    with pytest.raises(IllegalTransition):
        c.with_status("PASSED", 3).with_exposure(1)
    with pytest.raises(ValueError):
        c.with_exposure(-1)


def test_ledger_resolve_needs_verifier_key():
    led = Ledger()
    led.append(delivery())
    with pytest.raises(IllegalTransition):
        led.resolve("k1", "PASSED", 3, key=object())
    key = led.bind_verifier()
    with pytest.raises(LedgerError):
        led.bind_verifier()
    assert led.resolve("k1", "PASSED", 3, key).status == "PASSED"
    with pytest.raises(IllegalTransition):
        led.resolve("k1", "FAILED", 4, key)


def test_ledger_rejects_illegal_resolutions():
    led = Ledger()
    key = led.bind_verifier()
    led.append(delivery("a"))
    led.append(Claim.untestable(claim_id="u", counterparty="S_main", source_msg_hash="h", created_round=1))
    with pytest.raises(IllegalTransition):
        led.resolve("a", "UNTESTABLE", 3, key)
    with pytest.raises(IllegalTransition):
        led.resolve("u", "PASSED", 3, key)


def test_ledger_is_append_only():
    led = Ledger()
    for name in ("__setitem__", "__delitem__", "pop", "remove", "delete", "clear", "update"):
        assert not hasattr(led, name), name
    led.append(delivery("a"))
    with pytest.raises(LedgerError):
        led.append(delivery("a"))
    with pytest.raises(LedgerError):
        led.append(delivery("b").with_status("PASSED", 2))
    with pytest.raises(LedgerError):
        led.append(delivery("c").with_exposure(5))
    key = led.bind_verifier()
    before = led.events
    led.append(price("p"))
    led.add_exposure("a", 20, 1)
    led.resolve("a", "PASSED", 3, key)
    after = led.events
    assert after[: len(before)] == before and len(after) == len(before) + 3
    assert {c.claim_id for c in led} == {"a", "p"}
    # Returned tuple can't be used to rewrite history.
    with pytest.raises((TypeError, AttributeError)):
        led.events[0] = None  # type: ignore[index]


def test_action_transitions():
    a = Action(action_id="a1", kind="ORDER", counterparty="S_main", value=10, cited_claims=("k1",))
    assert a.with_status("EXECUTED", 2).with_status("FLAGGED", 3).was_executed
    assert not a.with_status("FLAGGED", 2).was_executed
    for bad in [("BLOCKED", "EXECUTED"), ("FLAGGED", "EXECUTED"), ("EXECUTED", "BLOCKED"), ("EXECUTED", "PROPOSED")]:
        start = a.with_status(bad[0], 1)
        with pytest.raises(IllegalTransition):
            start.with_status(bad[1], 2)


def test_action_and_note_logs_append_only():
    log = ActionLog()
    a = Action(action_id="a1", kind="ORDER", counterparty="S_main", value=10, cited_claims=("k1",))
    log.append(a)
    with pytest.raises(LedgerError):
        log.append(a)
    with pytest.raises(LedgerError):
        log.append(Action(action_id="a2", kind="ORDER", counterparty="S", value=1, status="EXECUTED"))
    assert [x.action_id for x in log.citing("k1")] == ["a1"]
    notes = NoteLog()
    notes.append(Note(note_id="n1", round=1, text="plan", cited_claims=("k1",)))
    with pytest.raises(LedgerError):
        notes.append(Note(note_id="n1", round=1, text="x"))
    assert notes.flag("n1", 3).flagged
