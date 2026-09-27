import json

from eval.run import EvalConfig, extractor_eval, parse_range, run_eval, score_extraction
from obt.extractor import RuleExtractor
from obt.llm import CostMeter, PAID_PRICES


def test_parse_range():
    assert parse_range("1-3,7") == [1, 2, 3, 7]


def test_score_extraction_is_multiset():
    g = [("DELIVERY", "widget", 4, 9), ("DELIVERY", "widget", 4, 9), ("PRICE", "widget", 5.0, 9)]
    assert score_extraction([("DELIVERY", "widget", 4, 9)] * 3, g) == (2, 3, 3)
    assert score_extraction([], g) == (0, 0, 3)


def test_rule_extractor_baseline_on_frozen_test_set():
    # The rule extractor is only a baseline here (D24). It never records a value the text doesn't state
    # unambiguously, and never an injected one.
    r = extractor_eval(RuleExtractor())
    assert r["n_messages"] == 199 and r["split"] == "test"          # test192 excluded (D23c)
    assert r["precision"] == 1.0 and r["recall"] > 0.8
    assert r["by_kind"]["vague"]["no_claim_accuracy"] == 1.0
    assert r["injection"]["n"] == 29 and r["injection"]["injected_values_recorded"] == 0
    assert 0 <= r["honest_untestable_rate"] < 0.2          # visible limitation, reported (D23)


def test_scripted_eval_end_to_end(tmp_path, rule_llm):
    ec = EvalConfig(backend="fake", model="fake", buyer="scripted", scenarios=(1, 2, 7), defenses=("obt", "none"),
                    rounds=20, extractor_limit=20)
    rep = run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "cost.json"), fake=rule_llm)
    # Every scripted run extracted with the LLM extractor (D24); the rule extractor is only on the test set.
    runs = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert {r["usage"]["extractor"] for r in runs} == {"llm"} and all(r["usage"]["by_purpose"]["extract"]["calls"]
                                                                      for r in runs)
    assert set(rep["extractor"]) == {"rule", "llm:fake", "rule:test_hard", "llm:fake:test_hard",
                                     "llm:fake:test_hard:no_guard"}
    assert rep["stopped"] is None and rep["n_runs"] == 6
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 6
    loss = rep["summary"]["loss_from_lies"]
    assert loss["1|obt"] == 0 and loss["1|none"] == 0
    assert loss["7|obt"] < loss["7|none"]
    assert "Loss from lies" in (tmp_path / "summary.md").read_text()
    assert rep["paid_spend_usd"]["after"] == 0


def _fake(system, user):
    if "procurement auditor" in system:
        return json.dumps({"trustworthy": True, "reason": "ok"})
    if "Reply with JSON only:\n{\"backup_qty\"" in user or "BLOCKED with reason" in user:
        return json.dumps({"backup_qty": 20})
    if "checkable claims" in system:
        return json.dumps({"claims": []})
    return json.dumps({"s_main_order": None, "backup_qty": 20, "next_lot_request": 1, "note": "",
                       "note_cites": []})


def test_llm_eval_with_fake_backend_records_overhead(tmp_path):
    ec = EvalConfig(backend="fake", model="fake", scenarios=(1, 2), rounds=4, extractor_limit=5)
    rep = run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "cost.json"), fake=_fake)
    assert rep["n_runs"] == 10 and rep["stopped"] is None      # 5 defenses x 2 scenarios
    over = rep["summary"]["overhead"]
    assert over["obt"]["tokens_per_round"] > 0
    assert over["llm_selfcheck"]["tokens_per_round"] >= over["none"]["tokens_per_round"]
    assert rep["extractor"]["llm:fake"]["n_messages"] == 5
    assert (tmp_path / "llm_calls.jsonl").exists()


def test_hard_stop_when_cap_already_reached(tmp_path, monkeypatch):
    monkeypatch.setitem(PAID_PRICES, "paid-model", (1.0, 1.0))
    meter = CostMeter(tmp_path / "cost.json", cap=13.0)
    meter.add("paid-model", 13_000_000, 0)                       # exactly $13 spent
    ec = EvalConfig(backend="openai", model="paid-model", scenarios=(1,), defenses=("obt",), rounds=3)
    rep = run_eval(ec, tmp_path, meter=meter)
    assert rep["n_runs"] == 0 and rep["stopped"].startswith("HardStop")


def test_paid_backend_refused_without_env_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("OBT_ALLOW_PAID", raising=False)
    ec = EvalConfig(backend="openai", model="gpt-5.6-luna", scenarios=(1,), defenses=("obt",), rounds=3)
    rep = run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "cost.json"))
    assert rep["n_runs"] == 0 and rep["stopped"].startswith("PaidCallRefused")


def test_harness_never_sets_paid_flag():
    import inspect
    import eval.run as er
    src = inspect.getsource(er)
    assert "OBT_ALLOW_PAID\"] =" not in src and "setdefault(\"OBT_ALLOW_PAID\"" not in src
