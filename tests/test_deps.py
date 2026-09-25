from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from obt.budget import BudgetConfig, TrustBudget
from obt.deps import DependencyTracker
from obt.env.oracles import Oracles, Receipt
from obt.gate import Gate
from obt.ledger import ActionLog, Ledger, NoteLog
from obt.types import Action, Claim, Note
from obt.verifier import Verifier

CP = "S_main"


def delivery(cid, created=1, qty=30, by=3):
    return Claim.make(claim_id=cid, counterparty=CP, source_msg_hash="h", created_round=created,
                      template="DELIVERY", slots={"item": "widget", "qty": qty, "by_round": by})


class World:
    def __init__(self, b0=1000.0):
        self.o = Oracles()
        self.led = Ledger()
        self.acts = ActionLog()
        self.notes = NoteLog()
        self.budget = TrustBudget(self.led, self.acts, BudgetConfig(b0=b0, window=3))
        self.gate = Gate(self.led, self.acts, self.budget)

        self.ver = Verifier(self.led, self.o.view)
        self.deps = DependencyTracker(self.led, self.acts, self.notes, self.ver)
        self.events = []
        self.deps.on_failure(self.events.append)
        self.n = 0

    def act(self, qty, cites, now=1):
        self.n += 1
        qty = int(qty)
        # Fresh one-round $1 quote: value == qty, and F2 needs exactly one PRICE claim per order.
        q = f"q{self.n}"
        self.led.append(Claim.make(claim_id=q, counterparty=CP, source_msg_hash="h", created_round=now,
                                   template="PRICE", slots={"item": "widget", "unit_price": 1.0,
                                                            "valid_until": now + 1}))
        return self.gate.submit(Action(action_id=f"a{self.n}", kind="ORDER", counterparty=CP, qty=qty,
                                       unit_price=1.0, value=float(qty), cited_claims=tuple(cites) + (q,),
                                       round=now), now)

    def note(self, cites, now=1):
        self.n += 1
        return self.deps.add_note(Note(note_id=f"n{self.n}", round=now, text="plan", cited_claims=tuple(cites)), now)


def test_failure_flags_citing_actions_and_notes_in_same_step():
    w = World()
    w.led.append(delivery("first", by=3))
    w.led.append(delivery("second", by=3))
    a1 = w.act(10, ["first"])
    a2 = w.act(10, ["first", "second"])
    a3 = w.act(10, ["second"])
    n1 = w.note(["first"])
    n2 = w.note(["second"])
    n3 = w.note([])
    # "first" is owed 20 (a1 + a2 via EDF/id order), "second" 10 (a3): 20 units only cover "first".
    w.o.record_receipt(Receipt(3, CP, "widget", 20, "o"))
    seen_during_step = []
    # A hook registered after the tracker sees the flags already applied.
    w.ver.subscribe(lambda c, now: seen_during_step.append(w.acts[a1.action_id].status))
    w.ver.step(3)
    assert {w.led["first"].status, w.led["second"].status} == {"PASSED", "FAILED"}
    failed = "first" if w.led["first"].status == "FAILED" else "second"
    assert failed == "second"
    for a in (a1, a2, a3):
        rec = w.acts[a.action_id]
        should = failed in a.cited_claims
        assert (rec.status == "FLAGGED") is should
        if should:
            assert rec.was_executed
    notes = {n.note_id: n for n in w.notes}
    assert notes[n2.note_id].flagged and notes[n2.note_id].flagged_round == 3
    assert not notes[n1.note_id].flagged and not notes[n3.note_id].flagged
    assert len(w.events) == 1
    ev = w.events[0]
    assert ev.claim_id == "second" and ev.round == 3
    assert set(ev.actions) == {a2.action_id, a3.action_id} and ev.notes == (n2.note_id,)


def test_pass_flags_nothing_and_blocked_actions_untouched():
    w = World(b0=5)
    w.led.append(delivery("k", by=3))
    ok = w.act(5, ["k"])
    blocked = w.act(50, ["k"])
    assert blocked.status == "BLOCKED"
    w.ver.step(3)
    assert w.led["k"].status == "FAILED"
    assert w.acts[ok.action_id].status == "FLAGGED"
    assert w.acts[blocked.action_id].status == "BLOCKED"


def test_duplicate_citation_flags_once():
    w = World()
    w.led.append(delivery("k", by=2))
    a = w.act(5, ["k", "k"])
    w.ver.step(2)
    assert w.acts[a.action_id].status == "FLAGGED"
    assert w.events[0].actions == (a.action_id,)


def test_note_citing_already_failed_claim_is_flagged_on_entry():
    w = World()
    w.led.append(delivery("k", by=2))
    w.act(5, ["k"])
    w.ver.step(2)
    n = w.note(["k"], now=4)
    assert n.flagged and n.flagged_round == 4


class DepsMachine(RuleBasedStateMachine):
    @initialize()
    def setup(self):
        self.w = World()
        self.now = 1
        self.ids: list[str] = []
        self.k = 0

    @rule(qty=st.integers(1, 20), dt=st.integers(0, 3))
    def offer(self, qty, dt):
        self.k += 1
        cid = f"c{self.k}"
        self.w.led.append(delivery(cid, created=self.now, qty=qty, by=self.now + dt))
        self.ids.append(cid)

    @rule(picks=st.lists(st.integers(0, 999), min_size=1, max_size=3), value=st.floats(0, 50))
    def act(self, picks, value):
        if self.ids:
            self.w.act(value, [self.ids[p % len(self.ids)] for p in picks], now=self.now)

    @rule(picks=st.lists(st.integers(0, 999), max_size=3))
    def note(self, picks):
        cites = [self.ids[p % len(self.ids)] for p in picks] if self.ids else []
        self.w.note(cites, now=self.now)

    @rule(qty=st.integers(1, 20))
    def receipt(self, qty):
        self.w.o.record_receipt(Receipt(self.now, CP, "widget", qty, "o"))

    @rule()
    def tick(self):
        self.now += 1
        self.w.ver.step(self.now)

    @invariant()
    def i4_propagation(self):
        if not hasattr(self, "w"):
            return
        for k in self.w.led:
            if k.status != "FAILED":
                continue
            for a in self.w.acts.citing(k.claim_id):
                if a.was_executed:
                    assert a.status == "FLAGGED"
            for n in self.w.notes.citing(k.claim_id):
                assert n.flagged
                assert n.flagged_round <= max(k.resolved_round, n.round)


DepsMachine.TestCase.settings = settings(max_examples=200, stateful_step_count=50, deadline=None)
test_deps_invariant = DepsMachine.TestCase
