"""Shared test helpers."""
import json

from obt.extractor import EXTRACTOR_SYSTEM, RuleExtractor
from obt.types import Message


def rule_backed_llm(system: str, user: str) -> str:
    """Fake LLM for eval-harness tests: answers the LLM extractor's prompt with the rule extractor's reading,
    so scripted evals run through the real LLMExtractor path without a model (D24). Anything else gets the
    buyer's 'order nothing from S_main' decision."""
    if system == EXTRACTOR_SYSTEM:
        text = user.split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]
        specs = RuleExtractor().propose(Message(msg_hash="t", counterparty="x", round=0, text=text))
        return json.dumps({"claims": [{"template": s["template"], **{k: (float(v) if k == "unit_price" else v)
                                                                     for k, v in s["slots"].items()}}
                                      for s in specs]})
    return json.dumps({"s_main_order": None, "backup_qty": 20, "next_lot_request": 1, "note": "", "note_cites": []})


import pytest  # noqa: E402


@pytest.fixture
def rule_llm():
    return rule_backed_llm
