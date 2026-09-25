"""F4: remediation happens in code, even when the buyer ignores every block and failure."""
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import BACKUP, MAIN, GameConfig
from obt.sim import Sim, SimConfig

G = GameConfig()


class Stubborn:
    """Orders from S_main every round at a fixed qty, never uses backup, ignores all feedback."""

    def __init__(self, qty, request=None):
        self.qty = qty
        self.request = request or qty

    def act(self, view, api):
        ids = [c.claim_id for c in view.offer if c.template in ("DELIVERY", "PRICE")]
        if ids:
            api.order(MAIN, ids, qty=self.qty)
        api.request(self.request)


def backup_orders(sim, rnd=None):
    return [o for o in sim.game.orders.values() if o.supplier == BACKUP and (rnd is None or o.round == rnd)]


def test_over_budget_block_rerouted_to_backup():
    sim = Sim(SimConfig(), 1, make_supplier(1, G, 1), Stubborn(qty=10))   # $50 > b0 = $5
    row = sim.step()
    main = [a for a in row["actions"] if a[0] == "ORDER" and a[1] == MAIN]
    assert [(a[4], a[5]) for a in main] == [("BLOCKED", "OVER_BUDGET")]
    assert [o.qty for o in backup_orders(sim, 1)] == [10]


def test_over_claim_block_rerouted_to_backup():
    sim = Sim(SimConfig(b0_frac=10.0), 1, make_supplier(1, G, 1), Stubborn(qty=30, request=5))
    sim.step()                         # round 1: default lot 20 < 30
    row = sim.step()                   # round 2: lot 5 < 30
    main = [a for a in row["actions"] if a[0] == "ORDER" and a[1] == MAIN]
    assert [(a[4], a[5]) for a in main] == [("BLOCKED", "OVER_CLAIM")]
    assert [o.qty for o in backup_orders(sim, 2)] == [30]


def test_failed_delivery_shortfall_ordered_from_backup_then_flagged():
    # Scenario 2 never delivers: a $5 (1-unit) order fits b0 and its claim fails at round t+2.
    sim = Sim(SimConfig(), 1, make_supplier(2, G, 1), Stubborn(qty=1, request=1))
    sim.step()                          # round 1: lot 20 > qty 1, $5 order allowed
    first = [a for a in sim.actions if a.kind == "ORDER" and a.counterparty == MAIN and a.was_executed]
    assert first and first[0].round == 1
    sim.step()
    row = sim.step()                    # round 3: claim due, nothing arrived
    failed = [cid for cid, st in row["resolved"] if st == "FAILED"]
    dels = [cid for cid in failed if sim.ledger[cid].template == "DELIVERY"]
    assert dels
    remed = [a for a in row["remediation"] if a[1] == BACKUP]
    assert [a[2] for a in remed] == [sim.ledger[dels[0]].consumed - sim.verifier.allocated(dels[0])] == [1]
    # The shortfall order was placed in phase 4, before the buyer acted this round.
    assert any(o.qty == 1 and o.round == 3 for o in backup_orders(sim))
    # ...and I4 flags still happened in the same step.
    assert sim.actions[first[0].action_id].status == "FLAGGED"
    assert sim.metrics()["shortfall_rerouted_units"] == 1


def test_partial_shortfall_only_reorders_the_missing_units():
    sim = Sim(SimConfig(b0_frac=10.0), 1, make_supplier(4, G, 1), Stubborn(qty=10, request=20))
    rows = [sim.step() for _ in range(20)]
    remed = [(r["round"], a[2]) for r in rows for a in r["remediation"]]
    assert remed
    for rnd, qty in remed:
        cids = [c for c, st in rows[rnd - 1]["resolved"] if st == "FAILED"
                and sim.ledger[c].template == "DELIVERY"]
        assert qty == sum(sim.ledger[c].consumed - sim.verifier.allocated(c) for c in cids)
        assert 0 < qty < 10          # slow drift ships most of the lot


def test_no_code_remediation_under_baselines():
    sim = Sim(SimConfig(defense="none"), 1, make_supplier(2, G, 1), Stubborn(qty=1, request=1))
    rows = [sim.step() for _ in range(5)]
    assert all(r["remediation"] == [] for r in rows)
