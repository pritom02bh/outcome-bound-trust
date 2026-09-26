"""F7: the loss bound. damage = cost(run) - cost(same decisions, every relied-on promise kept) <= sum of L_e.

Scenarios 11-12 arrive in F8; extend SCENARIOS-based tests to all 12 there.
"""
import pytest

from obt import lossbound
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, make_supplier
from obt.env.beer_game import GameConfig
from obt.sim import Sim, SimConfig, loss_from_lies

G = GameConfig()                 # full length, 50 rounds
EPS = 1e-6


def run(n, defense="obt", seed=1, game=G):
    sim = Sim(SimConfig(game=game, defense=defense), seed, make_supplier(n, game, seed), ScriptedClaimBuyer(game))
    return sim, sim.run()


@pytest.fixture(scope="module")
def runs():
    return {n: run(n) for n in sorted(SCENARIOS)}


# ------------------------------------------------------------------ the replay harness itself

@pytest.mark.parametrize("n", sorted(SCENARIOS))
@pytest.mark.parametrize("defense", ["obt", "none"])
def test_replay_with_actual_behaviour_reproduces_cost_exactly(n, defense):
    sim, res = run(n, defense)
    assert lossbound.replay_cost(sim, kept=False) == pytest.approx(res.total_cost, abs=EPS)


# ------------------------------------------------------------------ the bound

@pytest.mark.parametrize("n", sorted(SCENARIOS))
def test_damage_within_sum_of_event_bounds(runs, n):
    sim, res = runs[n]
    lb = res.metrics["loss_bound"]
    assert lb["ok"] and lb["damage"] <= lb["sum_bound"] + EPS, lb
    assert lb["sum_bound"] == pytest.approx(sum(e["bound"] for e in lb["events"]))


def test_honest_has_no_events_and_zero_damage(runs):
    lb = runs[1][1].metrics["loss_bound"]
    assert lb["events"] == [] and lb["sum_bound"] == 0 and abs(lb["damage"]) < EPS


@pytest.mark.parametrize("n", [5, 6, 7])        # price_bait, vague, far_deadlines: no DELIVERY failures
def test_no_delivery_failure_means_zero_damage(runs, n):
    sim, res = runs[n]
    assert not [c for c in sim.ledger if c.template == "DELIVERY" and c.status == "FAILED"]
    assert abs(res.metrics["loss_bound"]["damage"]) < EPS


@pytest.mark.parametrize("n", sorted(SCENARIOS))
def test_every_event_within_budget_corollary(runs, n):
    for e in runs[n][1].metrics["loss_bound"]["events"]:
        assert e["V"] <= e["B_at_order"] + EPS
        assert e["bound"] <= e["apriori"] + EPS, e


def test_hand_computed_single_failure():
    # always_lie: the first S_main order (at b0) is never delivered.
    g = GameConfig(rounds=12)
    sim = Sim(SimConfig(game=g), 1, make_supplier(2, g, 1), ScriptedClaimBuyer(g))
    sim.run()
    events = lossbound.failure_events(sim)
    assert events
    e = events[0]
    assert e.late_units == 0
    p_bk, lead_b, p_b = g.backup_price, g.backup_lead, g.backlog_cost
    assert e.V == pytest.approx(e.shortfall * e.unit_price)
    purchase = e.shortfall * p_bk
    assert lossbound.event_bound(e, g, grace=0) == pytest.approx(
        e.V + e.shortfall * p_b * (0 + lead_b + 1) + e.shortfall * (p_bk - e.unit_price)
        + e.late_units * g.holding_cost * (g.rounds - e.late_arrival + 1 if e.late_arrival else 0))
    assert purchase == pytest.approx(e.V + e.shortfall * (p_bk - e.unit_price))
    # Same decisions: the only purchase difference is the remediation, U_e x backup price per event.
    kept = lossbound.replay_game(sim, kept=True)
    assert sim.game.costs["purchase"] - kept.costs["purchase"] == pytest.approx(
        sum(x.shortfall * p_bk for x in events))
    lb = sim.metrics()["loss_bound"]
    assert 0 < lb["damage"] <= lb["sum_bound"]


def test_late_delivery_needs_the_surplus_term():
    # noisy_honest: slipped shipments fail their claim, get remediated, then arrive anyway.
    sim, res = run(9)
    lb = res.metrics["loss_bound"]
    late = [e for e in lb["events"] if e["late_units"] > 0]
    assert late, "expected late arrivals after resolution"
    without = sum(e["bound"] - e["surplus_term"] for e in lb["events"])
    assert lb["damage"] > without + EPS          # the FIXES form alone is too small here (DECISIONS D21)
    assert lb["damage"] <= lb["sum_bound"] + EPS


# ------------------------------------------------------------------ decomposition

@pytest.mark.parametrize("n", sorted(SCENARIOS))
def test_loss_decomposes(runs, n):
    sim, res = runs[n]
    honest = runs[1][1]
    loss = loss_from_lies(res, honest)
    lb = res.metrics["loss_bound"]
    parts = lossbound.decompose(loss, lb)
    assert parts["damage"] + parts["reroute_cost"] + parts["resid"] == pytest.approx(loss, abs=EPS)


def test_reroute_cost_hand_count_price_bait(runs):
    sim, res = runs[5]
    want = sum(r["qty"] * (G.backup_price - float(r["blocked_unit_price"]))
               for r in sim.reroutes if r["reason"] in ("OVER_BUDGET", "OVER_CLAIM"))
    assert sim.reroutes and res.metrics["loss_bound"]["reroute_cost"] == pytest.approx(want)
    assert any(r["reason"] == "OVER_BUDGET" for r in sim.reroutes)


def test_baselines_have_no_damage_measure_or_bound():
    # Without remediation the kept-promise counterfactual measures overstock, not damage (D21):
    # for always_lie under no defense it would come out at -4,116.5.
    sim, res = run(2, "none")
    lb = res.metrics["loss_bound"]
    assert lb["damage"] is None and lb["sum_bound"] is None and lb["ok"] is None
    assert lossbound.decompose(1000.0, lb)["resid"] is None


# ------------------------------------------------------------------ STOP wiring

def test_violation_stops_the_eval(tmp_path, monkeypatch):
    from eval.run import EvalConfig, LossBoundViolation, run_eval
    monkeypatch.setattr(lossbound, "event_bound", lambda e, g, grace=0: 0.0)
    ec = EvalConfig(buyer="scripted", scenarios=(1, 2), defenses=("obt",), rounds=20, extractor_eval=False)
    with pytest.raises(LossBoundViolation):
        run_eval(ec, tmp_path)
