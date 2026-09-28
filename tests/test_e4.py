"""E4: extractor eval for both local models, on the test set and the hard subset (with and without the guard)."""
import json

from eval import e4
from obt.llm import LLM


def test_e4_reports_every_model_and_split(tmp_path, rule_llm):
    llm_for = lambda m: LLM("fake", m, fake=rule_llm, log_path=tmp_path / "c.jsonl")  # noqa: E731
    rep = e4.run(("m1", "m2"), out=tmp_path, llm_for=llm_for, cache_for=lambda m: None)
    assert set(rep) == {"rule", "m1", "m2"}
    for m in ("m1", "m2"):
        r = rep[m]
        assert r["test"]["n_messages"] == 199 and r["test_hard"]["n_messages"] == 30
        assert r["test_hard_no_guard"]["hard"]["n"] == 30
        assert {"precision", "recall", "template_precision", "template_recall", "exact_match"} <= set(r["test"])
        assert r["meta"]["model"] == m and r["meta"]["extractor_prompt_sha256"]
    saved = json.loads((tmp_path / "e4.json").read_text())
    assert set(saved) == {"rule", "m1", "m2"}


def test_results_builder_writes_e4_table(tmp_path, rule_llm):
    from eval import results
    llm_for = lambda m: LLM("fake", m, fake=rule_llm, log_path=tmp_path / "c.jsonl")  # noqa: E731
    e4.run(("m1",), out=tmp_path / "runs" / "e4", llm_for=llm_for, cache_for=lambda m: None)
    results.build(tmp_path / "runs", tmp_path / "out")
    md = (tmp_path / "out" / "e4.md").read_text()
    assert "m1" in md and "rule" in md and "template precision" in md and "hard" in md.lower()
