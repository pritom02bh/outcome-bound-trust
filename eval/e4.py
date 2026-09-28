"""E4: extractor eval, both local models (FIXES Evaluation E4).

    python -m eval.e4          # gpt-oss:20b and qwen3:8b; writes runs/e4/e4.json

Each model extracts with the frozen prompt (tuned on gpt-oss dev items only, D23) on the 199-item test set and
the 30-item hard subset. Reported: precision/recall on template + slots, template-only precision/recall, exact
match, honest→UNTESTABLE, injections, and the hard subset with and without the code deadline guard (the
no-guard pass reuses the same cached outputs). The rule extractor is the baseline.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eval.run import EXTRACTOR_SET, extractor_eval, git_state
from obt.extractor import EXTRACTOR_SYSTEM, ExtractionCache, LLMExtractor, RuleExtractor, model_digest
from obt.llm import LLM, RUNS

MODELS = ("gpt-oss:20b", "qwen3:8b")
OUT = RUNS / "e4"


def run(models=MODELS, out: Path = OUT, llm_for=None, cache_for=None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    llm_for = llm_for or (lambda m: LLM("ollama", m, log_path=out / "llm_calls.jsonl"))
    cache_for = cache_for or (lambda m: ExtractionCache(RUNS / "cache" / "extract", m, model_digest(m)))
    unguarded = RuleExtractor()
    unguarded.deadline_guard = False
    rep = {"rule": {"test": extractor_eval(RuleExtractor(), 200, "test"),
                    "test_hard": extractor_eval(RuleExtractor(), 30, "test_hard"),
                    "test_hard_no_guard": extractor_eval(unguarded, 30, "test_hard")}}
    for m in models:
        llm, cache = llm_for(m), cache_for(m)
        rep[m] = {
            "test": extractor_eval(LLMExtractor(llm, cache), 200, "test"),
            "test_hard": extractor_eval(LLMExtractor(llm, cache), 30, "test_hard"),
            "test_hard_no_guard": extractor_eval(LLMExtractor(llm, cache, deadline_guard=False), 30, "test_hard"),
            "meta": {"model": m, "model_digest": model_digest(m) if llm.backend == "ollama" else m,
                     "extractor_prompt_sha256": hashlib.sha256(EXTRACTOR_SYSTEM.encode()).hexdigest(),
                     "extractor_dataset_sha256": hashlib.sha256(EXTRACTOR_SET.read_bytes()).hexdigest(),
                     "git_commit": git_state()[0], "calls": llm.calls, "tokens": llm.tokens,
                     "latency_s": round(llm.latency, 2)},
        }
        print(f"{m}: test P {rep[m]['test']['precision']} R {rep[m]['test']['recall']} exact "
              f"{rep[m]['test']['exact_match']}; hard recorded {rep[m]['test_hard']['hard']['delivery_recorded']}"
              f" (no guard {rep[m]['test_hard_no_guard']['hard']['delivery_recorded']})", flush=True)
    (out / "e4.json").write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n")
    return rep


if __name__ == "__main__":
    run()
