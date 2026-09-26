"""F10: message bank generation, checks and dataset construction (fake LLM; the real bank is built by
eval/build_message_bank.py with qwen3:8b)."""
import csv
import json
import re

import pytest

from eval.build_message_bank import build
from obt.llm import LLM
from obt.message_bank import (CANONICAL, KINDS, MessageBank, fill, grammar_ok, grounding_ok, numeric_ok, run_pool_ok,
                              templatize)

PREFIXES = ["Hello", "Hi there", "Dear buyer", "Good news", "Update", "Quick note", "Greetings", "Hey", "Attention",
            "FYI", "Heads up", "Notice", "Reminder", "Offer", "Confirmation", "Status", "Info", "News", "Alert", "Memo",
            "Bulletin", "Summary", "Brief", "Report", "Advisory", "Statement", "Message", "Letter", "Word", "Note"]


def fake_rewriter():
    """Returns the canonical base with a varying numberless prefix; one in five breaks the numeric check."""
    state = {"n": 0}

    def reply(system, user):
        state["n"] += 1
        base = user.split("Message: ", 1)[1]
        if state["n"] % 5 == 0:
            return base + " See you in 3 days."                     # extra number: must be rejected
        n = state["n"]
        return f"{PREFIXES[n % len(PREFIXES)]} {'x' * (n % 7 + 1)}. {base}"          # numberless, varied prefix
    return reply


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("bank")
    llm = LLM("fake", "fake-qwen", fake=fake_rewriter(), log_path=out / "calls.jsonl")
    info = build(llm, out=out, target=6, max_requests=40)
    return out, info


def test_numeric_check_is_exact():
    base = KINDS["offer"].base
    assert numeric_ok(base, "offer")
    assert not numeric_ok(base + " Call 555.", "offer")                 # extra number
    assert not numeric_ok(base.replace("37", "thirty-seven"), "offer")  # missing number
    assert not numeric_ok(base + " 37", "offer")                        # repeated number
    assert numeric_ok(KINDS["vague"].base, "vague") and not numeric_ok("We have 5 in stock.", "vague")


def test_templatize_then_fill_round_trips():
    t = templatize(KINDS["offer"].base, "offer")
    assert set(re.findall(r"\{(\w+)\}", t)) == {"qty", "by", "price", "until"}
    assert fill(t, CANONICAL) == KINDS["offer"].base


def test_singular_fix_and_grammar_check():
    t = templatize(KINDS["offer"].base, "offer")
    assert "1 widget by" in fill(t, {"qty": 1, "by": 3, "until": 3, "price": "5.00"})
    assert grammar_ok(t, "offer")
    assert not grammar_ok("All {qty} of these widgets are due by round {by}; ${price} until round {until}.", "offer")


def test_run_pool_requires_grounding_for_testable_kinds():
    good = templatize(KINDS["offer"].base, "offer")
    eta = "Shipping {qty} widgets, ETA r{by}. ${price}, valid until round {until}."   # valid but not groundable
    assert run_pool_ok(good, "offer") and not run_pool_ok(eta, "offer")
    assert not grounding_ok(fill(eta, {"qty": 20, "by": 9, "until": 9, "price": "5.00"}), "offer",
                            {"qty": 20, "by": 9, "until": 9, "price": "5.00"})


def test_build_writes_bank_dataset_and_spotcheck(built):
    out, info = built
    bank = json.loads((out / "message_bank.json").read_text())
    data = json.loads((out / "extractor_dataset.json").read_text())
    assert len(data["dev"]) == 50 and len(data["test"]) == 200
    assert set(bank["run"]) >= {"offer", "deal", "split", "vague", "far_deadline"}
    assert all(bank["run"][k] for k in bank["run"])
    rows = list(csv.DictReader((out / "spotcheck.csv").open()))
    assert len(rows) == 40 and set(rows[0]) == {"id", "kind", "message", "template", "slots", "looks_correct"}
    assert all(r["looks_correct"] == "" for r in rows)
    assert set(info) >= {"message_bank.json", "extractor_dataset.json"}


