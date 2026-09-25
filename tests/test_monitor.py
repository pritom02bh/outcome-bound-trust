"""F6: runtime invariant monitors. Clean runs have 0 violations; each tamper trips its invariant."""
import dataclasses

import pytest

from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, make_supplier
from obt.env.beer_game import MAIN, GameConfig
from obt.gate import Gate
from obt.sim import Sim, SimConfig

G = GameConfig(rounds=25)


def sim_for(n=1, defense="obt", seed=1, **cfg):
    return Sim(SimConfig(game=G, defense=defense, **cfg), seed, make_supplier(n, G, seed), ScriptedClaimBuyer(G))


def kinds(sim):
    return {v["invariant"] for v in sim.monitor.violations}


@pytest.mark.parametrize("n", sorted(SCENARIOS))
@pytest.mark.parametrize("defense", ["obt", "none"])
def test_clean_runs_have_zero_violations(n, defense):
    r = sim_for(n, defense).run()
    assert r.metrics["invariant_violations"]["count"] == 0, r.metrics["invariant_violations"]["details"]


def test_monitor_checks_every_phase():
    sim = sim_for()
    sim.step()
    assert [p for p, _ in sim.monitor.checked] == ["env", "verify", "budget", "remediate", "messages",
                                                    "propose", "gate", "execute"]


# ------------------------------------------------------------------ tamper tests

def test_i1_gate_skipping_budget_row_is_caught(monkeypatch):
    real = Gate.allow

    def lax(self, a, now):
        ok, why = real(self, a, now)
        return (True, "OK") if why == "OVER_BUDGET" else (ok, why)
    monkeypatch.setattr(Gate, "allow", lax)
    sim = sim_for(2)
    sim.run()
    assert kinds(sim) == {"I1"}


def test_i1_gate_skipping_capacity_row_is_caught(monkeypatch):
    real = Gate.allow

    def lax(self, a, now):
        ok, why = real(self, a, now)
        return (True, "OK") if why == "OVER_CLAIM" else (ok, why)
    monkeypatch.setattr(Gate, "allow", lax)

    class Grabby(ScriptedClaimBuyer):
        def act(self, view, api):
            ids = [c.claim_id for c in view.offer if c.template]
            if ids:
                api.order(MAIN, ids, qty=500)
            api.request(1)

    sim = Sim(SimConfig(game=G, b0_frac=1000.0), 1, make_supplier(1, G, 1), Grabby(G))
    sim.run()
    assert "I1" in kinds(sim)


def test_i2_budget_rising_outside_verifier_is_caught():
    sim = sim_for()
    real = sim.phase_messages

    def bump():
        real()
        if sim.game.round == 5:
            sim.budget.cfg = dataclasses.replace(sim.budget.cfg, b0=sim.budget.cfg.b0 + 50)
    sim.phase_messages = bump
    sim.run()
    assert kinds(sim) == {"I2"}


def test_i3_status_change_outside_verifier_is_caught():
    sim = sim_for()
    real = sim.phase_propose

    def rogue():
        real()
        if sim.game.round == 4:
            # An unconsumed offer lapsed by someone other than the verifier, mid-round.
            k = next(c for c in sim.ledger if c.status == "PENDING" and c.consumed == 0)
            sim.ledger.resolve(k.claim_id, "LAPSED", sim.game.round, sim.verifier._key)
    sim.phase_propose = rogue
    sim.run()
    assert kinds(sim) == {"I3"}


def test_i4_missing_flags_are_caught():
    sim = sim_for(2)
    sim.deps.process = lambda resolved, now: []
    sim.run()
    assert kinds(sim) == {"I4"}


def test_i6_over_consumption_is_caught():
    sim = sim_for()
    real = sim.phase_execute

    def overfill():
        real()
        if sim.game.round == 6:
            k = next(c for c in sim.ledger if c.status == "PENDING" and c.template == "DELIVERY")
            # Bypass Claim.with_consumption's own check, as a buggy gate might.
            object.__setattr__(k, "consumed", k.slots["qty"] + 3)
    sim.phase_execute = overfill
    sim.run()
    assert "I6" in kinds(sim) and "I2" not in kinds(sim)


def test_i7_double_credit_is_caught():
    sim = sim_for()
    v = sim.verifier
    real = v._allocate_new_receipts

    def double(now):
        before = len(v._credits)
        real(now)
        v._credits.extend(v._credits[before:])     # every new unit credited twice
    v._allocate_new_receipts = double
    sim.run()
    assert "I7" in kinds(sim)


def test_violations_land_in_metrics():
    sim = sim_for(2)
    sim.deps.process = lambda resolved, now: []
    m = sim.run().metrics["invariant_violations"]
    assert m["count"] == len(sim.monitor.violations) > 0
    assert m["details"][0]["invariant"] == "I4" and {"round", "phase", "detail"} <= set(m["details"][0])
