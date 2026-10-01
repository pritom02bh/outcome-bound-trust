"""D36: budget growth multiplier k, B(c) = b0 + k x max honored exposure; E7; the E3 loss split."""
import dataclasses
import hashlib
import json
from decimal import Decimal

import eval.run as er
from eval.run import EvalConfig
from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import MAIN, GameConfig
from obt.extractor import RuleExtractor
from obt.sim import Sim, SimConfig

G = GameConfig(rounds=30)


def run(n, k, seed=1):
    s = Sim(SimConfig(game=G, budget_k=k), seed, make_supplier(n, G, seed), ScriptedClaimBuyer(G),
            extractor=RuleExtractor())
    return s, s.run()


def test_k_multiplies_only_the_earned_part():
    s1, _ = run(1, 1)
    s2, _ = run(1, 2)
    b0 = s1.budget.cfg.b0
    earned = [k.realized_exposure for k in s2.ledger.claims_of(MAIN) if k.status == "PASSED"
              and k.template == "DELIVERY"]
    assert s2.budget.B(MAIN, G.rounds) == b0 + 2 * max(earned)
    assert s2.trace[-1]["B"] > s1.trace[-1]["B"]                     # faster growth


def test_k1_is_exactly_the_old_rule_and_keeps_old_config_hashes():
    ec = EvalConfig(sim={"b0_frac": 0.05, "window": 0, "grace": 0})
    sim = dataclasses.asdict(er.sim_config(ec))
    sim.pop("defense")
    sim.pop("budget_k")                                              # the pre-D36 blob had no budget_k
    sim.pop("domain")                                                # nor domain (D44)
    blob = {"eval": {k: getattr(ec, k) for k in er._RUN_FIELDS}, "sim": sim}
    assert er.config_hash(ec) == hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()
    assert er.config_hash(EvalConfig(sim={"budget_k": 2})) != er.config_hash(EvalConfig())


def test_bound_holds_with_k_and_the_apriori_bound_scales_with_k():
    for k in (1, 2, 4):
        s, res = run(2, k)
        lb = res.metrics["loss_bound"]
        assert res.metrics["invariant_violations"]["count"] == 0 and lb["ok"]
        assert all(e["apriori"] >= e["bound"] - 1e-9 for e in lb["events"])
        assert all(Decimal(str(e["B_at_order"])) <= s.budget.cfg.b0 + k * Decimal("10000") for e in lb["events"])


def test_e7_summary(tmp_path):
    from eval import e7
    out = e7.run(tmp_path, ks=(1, 2), horizons=(10,), scenarios=(1, 2, 9), seeds=(1,))
    for k in ("1", "2"):
        v = out["points"][k]["10"]
        assert set(v) >= {"utility_pct", "attack_loss", "main_share", "max_ratio", "max_ratio_apriori",
                          "invariant_violations", "bound_ok"}
        assert v["invariant_violations"] == 0 and v["bound_ok"]


def test_e3_loss_is_split_into_damage_reroute_and_resid():
    from eval.stats import loss_split
    h = {"scenario": 1, "defense": "obt", "seed": 1, "total_cost": 100.0,
         "metrics": {"loss_bound": {"damage": 0.0, "reroute_cost": 5.0, "sum_bound": 0, "ok": True, "events": []}}}
    a = {"scenario": 2, "defense": "obt", "seed": 1, "total_cost": 150.0,
         "metrics": {"loss_bound": {"damage": 20.0, "reroute_cost": 15.0, "sum_bound": 40, "ok": True, "events": [1]}}}
    s = loss_split([h, a], "obt")
    assert s == {"loss": 50.0, "damage": 20.0, "reroute": 10.0, "resid": 20.0, "n": 1}
    none = [dict(h, defense="none", metrics={"loss_bound": dict(h["metrics"]["loss_bound"], damage=None)}),
            dict(a, defense="none", metrics={"loss_bound": dict(a["metrics"]["loss_bound"], damage=None)})]
    s = loss_split(none, "none")
    assert s["damage"] is None and s["resid"] == 40.0                # no claims: damage undefined, shown as n/a
