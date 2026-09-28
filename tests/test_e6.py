"""E6: adaptive attacker search against OBT (scripted buyer). Parameter space, attacker, objective, search, STOP."""
import pytest

from eval import e6
from obt.attacks.adaptive import BOUNDS, AdaptiveAttacker, Params
from obt.env.beer_game import MAIN, GameConfig, OrderRequest

G = GameConfig()


def test_params_round_trip_and_clamp():
    p = Params()
    assert Params.from_vector(p.to_vector()) == p
    wild = Params.from_vector([1e9] * len(BOUNDS))
    for name, (lo, hi, kind) in BOUNDS.items():
        v = getattr(wild, name)
        assert lo <= v <= hi and isinstance(v, int if kind is int else float)


def test_honest_params_make_an_honest_supplier():
    a = AdaptiveAttacker(G, 1, Params(farm_len=G.rounds + 1))
    assert not any(a.lies_at(t) for t in range(1, G.rounds + 1))
    r = a.on_order(OrderRequest("o1", 5, 10))
    assert r.shipments == ((10, 5 + G.main_lead),) and r.unit_price == G.main_price


def test_lying_rounds_follow_farm_period_and_burst():
    a = AdaptiveAttacker(G, 1, Params(farm_len=10, lie_period=5, lie_burst=2))
    lies = [t for t in range(1, 30) if a.lies_at(t)]
    assert lies == [10, 11, 15, 16, 20, 21, 25, 26]


def test_partial_late_shipment_and_markup_on_lies():
    a = AdaptiveAttacker(G, 1, Params(farm_len=0, ship_frac=0.5, delay=3, price_markup=0.2))
    r = a.on_order(OrderRequest("o1", 4, 10))
    assert r.shipments == ((5, 4 + G.main_lead + 3),)
    assert r.unit_price == pytest.approx(G.main_price * 1.2)


def test_identity_reset_after_a_failed_promise():
    a = AdaptiveAttacker(G, 1, Params(farm_len=0, identities=3))
    assert a.identities == (MAIN, "S_main_2", "S_main_3") and a.identity == MAIN
    a.on_order(OrderRequest("o1", 2, 5))
    a.offer_intent(2 + G.main_lead + 1, 10)
    assert a.identity == "S_main_2"


def test_evaluate_reports_the_worst_seed_ratio():
    r = e6.evaluate(Params(farm_len=0), seeds=(1, 2))
    assert set(r) >= {"ratio", "mean_ratio", "damage", "sum_bound", "per_seed"}
    assert r["ratio"] == max(x["ratio"] for x in r["per_seed"]) and 0 <= r["ratio"] <= 1


def test_search_is_deterministic_and_within_budget():
    a = e6.search(budget=12, n_random=6, seeds=(1,), rng_seed=3)
    b = e6.search(budget=12, n_random=6, seeds=(1,), rng_seed=3)
    assert a["best"]["params"] == b["best"]["params"] and a["evaluations"] == 12 == b["evaluations"]


def test_a_ratio_above_one_stops_the_search(monkeypatch):
    monkeypatch.setattr(e6, "evaluate", lambda p, seeds=e6.SEEDS, sim_kw=None: {
        "ratio": 1.2, "mean_ratio": 1.2, "damage": 12.0, "sum_bound": 10.0, "per_seed": []})
    with pytest.raises(e6.BoundViolation):
        e6.search(budget=5, n_random=5, seeds=(1,), rng_seed=0)


def test_results_builder_writes_e6_summary(tmp_path):
    import json
    from eval import results
    runs = tmp_path / "runs" / "e6"
    runs.mkdir(parents=True)
    best = {"params": Params().as_dict(), "ratio": 0.5, "mean_ratio": 0.4, "damage": 7.0, "sum_bound": 14.0}
    ev = {"ratio": 0.5, "mean_ratio": 0.4, "damage": 7.0, "sum_bound": 14.0, "per_seed": []}
    (runs / "e6.json").write_text(json.dumps({
        "evaluations": 3, "budget": 3, "n_random": 2, "seeds": [1], "rng_seed": 0, "best": best, "max_damage": best,
        "history": [best] * 3, "best_on_seeds_1_10": ev, "best_under_variants": {"v": ev}, "wall_s": 1.0}))
    results.build(tmp_path / "runs", tmp_path / "out")
    md = (tmp_path / "out" / "e6.md").read_text()
    assert "0.5" in md and "farm_len" in md and "evaluations" in md


def test_confirmation_uses_the_llm_extractor_over_a2a(tmp_path, rule_llm):
    from obt.llm import LLM
    llm = LLM("fake", "gpt-oss:20b", fake=rule_llm, log_path=tmp_path / "c.jsonl")
    r = e6.confirm(Params(farm_len=0), seeds=(1,), llm=llm, cache=None, rounds=8)
    assert r["per_seed"][0]["transport"] == "a2a" and r["per_seed"][0]["extractor"] == "llm"
    assert 0 <= r["ratio"] <= 1 and llm.calls > 0
