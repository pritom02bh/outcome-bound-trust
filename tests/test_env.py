import pytest

from obt.agent import base_stock, run_plain
from obt.env.beer_game import (BACKUP, MAIN, BackupSupplier, BeerGame, GameConfig, HonestSupplier,
                               demand_series)
from obt.env.oracles import Invoice, OracleView, Receipt

CFG = GameConfig()


def test_honest_scripted_rerun_identical_cost():
    costs = [run_plain(CFG, seed=7, main=HonestSupplier(CFG, 7)).total_cost for _ in range(3)]
    assert costs[0] == costs[1] == costs[2]
    g1 = run_plain(CFG, seed=7, main=HonestSupplier(CFG, 7))
    g2 = run_plain(CFG, seed=7, main=HonestSupplier(CFG, 7))
    assert g1.costs == g2.costs
    assert [(h.demand, h.inventory, h.backlog) for h in g1.history] == \
           [(h.demand, h.inventory, h.backlog) for h in g2.history]
    assert g1.oracles.receipts() == g2.oracles.receipts()


def test_seeds_change_demand():
    assert demand_series(CFG, 1) != demand_series(CFG, 2)
    assert demand_series(CFG, 1) == demand_series(CFG, 1)
    assert len(demand_series(CFG, 1)) == CFG.rounds


def test_cost_accounting_by_hand():
    cfg = GameConfig(rounds=4, init_inventory=5, holding_cost=1.0, backlog_cost=3.0,
                     main_price=2.0, main_lead=1)
    g = BeerGame(cfg, 0, {MAIN: HonestSupplier(cfg), BACKUP: BackupSupplier(cfg)})
    g.demand = [3, 4, 0, 2]
    st = g.begin_round()                       # r1: inv 5 -> 2, hold 2
    assert (st.inventory, st.backlog) == (2, 0)
    o1 = g.place_order(MAIN, 10, 2)            # invoice 20, nothing charged yet (D14); arrives r2
    assert g.costs["purchase"] == 0 and g.posted_invoices == []
    st = g.begin_round()                       # r2: +10 -> 12, -4 -> 8, hold 8; invoice posted
    assert st.arrived == {MAIN: 10} and st.inventory == 8
    assert [i.order_id for i in g.posted_invoices] == [o1.order_id]
    g.pay_invoice(o1.order_id, 15)             # capped payment: 5 stays unpaid
    assert g.costs["purchase"] == 15 and g.unpaid_total == 5
    with pytest.raises(ValueError):
        g.pay_invoice(o1.order_id, 6)          # can't pay more than invoiced
    g.demand[2] = 11
    st = g.begin_round()                       # r3: 8 - 11 -> backlog 3, cost 9
    assert (st.inventory, st.backlog) == (0, 3)
    o2 = g.place_order(BACKUP, 4, 6)           # invoice 24, arrives r6 (after horizon)
    st = g.begin_round()                       # r4: backlog 3 + 2 = 5, cost 15
    assert st.backlog == 5
    g.pay_invoice(o2.order_id, 24)
    assert g.costs == {"purchase": 15 + 24, "holding": 2 + 8, "backlog": 9 + 15}
    assert g.total_cost == 73
    with pytest.raises(RuntimeError):
        g.begin_round()


def test_oracles_record_and_view_is_read_only():
    g = run_plain(CFG, seed=3, main=HonestSupplier(CFG, 3))
    view = g.oracles
    assert isinstance(view, OracleView)
    assert not any(n.startswith("record") for n in dir(view))
    with pytest.raises(AttributeError):
        view.x = 1
    rec = view.receipts()
    assert rec and all(isinstance(r, Receipt) for r in rec)
    inv = view.all_invoices()
    assert inv and all(isinstance(i, Invoice) and i.unit_price == CFG.main_price for i in inv)
    r0 = rec[0]
    assert view.received(MAIN, "widget", r0.round - 1, r0.round) >= r0.qty
    assert view.received(MAIN, "widget", r0.round, r0.round) == 0
    i0 = inv[0]
    assert i0 in view.invoices(MAIN, "widget", i0.round, i0.round + 1)
    assert i0 not in view.invoices(MAIN, "widget", i0.round + 1, i0.round + 5)


def test_honest_main_cheaper_than_backup_only():
    main = run_plain(CFG, 11, HonestSupplier(CFG, 11), supplier=MAIN).total_cost
    backup = run_plain(CFG, 11, HonestSupplier(CFG, 11), supplier=BACKUP).total_cost
    assert main < backup


def test_honest_supplier_offer_mentions_terms():
    s = HonestSupplier(CFG, 0)
    txt = s.offer_message(5, 17)
    assert "17" in txt and "7" in txt and "5.00" in txt
    assert base_stock(CFG, 2) > base_stock(CFG, 0)
