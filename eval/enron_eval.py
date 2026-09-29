"""Enron real-text check of the frozen extractor (DECISIONS D34). Run after the user labels the sample.

    python -m eval.enron_eval          # reads data/enron_candidates.csv; writes runs/enron/eval.json

Reported per stratum (delivery-like, price-only), never pooled:
  1. wrong_claims_recorded: claims the extractor recorded (PENDING) that don't match a labeled claim. The safety
     metric; target 0. A recorded DELIVERY matches only a labeled delivery claim with the same qty and a deadline
     written as that round number; a PRICE likewise (same price, valid_until as that round).
  2. commitment_claims_untestable: labeled claims in real commitments that were not recorded. The schema's coverage
     limit: calendar dates, non-widget items and quantities outside unit wording can't be expressed (expected).
  3. recorded_from_non_commitments: claims recorded from sentences labeled as not a commitment.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from obt.extractor import Extractor
from obt.types import Message

LABELS = Path(__file__).resolve().parent.parent / "data" / "enron_candidates.csv"


def _yes(v: str) -> bool:
    return v.strip().lower() in ("yes", "y", "true", "1")


def _int(v: str):
    try:
        return int(v.strip())
    except (ValueError, AttributeError):
        return None


def _float(v: str):
    try:
        return round(float(v.strip().lstrip("$")), 4)
    except (ValueError, AttributeError):
        return None


def evaluate(path: Path, extractor: Extractor) -> dict:
    rows = list(csv.DictReader(path.open()))
    bad = [i for i, r in enumerate(rows) if r.get("is_commitment", "").strip().lower() not in ("yes", "no", "y", "n")]
    if bad:
        raise ValueError(f"rows {bad[:5]}... have no is_commitment label (yes/no)")
    out: dict = {}
    for i, r in enumerate(rows):
        st = out.setdefault(r["stratum"], {"rows": 0, "commitments": 0, "commitment_claims": 0,
                                           "commitment_claims_untestable": 0, "recorded_claims": 0,
                                           "wrong_claims_recorded": 0, "recorded_from_non_commitments": 0})
        st["rows"] += 1
        claims = extractor.extract(Message(msg_hash=f"enron{i}", counterparty="S_main", round=0, text=r["message"]))
        rec = [c for c in claims if c.status == "PENDING"]
        labeled = []
        if _yes(r.get("has_delivery_claim", "")):
            labeled.append(("DELIVERY", _int(r["qty"]), _int(r["deadline"])))
        if _yes(r.get("has_price_claim", "")):
            labeled.append(("PRICE", _float(r["price"]), _int(r["valid_until"])))
        got = [("DELIVERY", c.slots["qty"], c.slots["by_round"]) if c.template == "DELIVERY"
               else ("PRICE", round(float(c.slots["unit_price"]), 4), c.slots["valid_until"]) for c in rec]
        matched = [g for g in got if g in labeled and None not in g]
        commitment = _yes(r["is_commitment"])
        st["recorded_claims"] += len(got)
        st["wrong_claims_recorded"] += len(got) - len(matched)
        if commitment:
            st["commitments"] += 1
            st["commitment_claims"] += len(labeled)
            st["commitment_claims_untestable"] += sum(1 for lab in labeled if lab not in matched)
        else:
            st["recorded_from_non_commitments"] += len(got)
    return out


def main() -> None:
    from obt.extractor import ExtractionCache, LLMExtractor, RuleExtractor, model_digest
    from obt.llm import LLM, RUNS
    m = "gpt-oss:20b"
    llm = LLM("ollama", m, log_path=RUNS / "enron" / "llm_calls.jsonl")
    rep = {"llm:" + m: evaluate(LABELS, LLMExtractor(llm, ExtractionCache(RUNS / "cache" / "extract", m,
                                                                          model_digest(m)))),
           "rule": evaluate(LABELS, RuleExtractor())}
    (RUNS / "enron" / "eval.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
