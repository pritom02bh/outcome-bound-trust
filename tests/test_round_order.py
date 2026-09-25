"""F1: one fixed round order, recorded per round."""
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import BACKUP, MAIN, ROUND_ORDER, GameConfig
from obt.sim import Sim, SimConfig

G = GameConfig()


def test_round_order_constant_matches_design():
    assert ROUND_ORDER == ("env", "verify", "budget", "remediate", "messages", "propose", "gate", "execute")


def test_one_scripted_round_calls_phases_in_order():
    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), ScriptedClaimBuyer(G))
    row = sim.step()
    assert row["phases"] == list(ROUND_ORDER)
    # Every phase ran against the same round.
    assert {r for _, r in sim.phase_log} == {1}
    assert [p for p, _ in sim.phase_log] == list(ROUND_ORDER)


def test_gate_runs_after_all_proposals_and_before_execution():
    events = []

    class Probe(ScriptedClaimBuyer):
        def act(self, view, api):
            super().act(view, api)
            # Proposals exist but nothing has been decided or sent to the environment yet.
            events.append(("proposed", [a.status for a in api.round_actions], len(sim.game.orders)))

    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), Probe(G))
    row = sim.step()
    assert events[0][0] == "proposed"
    assert set(events[0][1]) == {"PROPOSED"} and events[0][2] == 0
    assert all(a[4] in ("EXECUTED", "BLOCKED") for a in row["actions"])
    assert len(sim.game.orders) == sum(1 for a in row["actions"] if a[4] == "EXECUTED") + row["rerouted_orders"]


def test_later_proposals_see_earlier_allowed_ones_in_the_budget():
    # Two proposals citing the same offer in one round: the second must see the first's exposure.
    class Double(ScriptedClaimBuyer):
        def act(self, view, api):
            ids = [c.claim_id for c in view.offer]
            api.order(MAIN, ids)
            api.order(MAIN, ids)
            api.request(1)

    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), Double(G))
    sim.step()            # round 1: default lot 20 > b0, both blocked
    sim.step()            # round 2: lot 1 at $5 == b0
    acts = [a for a in sim.actions if a.round == 2 and a.counterparty == MAIN]
    assert [a.status for a in acts] == ["EXECUTED", "BLOCKED"]
    assert acts[1].reason == "OVER_BUDGET"


def test_blocked_order_rerouted_to_backup_same_round():
    class Greedy(ScriptedClaimBuyer):
        def act(self, view, api):
            api.order(MAIN, [c.claim_id for c in view.offer])   # 20-unit default lot, over b0
            api.request(20)

    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), Greedy(G))
    row = sim.step()
    assert [a[4] for a in row["actions"] if a[1] == MAIN] == ["BLOCKED"]
    backup = [o for o in sim.game.orders.values() if o.supplier == BACKUP]
    assert [o.qty for o in backup] == [20] and row["rerouted_orders"] == 1


def test_invoices_posted_at_start_of_next_round():
    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), ScriptedClaimBuyer(G))
    sim.step()
    assert sim.game.orders and sim.game.oracles.all_invoices() == ()
    sim.step()
    assert {i.round for i in sim.game.oracles.all_invoices()} == {1}
