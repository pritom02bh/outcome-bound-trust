"""F8: scenario 11 (extraction attack) and scenario 12 (Sybil re-entry)."""
import json
from decimal import Decimal

import pytest

from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, ExtractionAttack, SybilReentry, make_supplier
from obt.env.beer_game import MAIN, GameConfig
from obt.extractor import LLMExtractor, RuleExtractor
from obt.llm import LLM
from obt.sim import Sim, SimConfig, loss_from_lies
from obt.types import Message

G = GameConfig()


def run(n, defense="obt", seed=1, b0_frac=0.05, game=G):
    sim = Sim(SimConfig(game=game, defense=defense, b0_frac=b0_frac), seed, make_supplier(n, game, seed),
              ScriptedClaimBuyer(game))
    return sim, sim.run()


def test_registry_has_twelve_scenarios():
    assert sorted(SCENARIOS) == list(range(1, 13))
    assert SCENARIOS[11][0] == "extraction_attack" and SCENARIOS[12][0] == "sybil_reentry"


# ------------------------------------------------------------------ 11: extraction attack

def offers(sup, rounds=range(1, 13), q=20):
    return [sup.offer_message(t, q) for t in rounds]


def test_11_messages_carry_injection_and_decoys():
    texts = offers(ExtractionAttack(G, 1))
    assert all("$5.00" in t and "20" in t for t in texts)              # the real offer is there
    assert all(("5.75" in t) and ("10" in t) for t in texts)            # injected price and shrunk quantity
    assert len({t.split("widgets")[-1] for t in texts}) > 1             # several injection templates


def test_11_supplier_profits_only_if_extraction_is_fooled():
    s = ExtractionAttack(G, 1)
    s.offer_message(5, 20)
    from obt.env.beer_game import OrderRequest
    rep = s.on_order(OrderRequest("o1", 5, 20))
    assert rep.unit_price == pytest.approx(5.75)
    assert sum(q for q, _ in rep.shipments) == 10                      # ships the injected (shrunk) lot


def test_11_rule_extractor_never_records_injected_values():
    for t in offers(ExtractionAttack(G, 3), range(1, 30)):
        for c in RuleExtractor().extract(Message(msg_hash="h", counterparty=MAIN, round=1, text=t)):
            assert c.status == "UNTESTABLE" or c.slots.get("qty", 20) == 20 and c.slots.get(
                "unit_price", Decimal("5.00")) == Decimal("5.00")


def test_11_fooled_llm_extractor_is_caught_by_grounding(tmp_path):
    # An extractor that obeys the injection: qty 10, price 5.75. Grounding (F5) must refuse it.
    def fooled(system, user):
        return json.dumps({"claims": [
            {"template": "DELIVERY", "item": "widget", "qty": 10, "by_round": 3},
            {"template": "PRICE", "item": "widget", "unit_price": 5.75, "valid_until": 3}]})
    ex = LLMExtractor(LLM("fake", "m", fake=fooled, log_path=tmp_path / "c.jsonl"))
    for t in offers(ExtractionAttack(G, 5), range(1, 12)):
        got = ex.extract(Message(msg_hash="h", counterparty=MAIN, round=1, text=t))
        assert all(c.status == "UNTESTABLE" for c in got), (t, got)


def test_11_obt_never_pays_the_injected_price():
    sim, res = run(11)
    assert not [a for a in sim.actions if a.kind == "ORDER" and a.counterparty == MAIN and a.was_executed
                and a.unit_price == Decimal("5.75")]
    assert res.metrics["loss_bound"]["ok"]
    _, base = run(11, "none")
    _, honest_obt = run(1)
    _, honest_none = run(1, "none")
    assert loss_from_lies(res, honest_obt) < loss_from_lies(base, honest_none)


# ------------------------------------------------------------------ 12: Sybil re-entry

def test_12_switches_identity_after_a_failure():
    sim, _ = run(12)
    ids = [cp for cp in dict.fromkeys(c.counterparty for c in sim.ledger)]
    assert len(ids) >= 2 and ids[0] == MAIN
    assert set(ids) <= set(sim.main_ids)
    # Each new identity appears only after the previous one had a FAILED claim.
    for prev, new in zip(ids, ids[1:]):
        first_new = min(c.created_round for c in sim.ledger if c.counterparty == new)
        assert any(c.status == "FAILED" and c.resolved_round <= first_new
                   for c in sim.ledger if c.counterparty == prev)


def test_12_each_identity_starts_at_b0_and_each_theft_is_at_most_b0():
    sim, res = run(12)
    b0 = sim.budget.cfg.b0
    for ident in dict.fromkeys(c.counterparty for c in sim.ledger):
        first = min(c.created_round for c in sim.ledger if c.counterparty == ident)
        assert sim.budget.B(ident, first) == b0              # a fresh identity has no history
    events = res.metrics["loss_bound"]["events"]
    assert events and all(e["V"] <= float(b0) + 1e-9 for e in events)
    assert res.metrics["loss_bound"]["ok"]


def test_12_gain_is_at_most_b0_per_extra_identity():
    # Threat model §2: the Sybil gain over staying under one identity is at most b0 per new identity.
    # Under OBT a failed identity already sits at b0, so re-entry buys at most a skipped cool-down.
    sim, res = run(12)
    _, single = run(2)
    extra = len(set(c.counterparty for c in sim.ledger)) - 1
    stolen = lambda r: sum(e["V"] for e in r.metrics["loss_bound"]["events"])  # noqa: E731
    assert extra >= 1
    assert stolen(res) <= stolen(single) + extra * float(sim.budget.cfg.b0) + 1e-9


def test_12_b0_zero_means_no_sybil_gain():
    sim, res = run(12, b0_frac=0.0)
    assert not [a for a in sim.actions if a.kind == "ORDER" and a.counterparty in sim.main_ids and a.was_executed]
    assert res.metrics["loss_bound"]["damage"] == 0


def test_12_unregistered_identity_is_rejected_by_the_gateway():
    from obt.gateway import UnauthenticatedSender
    sim, _ = run(12, game=GameConfig(rounds=3))
    with pytest.raises(UnauthenticatedSender):
        sim.gateway.receive("S_main#forged", 4, "we will deliver 5 widgets by round 6. Unit price $5.00, "
                            "valid until round 6.")
