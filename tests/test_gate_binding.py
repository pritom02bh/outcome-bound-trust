"""F2: claim-action binding, capacity, LAPSED, gated payments."""
import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from obt.budget import BudgetConfig, TrustBudget
from obt.env.beer_game import BACKUP
from obt.env.oracles import Invoice, Oracles, Receipt
from obt.gate import Gate
from obt.ledger import ActionLog, Ledger
from obt.types import Action, Claim, IllegalTransition
from obt.verifier import Verifier

CP = "S_main"


class World:
    def __init__(self, b0=1000.0, window=3, min_lead=0):
        self.o = Oracles()
        self.led = Ledger()
        self.acts = ActionLog()
        self.budget = TrustBudget(self.led, self.acts, BudgetConfig(b0=b0, window=window))
        self.gate = Gate(self.led, self.acts, self.budget, min_lead={CP: min_lead})
        self.ver = Verifier(self.led, self.o.view)
        self.n = 0

    def d(self, cid, qty=10, by=5, created=1, cp=CP):
        self.led.append(Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                                   template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by}))

    def p(self, cid, price=5.0, until=5, created=1, cp=CP):
        self.led.append(Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                                   template="PRICE", slots={"item": "widget", "unit_price": price,
                                                            "valid_until": until}))

    def order(self, qty, cites, price=5.0, now=1, cp=CP):
        self.n += 1
        a = Action(action_id=f"a{self.n}", kind="ORDER", counterparty=cp, qty=qty, unit_price=price,
                   value=qty * price, cited_claims=tuple(cites), round=now)
        return self.gate.decide(a, now)

    def pay(self, ref, amount, cites, now=2, cp=CP):
        self.n += 1
        a = Action(action_id=f"a{self.n}", kind="PAYMENT", counterparty=cp, value=amount,
                   cited_claims=tuple(cites), round=now, ref_order=ref)
        return self.gate.decide(a, now)


def fresh(**kw):
    w = World(**kw)
    w.d("d1", qty=10, by=5)
    w.p("p1", price=5.0, until=5)
    return w


# ------------------------------------------------------------------ reason codes, in table order

def test_backup_always_ok():
    w = World(b0=0)
    a = Action(action_id="b", kind="ORDER", counterparty=BACKUP, qty=500, value=3000)
    assert w.gate.allow(a, 1) == (True, "OK")


def test_no_citation():
    assert fresh().order(1, []).reason == "NO_CITATION"


def test_unknown_claim_never_raises():
    w = fresh()
    assert w.order(1, ["d1", "p1", "nope"]).reason == "UNKNOWN_CLAIM"
    assert w.pay("a1", 1, ["ghost"]).reason == "UNKNOWN_CLAIM"


def test_wrong_counterparty():
    w = fresh()
    w.d("x", cp="S_other")
    assert w.order(1, ["d1", "p1", "x"]).reason == "WRONG_COUNTERPARTY"


@pytest.mark.parametrize("kind", ["FAILED", "UNTESTABLE", "LAPSED"])
def test_bad_claim(kind):
    w = fresh()
    if kind == "UNTESTABLE":
        w.led.append(Claim.untestable(claim_id="bad", counterparty=CP, source_msg_hash="h", created_round=1))
    else:
        w.d("bad", by=2)
        if kind == "FAILED":
            w.order(1, ["bad", "p1"])
        w.ver.step(2)
        assert w.led["bad"].status == kind
    assert w.order(1, ["d1", "p1", "bad"], now=2).reason == "BAD_CLAIM"


def test_claim_mismatch_no_delivery_claim():
    assert fresh().order(1, ["p1"]).reason == "CLAIM_MISMATCH"


def test_claim_mismatch_passed_only_citation():
    # D2 closed: an old PASSED claim can't back a new order.
    w = fresh()
    w.d("old", qty=5, by=2)
    w.p("oldp", until=3)
    assert w.order(5, ["old", "oldp"]).status == "EXECUTED"
    w.o.record_receipt(Receipt(2, CP, "widget", 5, "o"))
    w.ver.step(2)
    assert w.led["old"].status == "PASSED"
    assert w.order(1, ["old", "p1"], now=2).reason == "CLAIM_MISMATCH"


