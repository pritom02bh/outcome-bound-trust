"""E9 (DECISIONS D44): the cloud/API-capacity domain behind the `domain` flag, the SLA template, the one gate
bookkeeping line (reliance on SLA claims), the damage counterfactual and its per-event bounds."""
import dataclasses
import hashlib
import json
from decimal import Decimal

import pytest

import eval.run as er
from eval import e9
from obt.env import cloud, cloud_lossbound
from obt.env.beer_game import BACKUP, MAIN, GameConfig, OrderRequest, SupplierReply
from obt.env.oracles import Oracles
from obt.extractor import LLMExtractor
from obt.llm import LLM
from obt.sim import Sim, SimConfig
from obt.types import ITEMS, Claim, Message
from obt.verifier import check_sla

G = GameConfig(rounds=20)


def sla(a="0.8", start=3, end=7, cp=MAIN, cid="s1"):
    return Claim.make(claim_id=cid, counterparty=cp, source_msg_hash="h", created_round=1, template="SLA",
                      slots={"item": "capacity", "min_availability": a, "start": start, "end": end})


# ---- the SLA template

def test_sla_claim_is_typed_and_resolves_at_the_window_end():
    c = sla()
    assert c.deadline == 7 and c.slots["min_availability"] == Decimal("0.8") and c.remaining == 0
    with pytest.raises(Exception):
        sla(start=7, end=3)
    with pytest.raises(Exception):
        sla(a="1.5")


@pytest.mark.parametrize("up_rounds,a,ok", [(4, "0.8", True), (3, "0.8", False), (5, "1", True), (4, "1", False),
                                             (3, "0.6", True), (2, "0.6", False)])
def test_check_sla_pass_fail_and_boundary(up_rounds, a, ok):
    o = Oracles()
    for t in range(3, 8):                                  # window 3..7, n = 5: needs ceil(a x 5) up rounds
        o.record_uptime(t, MAIN, t - 3 < up_rounds)
    assert check_sla(sla(a), o.view) is ok


def test_a_round_missing_from_the_uptime_log_counts_as_down():
    o = Oracles()
    for t in (3, 4, 5, 6):
        o.record_uptime(t, MAIN, True)                      # round 7 never recorded
    assert check_sla(sla("1"), o.view) is False and check_sla(sla("0.8"), o.view) is True


# ---- the supply domain is untouched

def test_supply_catalog_stays_closed_for_the_llm_extractor():
    out = json.dumps({"claims": [{"template": "DELIVERY", "item": "capacity", "qty": 5, "by_round": 9}]})
    ex = LLMExtractor(LLM("fake", "m", fake=lambda s, u: out))
    msg = Message(msg_hash="h", counterparty=MAIN, round=1, text="We will deliver 5 widgets by round 9.")
    assert [c.status for c in ex.extract(msg)] == ["UNTESTABLE"] and ITEMS == ("widget",)


def test_default_domain_keeps_every_config_hash():
    ec = er.EvalConfig(sim={"b0_frac": 0.05, "window": 0, "grace": 0})
    sim = dataclasses.asdict(er.sim_config(ec))
    for k in ("defense", "budget_k", "domain"):
        sim.pop(k)
    blob = {"eval": {k: getattr(ec, k) for k in er._RUN_FIELDS}, "sim": sim}
    assert er.config_hash(ec) == hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()
    assert SimConfig().domain == "supply"
    with pytest.raises(ValueError):
        Sim(SimConfig(domain="space"), 1, cloud.Honest(G), cloud.CapacityBuyer(G))


# ---- the capacity game

class Fixed(cloud.CloudSupplier):
    def __init__(self, cfg, ships, down=()):
        super().__init__(cfg, 0)
        self.ships, self.down = ships, set(down)

    def on_order(self, req):
        return SupplierReply(5.0, self.ships)

    def up(self, t, identity):
        return t not in self.down


