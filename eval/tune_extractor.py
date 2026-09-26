"""Extractor prompt tuning on the dev split only (FIXES F10, DECISIONS D23).

    python -m eval.tune_extractor --tag v3_pass1      # local gpt-oss:20b; writes runs/tuning/<tag>/

Writes the dev metrics (the same `extractor_eval` the eval harness reports) and every dev item the extractor
got wrong, with its prediction, so prompt changes are driven by dev errors alone. The test split is refused
here: it is scored once, by eval/run.py, after the prompt is frozen.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.run import EXTRACTOR_SET, _key, extractor_eval
from obt.env.beer_game import MAIN
from obt.extractor import ExtractionCache, Extractor, LLMExtractor, model_digest
from obt.llm import LLM, RUNS
from obt.types import Message


def tune_report(extractor: Extractor, out: Path, split: str = "dev") -> dict:
    if split != "dev":
        raise ValueError("tuning reads the dev split only; the test split is scored once, after freezing")
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    for it in json.loads(EXTRACTOR_SET.read_text())["dev"]:
        v = it["values"]
        msg = Message(msg_hash=it["id"], counterparty=MAIN, round=max(0, v["by"] - 2), text=it["message"])
        claims = extractor.extract(msg)
        pred = sorted(_key(c.template, c.slots) for c in claims if c.status == "PENDING")
        gold = sorted(_key(g["template"], g["slots"]) for g in it["gold"] if g["template"])
        if pred != gold:
            errors.append({"id": it["id"], "kind": it["kind"], "message": it["message"], "gold": gold,
                           "pred": pred, "untestable": sum(c.status == "UNTESTABLE" for c in claims)})
    # Second pass through the harness's own scorer (served from the extraction cache when one is set).
    metrics = extractor_eval(extractor, 50, "dev")
    report = {"metrics": metrics, "n_errors": len(errors)}
    (out / "dev_errors.json").write_text(json.dumps(errors, indent=1, default=str) + "\n")
    (out / "dev_metrics.json").write_text(json.dumps(report, indent=1) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    out = RUNS / "tuning" / a.tag
    llm = LLM("ollama", a.model, log_path=out / "llm_calls.jsonl")
    cache = ExtractionCache(RUNS / "cache" / "extract", a.model, model_digest(a.model))
    print(json.dumps(tune_report(LLMExtractor(llm, cache), out), indent=1))


if __name__ == "__main__":
    main()
