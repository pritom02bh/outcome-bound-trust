"""F6 conformance check 1: the gate and the runtime monitor's independent table can't drift apart.

Random ledgers, action logs and proposed actions (wrong items, unknown ids, every claim status, over-capacity
orders, over-budget orders, overpayments, one-cent value/budget offsets at every boundary). On every input,
`Gate.allow` and `monitor.table_verdict` must return the same reason code. The spec side is checked by trace
replay (spec/replay.py).
"""
from decimal import Decimal

import pydantic
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from obt.env.beer_game import BACKUP, MAIN
from obt.money import to_money
from obt.monitor import table_verdict
from obt.types import Action, Claim
from spec.replay import build_world, snapshot, with_item

OTHER = "S_other"
IDS = [f"k{i}" for i in range(5)]
ITEMS = ["widget", "gadget"]
PRICES = [Decimal("5.00"), Decimal("4.00")]
C = Decimal("0.01")


@st.composite
def claim(draw, cid):
    cp = draw(st.sampled_from([MAIN, MAIN, OTHER]))
    created = draw(st.integers(0, 6))
    tmpl = draw(st.sampled_from(["DELIVERY", "DELIVERY", "PRICE", "PRICE", "UNTESTABLE"]))
    if tmpl == "UNTESTABLE":
        return Claim.untestable(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created)
    status = draw(st.sampled_from(["PENDING", "PENDING", "PASSED", "FAILED", "LAPSED"]))
    resolved = None if status == "PENDING" else draw(st.integers(0, 8))
    by = draw(st.integers(0, 9))
    if tmpl == "DELIVERY":
        qty = draw(st.integers(1, 6))
        c = Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                       template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by})
        consumed = 0 if status == "LAPSED" else draw(st.integers(0, qty))
        exposure = consumed * draw(st.sampled_from(PRICES))
    else:
        c = Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                       template="PRICE", slots={"item": "widget", "unit_price": draw(st.sampled_from(PRICES)),
                                                "valid_until": by})
        consumed = 0 if status == "LAPSED" else draw(st.integers(0, 8))
        exposure = Decimal("0.00")
    c = with_item(c, draw(st.sampled_from(ITEMS)))
    return c.model_copy(update={"status": status, "resolved_round": resolved, "consumed": consumed,
                                "realized_exposure": exposure})


cites = st.lists(st.sampled_from(IDS + ["ghost"]), max_size=4).map(tuple)
# Money is exact cents (D19): the smallest possible offset is one cent, so boundaries are probed at +-1c.
value_offset = st.sampled_from([Decimal("0.00")] * 3 + [C, -C, Decimal("0.50")])


@st.composite
def order(draw, aid, cp=None, round_=0):
    qty = draw(st.integers(0, 8))
    price = draw(st.sampled_from(PRICES + [None]))
    value = max(Decimal("0.00"), qty * (price or PRICES[0]) + draw(value_offset))
    a = Action(action_id=aid, kind="ORDER", counterparty=cp or draw(st.sampled_from([MAIN, MAIN, OTHER, BACKUP])),
               qty=qty, unit_price=price, value=value, cited_claims=draw(cites), round=round_)
    return a.model_copy(update={"item": draw(st.sampled_from(ITEMS))})


