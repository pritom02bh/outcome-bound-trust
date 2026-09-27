"""F10 dev tuning harness: dev split only, per-item error dump, metrics identical to eval.run's."""
import json

import pytest

from eval.run import extractor_eval
from eval.tune_extractor import tune_report
from obt.extractor import LLMExtractor
from obt.llm import LLM


def test_report_is_dev_only_and_matches_eval_metrics(tmp_path, rule_llm):
    llm = LLM("fake", "fake", fake=rule_llm, log_path=tmp_path / "c.jsonl")
    rep = tune_report(LLMExtractor(llm), out=tmp_path / "t")
    assert rep["metrics"]["split"] == "dev" and rep["metrics"]["n_messages"] == 49
    assert rep["metrics"] == extractor_eval(LLMExtractor(llm), 50, "dev")
    errs = json.loads((tmp_path / "t" / "dev_errors.json").read_text())
    assert all(set(e) >= {"id", "kind", "message", "gold", "pred", "untestable"} for e in errs)
    assert all(e["id"].startswith("dev") for e in errs)


def test_test_split_is_refused(tmp_path, rule_llm):
    llm = LLM("fake", "fake", fake=rule_llm, log_path=tmp_path / "c.jsonl")
    with pytest.raises(ValueError):
        tune_report(LLMExtractor(llm), out=tmp_path / "t", split="test")


def test_hard_subset_metric_counts_shipping_dates_recorded_as_deadlines(tmp_path, rule_llm):
    # The rule-backed fake proposes "ship ... by round N" as DELIVERY: the LLM-alone ablation must count it, and
    # the code guard must bring the count to 0.
    from eval.run import extractor_eval
    llm = LLM("fake", "fake", fake=rule_llm, log_path=tmp_path / "c.jsonl")
    off = extractor_eval(LLMExtractor(llm, deadline_guard=False), 30, "test_hard")["hard"]
    on = extractor_eval(LLMExtractor(llm), 30, "test_hard")["hard"]
    assert off["n"] == 30 and set(off["by_group"]) == {"ship", "ready", "scheduled"}
    assert off["delivery_recorded"] == sum(g["delivery_recorded"] for g in off["by_group"].values())
    assert off["by_group"]["ship"]["delivery_recorded"] > 0
    assert off["by_group"]["scheduled"]["delivery_recorded"] == 0     # no "by round": grounding refuses
    assert on["delivery_recorded"] == 0 and on["price_recovery"] == 1.0
