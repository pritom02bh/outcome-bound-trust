import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from obt.budget import BudgetConfig, TrustBudget
from obt.env.beer_game import BACKUP, GameConfig
from obt.env.oracles import Invoice, Oracles, Receipt
from obt.gate import Gate
from obt.ledger import ActionLog, Ledger
from obt.types import Action, Claim
from obt.verifier import Verifier

CP = "S_main"


def delivery(cid, cp=CP, created=1, qty=10, by=3):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=created,
                      template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by})


class World:
    """Claims go straight to the ledger (F2). `act` cites a fresh one-round $1 quote, so an
    order's value equals its qty and the quote resolves right after (it never earns trust)."""

    def __init__(self, b0=10.0, window=3, cps=(CP, "S_x")):
        self.o = Oracles()
        self.led = Ledger()
        self.acts = ActionLog()
        self.budget = TrustBudget(self.led, self.acts, BudgetConfig(b0=b0, window=window))
        self.gate = Gate(self.led, self.acts, self.budget)
        self.ver = Verifier(self.led, self.o.view)
        self.n = 0

    def act(self, qty, cites, cp=CP, now=1):
        self.n += 1
        if cites and cp != BACKUP:
            q = f"q{self.n}"
            self.led.append(Claim.make(claim_id=q, counterparty=cp, source_msg_hash="h", created_round=now,
                                       template="PRICE", slots={"item": "widget", "unit_price": 1.0,
                                                                "valid_until": now + 1}))
            cites = list(cites) + [q]
        return self.gate.submit(Action(action_id=f"a{self.n}", kind="ORDER", counterparty=cp, qty=int(qty),
                                       unit_price=1.0, value=float(int(qty)), cited_claims=tuple(cites),
                                       round=now), now)


def test_default_b0_is_5pct_of_round_spend():
    assert BudgetConfig.from_game(GameConfig()).b0 == pytest.approx(5.0)


def test_failed_claim_blocks_citation():
    w = World()
    w.led.append(delivery("k", by=2))
    w.act(5, ["k"])
    w.ver.step(2)
    assert w.led["k"].status == "FAILED"
    assert w.act(1, ["k"]).reason == "BAD_CLAIM"


def test_budget_grows_by_honored_claim_and_resets_on_failure():
    w = World(b0=10, window=3)
    w.led.append(delivery("k1", qty=10, by=3))
    w.act(10, ["k1"], now=1)
    w.o.record_receipt(Receipt(3, CP, "widget", 10, "o1"))
    w.ver.step(3)
    assert w.budget.B(CP, 3) == 20            # b0 + largest honored claim
    assert w.budget.pending(CP) == 0
    w.led.append(delivery("k2", created=3, qty=20, by=5))
    w.act(20, ["k2"], now=3)
    w.ver.step(5)                               # not delivered
    assert w.led["k2"].status == "FAILED"
    assert w.budget.B(CP, 5) == 10 and w.budget.B(CP, 7) == 10
    # Window over: history max was cleared, so still only b0.
    assert w.budget.B(CP, 8) == 10


def test_pass_during_cooldown_never_counts():
    w = World(b0=10, window=3)
    w.led.append(delivery("bad", qty=5, by=2))
    w.act(5, ["bad"], now=1)
    w.ver.step(2)                               # fails at round 2; cool-down covers rounds 2..4
    w.led.append(delivery("good", created=2, qty=5, by=4))
    w.act(5, ["good"], now=2)
    w.o.record_receipt(Receipt(4, CP, "widget", 5, "o"))
    w.ver.step(4)
    assert w.led["good"].status == "PASSED"
    assert w.budget.B(CP, 4) == 10 and w.budget.B(CP, 5) == 10
    w.led.append(delivery("later", created=5, qty=8, by=6))
    w.act(8, ["later"], now=5)
    w.o.record_receipt(Receipt(6, CP, "widget", 8, "o"))
    w.ver.step(6)
    assert w.budget.B(CP, 6) == 18