@st.composite
def world_and_action(draw):
    claims = [draw(claim(cid)) for cid in draw(st.lists(st.sampled_from(IDS), unique=True, max_size=5))]
    prior = []
    for i in range(draw(st.integers(0, 3))):
        a = draw(order(f"o{i}", cp=draw(st.sampled_from([MAIN, OTHER])), round_=draw(st.integers(0, 6))))
        fate = draw(st.sampled_from(["EXECUTED", "EXECUTED", "FLAGGED", "BLOCKED", "PROPOSED"]))
        upd = {"status": fate}
        if fate in ("EXECUTED", "FLAGGED"):
            upd["executed_round"] = a.round
        prior.append(a.model_copy(update=upd))
    executed = [a for a in prior if a.was_executed]
    if executed and draw(st.booleans()):
        ref = draw(st.sampled_from(executed))
        prior.append(Action(action_id="pay0", kind="PAYMENT", counterparty=ref.counterparty,
                            value=draw(st.sampled_from([Decimal("1.00"), Decimal("5.00"), ref.value])),
                            cited_claims=ref.cited_claims,
                            round=ref.round + 1, ref_order=ref.action_id, status="EXECUTED",
                            executed_round=ref.round + 1))
    now = draw(st.integers(0, 8))
    shaped = draw(st.booleans())
    if shaped:
        # A well-formed offer the order can cite, so the later rows (OVER_CLAIM, OVER_BUDGET, OK) come up;
        # prior orders citing it add pending exposure.
        cap, price = draw(st.integers(1, 6)), draw(st.sampled_from(PRICES))
        claims = [c for c in claims if c.claim_id not in ("gd", "gp")] + [
            Claim.make(claim_id="gd", counterparty=MAIN, source_msg_hash="h", created_round=max(0, now - 1),
                       template="DELIVERY", slots={"item": "widget", "qty": cap,
                                                    "by_round": now + draw(st.integers(0, 4))}),
            Claim.make(claim_id="gp", counterparty=MAIN, source_msg_hash="h", created_round=max(0, now - 1),
                       template="PRICE", slots={"item": "widget", "unit_price": price,
                                                "valid_until": now + draw(st.integers(0, 3))})]
        for i in range(draw(st.integers(0, 2))):
            q = draw(st.integers(1, 3))
            prior.append(Action(action_id=f"s{i}", kind="ORDER", counterparty=MAIN, qty=q, unit_price=price,
                                value=q * price, cited_claims=("gd", "gp"), round=max(0, now - 1),
                                status="EXECUTED", executed_round=max(0, now - 1)))
        if draw(st.booleans()):
            q = draw(st.integers(max(0, cap - 1), cap + 2))
            extra = draw(st.lists(st.sampled_from(IDS + ["ghost"]), max_size=1))
            target = Action(action_id="new", kind="ORDER", counterparty=MAIN, qty=q, unit_price=price,
                            value=max(Decimal("0.00"), q * price + draw(value_offset)),
                            cited_claims=("gd", "gp", *extra), round=now)
        else:
            refs = [a.action_id for a in prior if a.kind == "ORDER"] or [None]
            target = Action(action_id="new", kind="PAYMENT", counterparty=MAIN,
                            value=max(Decimal("0.00"), draw(st.sampled_from([Decimal(1), Decimal(5), Decimal(10)]))
                                      + draw(value_offset)),
                            cited_claims=("gd", "gp"), round=now, ref_order=draw(st.sampled_from(refs)))
    elif draw(st.booleans()):
        target = draw(order("new", round_=now))
    else:
        refs = [a.action_id for a in prior if a.kind == "ORDER"] + ["ghost", None]
        target = Action(action_id="new", kind="PAYMENT", counterparty=draw(st.sampled_from([MAIN, OTHER])),
                        value=max(Decimal("0.00"), draw(st.sampled_from([Decimal(v) for v in (0, 1, 5, 10, 20, 40)]))
                                  + draw(value_offset)),
                        cited_claims=draw(cites), round=now, ref_order=draw(st.sampled_from(refs)))
    # One-cent offsets straddle every budget boundary (P + inc == B exactly vs one cent over).
    b0 = max(Decimal("0.00"), draw(st.sampled_from([Decimal(v) for v in (0, 5, 10, 20, 25, 50)]))
             + draw(st.sampled_from([Decimal("0.00"), C, -C])))
    gate = build_world(claims, prior, b0=b0, window=draw(st.integers(1, 4)),
                       min_lead={MAIN: draw(st.integers(0, 3)), OTHER: draw(st.integers(0, 3))})
    return gate, target, now


def check(case):
    gate, a, now = case
    ok, why = gate.allow(a, now)
    mok, mwhy = table_verdict(snapshot(gate, a, now))
    assert (ok, why) == (mok, mwhy), f"gate {why} vs monitor {mwhy} for {a!r} at {now}"


_SETTINGS = dict(derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@settings(max_examples=400, **_SETTINGS)
@given(world_and_action())
def test_gate_and_monitor_agree(case):
    check(case)


@pytest.mark.slow
@settings(max_examples=10_000, **_SETTINGS)
@given(world_and_action())
def test_gate_and_monitor_agree_10k(case):
    check(case)


def test_generator_reaches_every_reason_code():
    """The differential test is only as good as its coverage: every row of the table must come up."""
    seen = set()

    @settings(max_examples=3000, **_SETTINGS)
    @given(world_and_action())
    def collect(case):
        gate, a, now = case
        seen.add(gate.allow(a, now)[1])
    collect()
    assert seen >= {"OK", "NO_CITATION", "UNKNOWN_CLAIM", "WRONG_COUNTERPARTY", "BAD_CLAIM", "CLAIM_MISMATCH",
                    "PRICE_MISMATCH", "OVER_CLAIM", "OVERPAY", "OVER_BUDGET"}, seen


def test_regression_sub_cent_money_cannot_exist():
    # Found by the differential test when money was float: the monitor allowed payments up to 1e-6 over the
    # cap (1e-9 in the gate). With exact cents (D19) a 5.00000001 payment can't be constructed at all, the
    # env boundary rounds float noise away by one documented rule, and one cent over the cap is OVERPAY in both.
    with pytest.raises(pydantic.ValidationError):
        Action(action_id="new", kind="PAYMENT", counterparty=MAIN, value=5.00000001, ref_order="s0")
    assert to_money(5.00000001) == Decimal("5.00") and to_money(87.55000000000001) == Decimal("87.55")
    d = Claim.make(claim_id="gd", counterparty=MAIN, source_msg_hash="h", created_round=0, template="DELIVERY",
                   slots={"item": "widget", "qty": 1, "by_round": 3})
    p = Claim.make(claim_id="gp", counterparty=MAIN, source_msg_hash="h", created_round=0, template="PRICE",
                   slots={"item": "widget", "unit_price": 5.0, "valid_until": 3})
    o = Action(action_id="s0", kind="ORDER", counterparty=MAIN, qty=1, unit_price=5.0, value=5.0,
               cited_claims=("gd", "gp"), status="EXECUTED", executed_round=0)
    gate = build_world([d, p], [o], b0=Decimal("5.00"), window=1, min_lead={MAIN: 0})   # P = 5.00 = B
    for value, want in ((Decimal("5.00"), (True, "OK")), (Decimal("5.01"), (False, "OVERPAY"))):
        pay = Action(action_id="new", kind="PAYMENT", counterparty=MAIN, value=value, cited_claims=("gd", "gp"),
                     ref_order="s0")
        assert gate.allow(pay, 0) == want
        assert table_verdict(snapshot(gate, pay, 0)) == want
