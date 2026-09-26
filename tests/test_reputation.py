"""F9: the reputation baseline (Beta score over delivery outcomes, probation cold start, D22)."""
from decimal import Decimal

import pytest

from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import MAIN, GameConfig
from obt.reputation import RepConfig, beta_score
from obt.sim import DEFENSES, Sim, SimConfig, loss_from_lies

G = GameConfig()


def run(n, defense="reputation", seed=1, **kw):
    sim = Sim(SimConfig(game=G, defense=defense, **kw), seed, make_supplier(n, G, seed), ScriptedClaimBuyer(G))
    return sim, sim.run()


def main_orders(sim):
    return [a for a in sim.actions if a.kind == "ORDER" and a.counterparty in sim.main_ids]


def test_final_defense_list():
    assert DEFENSES == ("obt", "none", "provenance", "reputation", "llm_selfcheck")


def test_beta_score():
    assert beta_score(0, 0) == pytest.approx(0.5)
    assert beta_score(3, 0) == pytest.approx(0.8)
    assert beta_score(0, 3) == pytest.approx(0.2)


def test_defaults_are_d22():
    c = RepConfig()
    assert (c.theta, c.cap, c.n0) == (0.8, Decimal("200.00"), 3)


def test_newcomer_is_on_probation_with_half_the_cap():
    sim, _ = run(1)
    first = [a for a in main_orders(sim) if a.round <= 3]
    assert first and any(a.was_executed for a in first)
    assert all(a.value <= Decimal("100.00") for a in first if a.was_executed)       # 0.5 x $200


def test_every_executed_order_respects_the_rule():
    for n in (1, 2, 3, 9):
        sim, _ = run(n)
        for a in main_orders(sim):
            if not a.was_executed:
                continue
            s, f = sim.reputation.outcomes(a.counterparty, a.round)
            score = beta_score(s, f)
            assert s + f < 3 or score >= 0.8
            assert a.value <= Decimal(str(score)) * Decimal("200.00") + Decimal("0.01")


def test_liar_is_cut_off_once_failures_resolve():
    # always_lie: after its first failed outcomes the score (1/4 after two) makes every order exceed
    # score x cap, so nothing more executes; the cut-off comes from the cap while still on probation.
    sim, _ = run(2)
    fails = [p["promised"] for p in sim.placements if p["supplier"] == MAIN]
    first_fail = min(fails)
    assert not [a for a in main_orders(sim) if a.was_executed and a.round > first_fail + 1]
    blocked = [a for a in main_orders(sim) if a.status == "BLOCKED"]
    assert blocked and {a.reason for a in blocked} <= {"REP_SCORE", "REP_CAP"}


def test_blocked_quantity_is_rerouted_to_backup():
    sim, _ = run(2)
    assert sim.reroutes and all(r["reason"] in ("REP_SCORE", "REP_CAP") for r in sim.reroutes)


def test_farmed_reputation_is_spent_on_the_big_lie_but_obt_bounds_it():
    # The positioning claim: reputation scores who the counterparty is, so trust farmed with small
    # honest trades can be spent on one large false promise; OBT binds each order to its claims.
    _, rep = run(3, "reputation")
    _, obt = run(3, "obt")
    _, rep_h = run(1, "reputation")
    _, obt_h = run(1, "obt")
    assert loss_from_lies(rep, rep_h) > loss_from_lies(obt, obt_h)


def test_sybil_identities_each_get_probation_under_reputation():
    sim, _ = run(12)
    idents = {a.counterparty for a in main_orders(sim) if a.was_executed}
    assert len(idents) >= 2                           # every fresh identity starts on probation again


def test_all_baselines_see_raw_messages_obt_never_does():
    for d, sees in (("none", True), ("provenance", True), ("reputation", True), ("obt", False)):
        sim = Sim(SimConfig(game=GameConfig(rounds=3), defense=d), 1, make_supplier(1, G, 1), ScriptedClaimBuyer(G))
        sim.run()
        assert bool(sim.view().raw_messages) == sees, d


def test_reputation_view_shows_the_code_computed_limit():
    from obt.memory_view import render
    sim = Sim(SimConfig(game=GameConfig(rounds=4), defense="reputation"), 1, make_supplier(1, G, 1),
              ScriptedClaimBuyer(G))
    sim.run()
    assert "REPUTATION (computed by code)" in render(sim.view())
    assert sim.view().main_id == MAIN