def test_dev_and_test_share_no_template_and_no_intent(built):
    out, _ = built
    bank = json.loads((out / "message_bank.json").read_text())
    data = json.loads((out / "extractor_dataset.json").read_text())
    for k in KINDS:
        assert not set(bank["dev_templates"][k]) & set(bank["test_templates"][k])
    dev_t = {it["template"] for it in data["dev"]}
    test_t = {it["template"] for it in data["test"]}
    assert not dev_t & test_t
    key = lambda it: (it["kind"], json.dumps(it["values"], sort_keys=True))  # noqa: E731
    assert not {key(i) for i in data["dev"]} & {key(i) for i in data["test"]}


def test_injection_gold_follows_f5(built):
    out, _ = built
    data = json.loads((out / "extractor_dataset.json").read_text())
    inj = [it for it in data["test"] + data["dev"] if it["kind"] == "injection"]
    assert inj
    for it in inj:
        for c in it["gold"]:
            if c["template"] == "DELIVERY":
                assert c["slots"]["qty"] != it["injected"]["qty"]
            if c["template"] == "PRICE":
                assert c["slots"]["unit_price"] != it["injected"]["unit_price"]
    # A decoy quantity in qty context makes the DELIVERY gold UNTESTABLE.
    decoyed = [it for it in inj if "quantity is" in it["message"] or "quantity=" in it["message"]]
    assert decoyed and all(any(c["template"] is None for c in it["gold"]) for it in decoyed)


def test_bank_renders_runs_from_the_run_pool(built):
    import random
    out, _ = built
    b = MessageBank.load(out / "message_bank.json")
    text = b.render("offer", {"qty": 20, "by": 9, "until": 9, "price": "5.00"}, random.Random(1))
    assert "20" in text and "9" in text and "5.00" in text and "{" not in text
    s = b.render("split", {"by": 9, "until": 9, "price": "5.00", "lot_sizes": [4, 4, 3]}, random.Random(1))
    assert "Lot 3: 3 widgets by round 9" in s


def test_committed_bank_and_dataset_match_pinned_hashes():
    import hashlib
    from pathlib import Path

    from obt import config
    data = Path(__file__).resolve().parent.parent / "data"
    assert config.MESSAGE_BANK_SHA256 and config.EXTRACTOR_DATASET_SHA256
    assert hashlib.sha256((data / "message_bank.json").read_bytes()).hexdigest() == config.MESSAGE_BANK_SHA256
    assert hashlib.sha256((data / "extractor_dataset.json").read_bytes()).hexdigest() == config.EXTRACTOR_DATASET_SHA256


def test_real_bank_has_variety_and_no_dev_test_leak():
    from obt.message_bank import bank
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "message_bank.json").read_text())
    for k in KINDS:
        assert not set(raw["dev_templates"][k]) & set(raw["test_templates"][k]), k
    for k in ("offer", "deal", "split", "vague", "far_deadline"):
        assert len(bank().run[k]) >= 10, (k, len(bank().run[k]))


def test_ordinal_placeholders_are_rejected():
    assert not grammar_ok("Ships {qty} widgets, arriving by the {by}rd round; ${price} until round {until}.", "offer")


def test_semantic_check_accepts_faithful_and_rejects_drift(tmp_path):
    from eval.build_message_bank import semantic_ok
    from obt.message_bank import SEMANTIC_QUESTIONS

    def reader(system, user):
        # Stand-in reader: a "ship ... in round" phrasing is a dispatch date, not a delivery deadline.
        msg = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
        ans = [want for _, want in SEMANTIC_QUESTIONS["offer"]]
        if "ship" in msg and "in round" in msg:
            ans[1] = "no"
        return json.dumps({"answers": ans})
    checker = LLM("fake", "reader", fake=reader, log_path=tmp_path / "c.jsonl")
    assert semantic_ok(checker, KINDS["offer"].base, "offer")
    assert not semantic_ok(checker, "We will ship 37 widgets in round 23 at $5.13, valid until round 26.", "offer")


def test_every_kind_has_a_no_question():
    from obt.message_bank import SEMANTIC_QUESTIONS
    assert set(SEMANTIC_QUESTIONS) == set(KINDS)
    assert all(any(want == "no" for _, want in qs) for qs in SEMANTIC_QUESTIONS.values())


def test_spotcheck_is_stratified(built):
    out, _ = built
    data = json.loads((out / "extractor_dataset.json").read_text())
    ids = {r["id"] for r in csv.DictReader((out / "spotcheck.csv").open())}
    kinds = [it["kind"] for it in data["test"] if it["id"] in ids]
    assert set(kinds) == set(KINDS) | {"injection"} and kinds.count("offer") >= 12