def test_capacity_game_costs_by_hand():
    cfg = GameConfig(rounds=8, demand_mean=10, demand_sd=0)
    g = cloud.CloudGame(cfg, 1, {MAIN: Fixed(cfg, ((6, 3),), down={4}), BACKUP: cloud.BackupSupplier(cfg)})
    g.begin_round()
    g.place_order(MAIN, 6, 3)
    for _ in range(7):
        g.begin_round()
    # Rounds 1-2: no capacity (20 on demand); 3: 6 up (4); 4: down (10); 5-7: 6 up (4 each); 8: lot expired (10).
    assert [h.inventory for h in g.history] == [0, 0, 6, 0, 6, 6, 6, 0]
    assert g.costs["on_demand"] == cloud.ON_DEMAND * (10 + 10 + 4 + 10 + 4 + 4 + 4 + 10)
    assert g.oracles.uptime(MAIN, 4, 4) == (0, 1) and g.oracles.received(MAIN, "capacity", 0, 3) == 6


def test_structured_extractor_fails_closed():
    ex = cloud.StructuredExtractor()
    good = json.dumps({"claims": [{"template": "SLA", "slots": {"item": "capacity", "min_availability": "0.9",
                                                                "start": 3, "end": 7}}]})
    assert [c.template for c in ex.extract(Message(msg_hash="a", counterparty=MAIN, round=1, text=good))] == ["SLA"]
    widget = json.dumps({"claims": [{"template": "DELIVERY", "slots": {"item": "widget", "qty": 3, "by_round": 3}}]})
    for text in (widget, "not json", "{}"):
        assert [c.status for c in ex.extract(Message(msg_hash="b", counterparty=MAIN, round=1, text=text))] == \
            ["UNTESTABLE"]


# ---- the gate's one new line: reliance on cited SLA claims

def _run(n, defense="obt", rounds=50, seed=1):
    cfg = e9.sim_config(defense, rounds)
    sim = Sim(cfg, seed, cloud.make_cloud_supplier(n, cfg.game, seed), cloud.CapacityBuyer(cfg.game),
              extractor=cloud.StructuredExtractor(), scenario=cloud.cloud_scenario_name(n))
    return sim, sim.run()


def test_a_relied_on_sla_resolves_and_an_uncited_one_lapses():
    sim, res = _run(1)
    slas = [c for c in sim.ledger if c.template == "SLA" and c.status != "PENDING"]
    cited = {k for a in sim.actions if a.kind == "ORDER" and a.was_executed for k in a.cited_claims}
    assert any(c.claim_id in cited for c in slas)
    for c in slas:
        relied = sum(a.qty for a in sim.actions if a.kind == "ORDER" and a.was_executed and c.claim_id in a.cited_claims)
        assert c.consumed == relied
        assert c.status == ("PASSED" if relied else "LAPSED")           # honest: every relied-on SLA passes


def test_always_lie_fails_quota_and_sla_and_the_bound_holds():
    sim, res = _run(2)
    lb = res.metrics["loss_bound"]
    kinds = {e["template"] for e in lb["events"]}
    assert kinds == {"QUOTA", "SLA"} and lb["ok"] and res.metrics["invariant_violations"]["count"] == 0
    assert all(e["bound"] <= e["apriori"] + 1e-9 for e in lb["events"])


@pytest.mark.parametrize("n", list(cloud.SCENARIOS))
def test_replay_fidelity_bound_and_invariants_on_every_scenario(n):
    for defense in ("obt", "none", "rep-n18"):
        sim, res = _run(n, defense, rounds=40)
        assert res.metrics["invariant_violations"]["count"] == 0
        if defense == "obt":
            assert cloud_lossbound.replay_cost(sim, kept=False) == pytest.approx(sim.game.total_cost, abs=1e-6)
            lb = res.metrics["loss_bound"]
            assert lb["ok"], (n, lb["damage"], lb["sum_bound"])
            if n == 1:
                assert lb["events"] == [] and lb["damage"] == pytest.approx(0, abs=1e-6)


def test_e9_runner_and_summary(tmp_path):
    rows = e9.run(tmp_path, scenarios=(1, 2), defenses=("obt", "none"), seeds=(1,), rounds=20)
    assert len(rows) == 4 and all(r["domain"] == "cloud" for r in rows)
    s = e9.summary(rows)
    assert set(s["defenses"]) == {"obt", "none"} and s["bound"]["all"]["held"]
    b = s["bound"]["all"]
    assert b["max_apriori_ratio"] is None or b["max_apriori_ratio"] <= (b["max_ratio"] or 0) + 1e-9   # a-priori >= bound
    assert e9.run(tmp_path, scenarios=(1, 2), defenses=("obt", "none"), seeds=(1,), rounds=20) == rows   # resumable