def test_citing_passed_claim_cannot_back_an_order():
    # D2 closed by F2: an order must cite a PENDING DELIVERY claim.
    w = World()
    w.led.append(delivery("k", qty=10, by=2))
    w.act(10, ["k"], now=1)
    w.o.record_receipt(Receipt(2, CP, "widget", 10, "o"))
    w.ver.step(2)
    before = w.budget.B(CP, 2)
    assert w.act(15, ["k"], now=2).reason == "CLAIM_MISMATCH"
    assert w.budget.B(CP, 2) == before and w.led["k"].realized_exposure == 10


class GateMachine(RuleBasedStateMachine):
    """Random interleavings of offers, outcomes, verifier ticks and actions."""

    CPS = (CP, "S_x")

    @initialize(b0=st.sampled_from([1.0, 5.0, 25.0]), window=st.integers(1, 5))
    def setup(self, b0, window):
        self.w = World(b0=b0, window=window)
        self.now = 1
        self.ids: list[str] = []
        self.k = 0

    def _Bs(self):
        return {c: self.w.budget.B(c, self.now) for c in self.CPS}

    def _no_rise(self, before):
        after = self._Bs()
        assert all(after[c] <= before[c] + 1e-9 for c in self.CPS), (before, after)

    @rule(cp=st.sampled_from(CPS), tmpl=st.sampled_from(["DELIVERY", "PRICE", "UNTESTABLE"]),
          qty=st.integers(1, 30), dt=st.integers(0, 4), price=st.sampled_from([4.0, 5.0, 6.0]))
    def new_claim(self, cp, tmpl, qty, dt, price):
        before = self._Bs()
        self.k += 1
        cid = f"c{self.k}"
        if tmpl == "UNTESTABLE":
            c = Claim.untestable(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=self.now)
        elif tmpl == "DELIVERY":
            c = Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=self.now,
                           template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": self.now + dt})
        else:
            c = Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=self.now,
                           template="PRICE",
                           slots={"item": "widget", "unit_price": price, "valid_until": self.now + dt})
        self.w.led.append(c)
        self.ids.append(cid)
        self._no_rise(before)

    @rule(cp=st.sampled_from(CPS), qty=st.integers(1, 30))
    def receipt(self, cp, qty):
        before = self._Bs()
        self.w.o.record_receipt(Receipt(self.now, cp, "widget", qty, "o"))
        self._no_rise(before)

    @rule(cp=st.sampled_from(CPS), price=st.sampled_from([4.0, 5.0, 6.0]))
    def invoice(self, cp, price):
        before = self._Bs()
        self.w.o.record_invoice(Invoice(self.now, cp, "widget", 1, price, "o"))
        self._no_rise(before)

    @rule()
    def tick(self):
        before = self._Bs()
        self.now += 1
        resolved = self.w.ver.step(self.now)
        after = self._Bs()
        for c in self.CPS:
            if after[c] > before[c] + 1e-9:
                # I2: a rise needs a PASSED claim of c in this verifier step.
                assert any(k.counterparty == c and k.status == "PASSED" for k in resolved)

    @rule(cp=st.sampled_from(CPS + (BACKUP,)), value=st.integers(0, 60),
          picks=st.lists(st.integers(0, 10_000), max_size=3), bogus=st.booleans())
    def propose(self, cp, value, picks, bogus):
        before = self._Bs()
        cites = [self.ids[p % len(self.ids)] for p in picks] if self.ids else []
        if bogus:
            cites.append("ghost")
        rec = self.w.act(value, cites, cp=cp, now=self.now)
        self._no_rise(before)
        if rec.status == "EXECUTED" and cp != BACKUP:
            # I1, checked at execution time.
            claims = [self.w.led[k] for k in rec.cited_claims]
            assert claims, "executed without a citation"
            assert all(k.counterparty == cp for k in claims)
            assert all(k.status not in ("FAILED", "UNTESTABLE", "LAPSED") for k in claims)
            assert self.w.budget.pending(cp) <= self.w.budget.B(cp, self.now) + 1e-9

    @invariant()
    def claims_only_enter_ledger_via_allowed_actions_or_directly(self):
        if not hasattr(self, "w"):
            return
        for k in self.w.led:
            assert k.status in ("PENDING", "PASSED", "FAILED", "LAPSED", "UNTESTABLE")
            if k.status == "PASSED":
                assert k.resolved_round is not None


GateMachine.TestCase.settings = settings(max_examples=300, stateful_step_count=60, deadline=None)
test_gate_invariants = GateMachine.TestCase
