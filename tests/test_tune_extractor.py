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
    assert rep["metrics"]["split"] == "dev" and rep["metrics"]["n_messages"] == 50
    assert rep["metrics"] == extractor_eval(LLMExtractor(llm), 50, "dev")
    errs = json.loads((tmp_path / "t" / "dev_errors.json").read_text())
    assert all(set(e) >= {"id", "kind", "message", "gold", "pred", "untestable"} for e in errs)
    assert all(e["id"].startswith("dev") for e in errs)


def test_test_split_is_refused(tmp_path, rule_llm):
    llm = LLM("fake", "fake", fake=rule_llm, log_path=tmp_path / "c.jsonl")
    with pytest.raises(ValueError):
        tune_report(LLMExtractor(llm), out=tmp_path / "t", split="test")