def test_claim_mismatch_by_round_before_min_lead():
    w = World(min_lead=2)
    w.d("soon", by=2)          # created round 1: by_round - now = 1 < 2
    w.d("ok", by=3)
    w.p("p1", until=5)
    assert w.order(1, ["soon", "p1"]).reason == "CLAIM_MISMATCH"
    assert w.order(1, ["ok", "p1"]).status == "EXECUTED"


@pytest.mark.parametrize("case", ["none", "two", "expired", "not_yet", "wrong_price"])
def test_price_mismatch(case):
    w = World()
    w.d("d1", by=6)
    cites, price, now = ["d1"], 5.0, 2
    if case == "two":
        w.p("pa", until=6)
        w.p("pb", until=6)
        cites += ["pa", "pb"]
    elif case == "expired":
        w.p("pa", until=2)
        cites += ["pa"]
    elif case == "not_yet":
        w.p("pa", created=3, until=6)
        cites += ["pa"]
    elif case == "wrong_price":
        w.p("pa", price=4.0, until=6)
        cites += ["pa"]
    assert w.order(1, cites, price=price, now=now).reason == "PRICE_MISMATCH"


def test_over_claim_regression_small_claim_large_order():
    # The v1 hole: a 1-unit claim backing a 50-unit order.
    w = World()
    w.d("tiny", qty=1)
    w.p("p1")
    rec = w.order(50, ["tiny", "p1"])
    assert rec.status == "BLOCKED" and rec.reason == "OVER_CLAIM"
    assert w.led["tiny"].consumed == 0 and w.led["tiny"].realized_exposure == 0


def test_capacity_never_shared_twice():
    w = fresh()
    assert w.order(6, ["d1", "p1"]).status == "EXECUTED"
    assert w.order(5, ["d1", "p1"]).reason == "OVER_CLAIM"      # only 4 left
    assert w.order(4, ["d1", "p1"]).status == "EXECUTED"
    assert w.led.remaining("d1") == 0
    assert w.order(1, ["d1", "p1"]).reason == "OVER_CLAIM"


def test_edf_consumption_and_exposure():
    w = World()
    w.d("late", qty=10, by=6)
    w.d("early", qty=4, by=4)
    w.p("p1", price=5.0, until=6)
    assert w.order(7, ["late", "early", "p1"]).status == "EXECUTED"
    assert (w.led["early"].consumed, w.led["late"].consumed) == (4, 3)
    assert w.led["early"].realized_exposure == 20 and w.led["late"].realized_exposure == 15
    assert w.led["p1"].consumed == 7 and w.led["p1"].realized_exposure == 0


def test_overpay():
    w = fresh()
    o = w.order(4, ["d1", "p1"])
    assert w.pay("nope", 1, ["d1", "p1"]).reason == "OVERPAY"
    blocked = w.order(100, ["d1", "p1"])
    assert w.pay(blocked.action_id, 1, ["d1", "p1"]).reason == "OVERPAY"
    assert w.pay(o.action_id, 20.01, ["d1", "p1"]).reason == "OVERPAY"
    assert w.pay(o.action_id, 15, ["d1", "p1"]).status == "EXECUTED"
    assert w.pay(o.action_id, 6, ["d1", "p1"]).reason == "OVERPAY"       # cumulative 21 > 20
    assert w.pay(o.action_id, 5, ["d1", "p1"]).status == "EXECUTED"


def test_over_budget_and_payment_adds_no_exposure():
    w = fresh(b0=20)
    o = w.order(4, ["d1", "p1"])                     # $20 == B
    assert o.status == "EXECUTED"
    assert w.order(1, ["d1", "p1"]).reason == "OVER_BUDGET"
    assert w.pay(o.action_id, 20, ["d1", "p1"]).status == "EXECUTED"
    assert w.budget.pending(CP) == 20


# ------------------------------------------------------------------ LAPSED

def test_unused_claims_lapse_and_do_not_move_budget():
    w = fresh(b0=7)
    before = w.budget.B(CP, 5)
    w.ver.step(5)
    assert w.led["d1"].status == "LAPSED" and w.led["p1"].status == "LAPSED"
    assert w.budget.B(CP, 5) == before and w.budget.last_failure(CP) is None


