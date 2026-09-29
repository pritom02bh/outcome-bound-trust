"""D32: the code order planner. The LLM gives only a desired total quantity; code sizes and cites the S_main order."""
import json
from decimal import Decimal

import eval.run as er
from eval.run import EvalConfig
from obt.agent import LLMBuyer, ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import BACKUP, GameConfig
from obt.llm import LLM
from obt.planner import plan_obt, plan_reputation
from obt.sim import Sim, SimConfig

G = GameConfig()


class Api:
    def __init__(self, pending=Decimal("0")):
        self.orders, self.req, self._p = [], None, pending

    def order(self, cp, cited_claims=(), qty=0):
        self.orders.append((cp, tuple(cited_claims), qty))
        return None

    def pending(self):
        return self._p

    def request(self, q):
        self.req = q


def view_after(rounds, defense="obt", **kw):
    g = GameConfig(rounds=rounds)
    s = Sim(SimConfig(game=g, defense=defense, **kw), 1, make_supplier(1, g, 1), ScriptedClaimBuyer(g))
    s.run()
    return s.view()


def test_obt_planner_orders_only_when_nothing_is_pending():
    v = view_after(6)
    tr = v.track[v.main_id]
    api = Api()
    plan_obt(v, 30, api, G)
    if tr.pending_exposure > 0:
        assert all(cp == BACKUP for cp, _, _ in api.orders) and sum(q for *_, q in api.orders) == 30


def test_obt_planner_sizes_to_headroom_capacity_and_desire_and_cites_the_offer():
    v = view_after(1)                                   # round 1: nothing pending, B = b0
    tr = v.track[v.main_id]
    assert tr.pending_exposure == 0
    dels = [c for c in v.offer if c.template == "DELIVERY"]
    price = next(c.slot("unit_price") for c in v.offer if c.template == "PRICE")
    api = Api()
    plan_obt(v, 30, api, G)
    main = [o for o in api.orders if o[0] == v.main_id]
    want = min(30, int(tr.headroom // Decimal(str(price))), sum(c.remaining for c in dels))
    assert main == [(v.main_id, tuple(c.claim_id for c in dels) + tuple(c.claim_id for c in v.offer
                                                                       if c.template == "PRICE"), want)]
    assert [o for o in api.orders if o[0] == BACKUP] == ([(BACKUP, (), 30 - want)] if 30 - want else [])
    assert api.req is not None and api.req >= 1


def test_reputation_planner_stays_within_the_allowed_value():
    v = view_after(10, "reputation", rep_theta=0.8)
    score, n, limit = v.reputation
    api = Api()
    plan_reputation(v, 40, api, G)
    main = sum(q for cp, _, q in api.orders if cp == v.main_id)
    assert main * G.main_price <= float(limit) + 1e-9
    assert main + sum(q for cp, _, q in api.orders if cp == BACKUP) == 40


def fake_llm(total):
    def f(system, user):
        if "checkable claims" in system:
            return json.dumps({"claims": []})
        return json.dumps({"s_main_order": None, "backup_qty": total, "next_lot_request": 1, "note": "",
                           "note_cites": []})
    return f


def test_planner_run_grows_trust_like_the_scripted_buyer_and_keeps_every_invariant():
    from obt.extractor import RuleExtractor
    g = GameConfig(rounds=30)
    s = Sim(SimConfig(game=g, defense="obt"), 1, make_supplier(1, g, 1),
            LLMBuyer(LLM("fake", "f", fake=fake_llm(20)), g, "obt", planner=True), extractor=RuleExtractor())
    res = s.run()
    assert res.metrics["invariant_violations"]["count"] == 0
    assert s.trace[-1]["B"] > 5 * s.trace[0]["B"]         # trust grows (E2's LLM buyer stayed at $10)
    assert all(a[0] != "ORDER" or not a[1].startswith("S_main") or a[4] == "EXECUTED"
               for t in s.trace for a in t["actions"])   # the planner never proposes an order the gate blocks


def test_obt_planner_variant_is_its_own_defense():
    ec = EvalConfig()
    assert er.base_defense("obt+planner") == "obt" and er.variant_opts("obt+planner") == {"planner": True}
    assert er.variant_opts("obt") == {}
    assert er.config_hash(ec, "obt+planner") != er.config_hash(ec, "obt")
