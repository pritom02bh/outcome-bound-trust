from decimal import Decimal
import json
import re

from obt.agent import LLMBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import BACKUP, MAIN, GameConfig
from obt.llm import LLM
from obt.sim import Sim, SimConfig
from tests.test_extractor_view import CANARIES, InjectionSupplier

G = GameConfig()


def offer_ids(user):
    return re.findall(r"\[(S_main#\d+\.\d+)\] (?:DELIVERY|PRICE)", user.split("RECENT S_main CLAIMS")[0])


def decision(cite=(), qty=0, backup=10, lot=20, **extra):
    d = {"s_main_order": {"cite": list(cite), "qty": qty} if (cite or qty) else None,
         "backup_qty": backup, "next_lot_request": lot, "note": "n", "note_cites": list(cite)[:1]}
    d.update(extra)
    return json.dumps(d)


def make(tmp_path, fn, defense="obt", supplier=None, rounds=None):
    cfg = G if rounds is None else GameConfig(rounds=rounds)
    llm = LLM("fake", "fake", fake=fn, log_path=tmp_path / "calls.jsonl")
    buyer = LLMBuyer(llm, cfg, defense)
    sim = Sim(SimConfig(game=cfg, defense=defense), 1, supplier or make_supplier(1, cfg, 1), buyer)
    return sim, buyer


def main_actions(sim):
    return [a for a in sim.actions if a.counterparty == MAIN and a.kind == "ORDER"]


def backup_orders(sim):
    return [a for a in sim.actions if a.counterparty == BACKUP and a.kind == "ORDER"]


def test_obt_qty_capped_by_claims_and_value_never_from_llm(tmp_path):
    def fn(system, user):
        rnd = int(re.search(r"ROUND (\d+)", user).group(1))
        # Round 1: try to inflate far past the offered capacity. Later: 1 unit, plus smuggled fields.
        qty = 999 if rnd == 1 else 1
        return decision(offer_ids(user), qty=qty, backup=0, lot=1, value=0.01, trust_budget=1e9)
    sim, _ = make(tmp_path, fn, rounds=3)
    sim.run()
    acts = main_actions(sim)
    assert acts[0].status == "BLOCKED" and acts[0].reason == "OVER_CLAIM"
    execd = [a for a in acts if a.was_executed]
    assert execd
    for a in execd:
        price = [sim.ledger[k] for k in a.cited_claims if sim.ledger[k].template == "PRICE"][0]
        assert a.unit_price == price.slots["unit_price"] and a.value == a.qty * a.unit_price
    assert sim.budget.B(MAIN, sim.game.round) <= Decimal("5.00") + max(a.value for a in execd)


def test_block_is_rerouted_by_code_not_llm(tmp_path):
    calls = []

    def fn(system, user):
        calls.append(user)
        return decision(offer_ids(user), qty=20, backup=0, lot=100)   # $100, way over b0
    sim, buyer = make(tmp_path, fn, rounds=3)
    sim.run()
    blocked = [a for a in main_actions(sim) if a.status == "BLOCKED"]
    assert blocked and all(a.reason == "OVER_BUDGET" for a in blocked)
    assert buyer.stats["replans"] == 0 and not any("BLOCKED with reason" in u for u in calls)
    backups = [o for o in sim.game.orders.values() if o.supplier == BACKUP]
    assert [(o.round, o.qty) for o in backups] == [(b.round, b.qty) for b in blocked]
    assert {a.reason for a in backup_orders(sim)} == {"OK"}


def test_unparseable_output_falls_back_to_backup(tmp_path):
    sim, buyer = make(tmp_path, lambda s, u: "I think we should order some widgets!", rounds=4)
    sim.run()
    assert buyer.stats["parse_failures"] == 4
    assert not main_actions(sim)
    assert any(a.counterparty == BACKUP for a in sim.actions)


def test_cannot_cite_untestable_or_foreign_ids(tmp_path):
    def fn(system, user):
        if "BLOCKED with reason" in user:
            return json.dumps({"backup_qty": 0})
        return decision(["S_main#1.9", "S_backup#1.1"], backup=0)
    sim, _ = make(tmp_path, fn, rounds=2)
    sim.run()
    assert {a.reason for a in main_actions(sim)} == {"UNKNOWN_CLAIM"}


def test_selfcheck_veto_blocks_main_order(tmp_path):
    def fn(system, user):
        if "procurement auditor" in system:
            return json.dumps({"trustworthy": False, "reason": "no"})
        if "BLOCKED with reason" in user:
            return json.dumps({"backup_qty": 7})
        return decision(qty=20, backup=0)
    sim, buyer = make(tmp_path, fn, defense="llm_selfcheck", rounds=3)
    sim.run()
    acts = main_actions(sim)
    assert acts and all(a.status == "BLOCKED" and a.reason == "SELF_CHECK" for a in acts)
    assert buyer.stats["selfcheck_vetoes"] == 3
    assert [a.qty for a in backup_orders(sim)] == [7, 7, 7]


def test_no_defense_orders_by_qty_ungated(tmp_path):
    sim, _ = make(tmp_path, lambda s, u: decision(qty=40, backup=0), defense="none", rounds=3)
    sim.run()
    acts = main_actions(sim)
    assert [a.qty for a in acts] == [40, 40, 40] and all(a.reason == "UNGATED" for a in acts)


def test_llm_prompt_has_no_raw_text_under_obt(tmp_path):
    for defense, leaks in (("obt", False), ("none", True), ("llm_selfcheck", True)):
        seen = []

        def fn(system, user):
            seen.append(system + user)
            if "procurement auditor" in system:
                return json.dumps({"trustworthy": True, "reason": ""})
            return decision(offer_ids(user), qty=5, backup=10)
        sim, _ = make(tmp_path, fn, defense=defense, supplier=InjectionSupplier(G, 3), rounds=6)
        sim.run()
        blob = "\n".join(seen)
        assert any(c in blob for c in CANARIES) is leaks, defense
        if not leaks:
            assert "OVERRIDE" not in blob and "bankrupt" not in blob