def test_lapsed_only_when_nothing_consumed():
    c = Claim.make(claim_id="k", counterparty=CP, source_msg_hash="h", created_round=1, template="DELIVERY",
                   slots={"item": "widget", "qty": 5, "by_round": 3})
    assert c.with_status("LAPSED", 3).status == "LAPSED"
    with pytest.raises(IllegalTransition):
        c.with_consumption(1, 5.0).with_status("LAPSED", 3)
    with pytest.raises(IllegalTransition):
        c.with_status("LAPSED", 3).with_status("PASSED", 4)


def test_obligation_is_consumed_qty():
    w = fresh(b0=1000)
    w.order(3, ["d1", "p1"])
    w.o.record_receipt(Receipt(4, CP, "widget", 3, "o"))
    w.ver.step(5)
    assert w.led["d1"].status == "PASSED"           # owed 3 of the 10 offered
    assert w.budget.B(CP, 5) == 1000 + 15


# ------------------------------------------------------------------ capacity property

class CapacityMachine(RuleBasedStateMachine):
    @initialize(b0=st.sampled_from([5.0, 50.0, 500.0]), lead=st.integers(0, 2))
    def setup(self, b0, lead):
        self.w = World(b0=b0, min_lead=lead)
        self.now = 1
        self.ids: list[str] = []
        self.orders: list[str] = []
        self.k = 0

    def _Bs(self):
        return self.w.budget.B(CP, self.now)

    @rule(tmpl=st.sampled_from(["D", "P", "U"]), qty=st.integers(1, 20), dt=st.integers(0, 4),
          price=st.sampled_from([4.0, 5.0]))
    def claim(self, tmpl, qty, dt, price):
        self.k += 1
        cid = f"c{self.k}"
        if tmpl == "D":
            self.w.d(cid, qty=qty, by=self.now + dt, created=self.now)
        elif tmpl == "P":
            self.w.p(cid, price=price, until=self.now + dt, created=self.now)
        else:
            self.w.led.append(Claim.untestable(claim_id=cid, counterparty=CP, source_msg_hash="h",
                                               created_round=self.now))
        self.ids.append(cid)

    @rule(qty=st.integers(0, 40), picks=st.lists(st.integers(0, 999), max_size=4),
          price=st.sampled_from([4.0, 5.0]))
    def order(self, qty, picks, price):
        cites = [self.ids[p % len(self.ids)] for p in picks] if self.ids else []
        before = self._Bs()
        rec = self.w.order(qty, cites, price=price, now=self.now)
        assert self._Bs() <= before
        if rec.status == "EXECUTED":
            self.orders.append(rec.action_id)
            dels = [self.w.led[k] for k in rec.cited_claims if self.w.led[k].template == "DELIVERY"]
            assert dels and all(k.status == "PENDING" for k in dels)
            assert self.w.budget.pending(CP) <= self.w.budget.B(CP, self.now) + 1e-9

    @rule(pick=st.integers(0, 999), amount=st.floats(0, 200, allow_nan=False))
    def pay(self, pick, amount):
        if not self.orders:
            return
        ref = self.orders[pick % len(self.orders)]
        o = self.w.acts[ref]
        self.w.pay(ref, amount, list(o.cited_claims), now=self.now)
        paid = sum(a.value for a in self.w.acts if a.kind == "PAYMENT" and a.ref_order == ref and a.was_executed)
        assert paid <= o.qty * o.unit_price + 1e-9

    @rule(qty=st.integers(1, 20))
    def receipt(self, qty):
        self.w.o.record_receipt(Receipt(self.now, CP, "widget", qty, "o"))

    @rule(price=st.sampled_from([4.0, 5.0, 6.0]))
    def invoice(self, price):
        self.w.o.record_invoice(Invoice(self.now, CP, "widget", 1, price, "o"))

    @rule()
    def tick(self):
        before = self._Bs()
        self.now += 1
        resolved = self.w.ver.step(self.now)
        if self._Bs() > before + 1e-9:
            assert any(k.status == "PASSED" for k in resolved)

    @invariant()
    def capacity(self):
        if not hasattr(self, "w"):
            return
        for k in self.w.led:
            if k.template == "DELIVERY":
                assert 0 <= k.consumed <= k.slots["qty"]
            if k.status == "LAPSED":
                assert k.consumed == 0


CapacityMachine.TestCase.settings = settings(max_examples=250, stateful_step_count=60, deadline=None)
test_capacity_invariant = CapacityMachine.TestCase
