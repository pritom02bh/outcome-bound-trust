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


def test_committed_run_pool_is_the_final_grounding_filter():
    # The run pool is exactly the accepted templates that pass the final F5 patterns, so a pattern fix
    # after generation can't leave a stale pool behind (re-applied with --rebank).
    from pathlib import Path

    from eval.build_message_bank import RUN_KINDS, run_pool
    raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "message_bank.json").read_text())
    for k in RUN_KINDS:
        assert raw["run"][k] == run_pool(raw, k), k


def test_committed_gold_is_the_final_f5_gold():
    from pathlib import Path

    from eval.build_message_bank import f5_gold
    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "extractor_dataset.json").read_text())
    for it in data["dev"] + data["test"] + data["test_hard"]:
        assert it["gold"] == f5_gold(it), it["id"]


def test_scheduled_for_round_stays_out_of_the_run_pool():
    # "delivery ... scheduled for round N" can mean dispatch or arrival: a real ambiguity, allowed in the test
    # set (where it counts toward honest->UNTESTABLE) but never used to drive runs. The v3 generator, told to
    # use arrival wording, produced none, so the test set currently has none either (D23).
    from pathlib import Path
    raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "message_bank.json").read_text())
    assert not [t for ts in raw["run"].values() for t in ts if "scheduled" in t.lower()]


@pytest.mark.parametrize("template,kind,ok", [
    ("We will deliver {qty} widgets by round {by}. Unit price ${price}, valid until round {until}.", "offer", True),
    ("We'll ship {qty} units no later than round {by}. Price ${price} good till round {until}.", "offer", False),
    ("We commit to shipping {qty} units no later than round {by}. ${price} each through round {until}.", "offer",
     False),
    ("We'll send out {qty} widgets no later than round {by}. ${price} each until round {until}.", "offer", False),
    ("We'll have the {qty} widgets ready by round {by}. ${price} each until round {until}.", "offer", False),
    ("We will have the {qty} widgets available no later than round {by}. ${price} until round {until}.", "offer",
     False),
    ("We dispatch {qty} widgets by round {by}. ${price} until round {until}.", "deal", False),
    # An explicit arrival statement in the same sentence makes the deadline an arrival deadline.
    ("We'll ship {qty} widgets so they arrive by round {by}. ${price} until round {until}.", "offer", True),
    ("We'll send {qty} widgets; they will be delivered by round {by}. ${price} until round {until}.", "offer", True),
    ("Ready for you: {qty} widgets in your warehouse by round {by}. ${price} until round {until}.", "offer", True),
    ("We'll ship so you will have {qty} widgets by round {by}. ${price} until round {until}.", "offer", True),
    # A shipping verb outside the deadline's sentence doesn't matter.
    ("Guaranteed: we will deliver {qty} widgets by round {far}. We usually ship within {lead} rounds. "
     "${price} until round {until}.", "far_deadline", True),
    ("Guaranteed delivery of {qty} widgets by round {far}, though we usually ship within {lead} rounds. "
     "${price} until round {until}.", "far_deadline", True),
    ("We ship {qty} widgets by round {far}, usually within {lead} rounds. ${price} until round {until}.",
     "far_deadline", False),
    ("Split shipment plan. {LOTS} Unit price ${price}, valid until round {until}.", "split", True),
    ("We will ship in lots: {LOTS} Unit price ${price}, valid until round {until}.", "split", False),
    ("Our widget price is ${price} per unit, available until round {until}.", "price_only", True),
])
def test_delivery_verb_guard(template, kind, ok):
    from obt.message_bank import delivery_verb_ok
    assert delivery_verb_ok(template, kind) == ok


def test_run_pool_and_grammar_reject_shipping_deadlines():
    t = "We'll ship {qty} units no later than round {by}. Price ${price} good till round {until}."
    assert not run_pool_ok(t, "offer")


def test_committed_bank_has_no_shipping_or_readiness_deadlines():
    from pathlib import Path

    from obt.message_bank import delivery_verb_ok
    raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "message_bank.json").read_text())
    for sec in ("run", "dev_templates", "test_templates"):
        for k, ts in raw[sec].items():
            assert all(delivery_verb_ok(t, k) for t in ts), (sec, k)


def test_contrast_set_is_balanced_and_labeled():
    from obt.message_bank import SEMANTIC_CONTRAST
    assert len(SEMANTIC_CONTRAST) == 20
    labels = [want for _, want in SEMANTIC_CONTRAST]
    assert labels.count("yes") == 10 and labels.count("no") == 10
    assert len({m for m, _ in SEMANTIC_CONTRAST}) == 20


def test_checker_must_pass_the_contrast_set_before_use(tmp_path):
    from eval.build_message_bank import CANONICAL_LOTS, CheckerInvalid, validate_checker
    from obt.message_bank import SEMANTIC_QUESTIONS

    def reader(always_yes):
        def r(system, user):
            raw = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
            for k, spec in KINDS.items():
                if raw == spec.base.replace("{LOTS}", CANONICAL_LOTS):
                    return json.dumps({"answers": [want for _, want in SEMANTIC_QUESTIONS[k]]})
            msg = raw.lower()
            ans = [want for _, want in SEMANTIC_QUESTIONS["offer"]]
            if not always_yes and any(w in msg for w in ("ship", "send", "dispatch", "ready", "available",
                                                          "leave", "loaded", "handed", "production")) \
                    and not any(w in msg for w in ("arrive", "delivered", "you will have", "your warehouse")):
                ans[1] = "no"
            return json.dumps({"answers": ans})
        return LLM("fake", "reader", fake=r, log_path=tmp_path / "c.jsonl")
    report = validate_checker(reader(False))
    assert report["correct"] == 20 and not report["errors"] and report["canonical_accepted"] == len(KINDS)
    with pytest.raises(CheckerInvalid):
        validate_checker(reader(True))


def test_build_refuses_an_invalid_checker(tmp_path):
    from eval.build_message_bank import CheckerInvalid
    yes = LLM("fake", "reader", fake=lambda s, u: json.dumps({"answers": ["yes"] * 5 if "37 widgets" in u
                                                                else ["yes"] * 6}), log_path=tmp_path / "c.jsonl")
    llm = LLM("fake", "fake-qwen", fake=fake_rewriter(), log_path=tmp_path / "g.jsonl")
    with pytest.raises(CheckerInvalid):
        build(llm, out=tmp_path, target=2, max_requests=4, checker=yes)


def test_build_checkpoints_each_kind_and_resumes(tmp_path):
    # A rebuild must never lose finished kinds: each kind's pools are saved as soon as it is done and reused
    # when the generation settings match, so a resumed build makes no LLM call for them.
    out1, out2, ck = tmp_path / "a", tmp_path / "b", tmp_path / "ck"
    llm = LLM("fake", "fake-qwen", fake=fake_rewriter(), log_path=tmp_path / "g.jsonl")
    build(llm, out=out1, target=6, max_requests=40, checkpoint=ck)
    assert {p.stem for p in ck.glob("*.json")} == set(KINDS)

    def boom(system, user):
        raise AssertionError("resumed build called the generator")
    build(LLM("fake", "fake-qwen", fake=boom, log_path=tmp_path / "g2.jsonl"), out=out2, target=6,
          max_requests=40, checkpoint=ck)
    for name in ("message_bank.json", "extractor_dataset.json", "spotcheck.csv"):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes(), name


def test_checkpoint_is_ignored_when_settings_change(tmp_path):
    ck = tmp_path / "ck"
    build(LLM("fake", "fake-qwen", fake=fake_rewriter(), log_path=tmp_path / "g.jsonl"), out=tmp_path / "a",
          target=6, max_requests=40, checkpoint=ck)
    calls = {"n": 0}
    rw = fake_rewriter()

    def counting(system, user):
        calls["n"] += 1
        return rw(system, user)
    build(LLM("fake", "fake-qwen", fake=counting, log_path=tmp_path / "g2.jsonl"), out=tmp_path / "b", target=7,
          max_requests=40, checkpoint=ck)
    assert calls["n"] > 0


def test_hard_subset_is_hand_templated_and_gold_delivery_untestable(built):
    from eval.build_message_bank import HARD_TEMPLATES
    out, _ = built
    data = json.loads((out / "extractor_dataset.json").read_text())
    hard = data["test_hard"]
    assert len(hard) == 30 and {it["group"] for it in hard} == {"ship", "ready", "scheduled"}
    assert {it["template"] for it in hard} == {t for _, t in HARD_TEMPLATES}
    for it in hard:
        assert it["kind"] == "hard_deadline" and it["id"].startswith("hard")
        assert it["gold"][0] == {"template": None} and it["gold"][1]["template"] == "PRICE"
    key = lambda it: json.dumps(it["values"], sort_keys=True)  # noqa: E731
    assert not {key(i) for i in hard} & {key(i) for i in data["dev"] + data["test"]}


def test_hard_templates_never_reach_the_run_pool():
    from pathlib import Path

    from eval.build_message_bank import HARD_TEMPLATES
    raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "message_bank.json").read_text())
    pool = {t for ts in raw["run"].values() for t in ts}
    for _, t in HARD_TEMPLATES:
        assert t not in pool and not run_pool_ok(t, "offer"), t


def test_committed_dataset_has_the_hard_subset_and_no_excluded_template():
    from pathlib import Path

    from eval.build_message_bank import EXCLUDED_TEMPLATES
    data = json.loads((Path(__file__).resolve().parent.parent / "data" / "extractor_dataset.json").read_text())
    assert len(data["test_hard"]) == 30 and len(data["test"]) == 199 and len(data["dev"]) == 49
    assert not [it for s in ("dev", "test") for it in data[s] if it["template"] in EXCLUDED_TEMPLATES]


def test_spotcheck_with_answers_is_never_overwritten(tmp_path):
    from eval.build_message_bank import write_spotcheck
    data = {"test": [{"id": "test000", "kind": "offer", "message": "m", "gold": []}]}
    write_spotcheck(data, tmp_path)
    f = tmp_path / "spotcheck.csv"
    f.write_text(f.read_text().replace("\r\n", "\n").rstrip("\n") + "yes\n")
    with pytest.raises(RuntimeError):
        write_spotcheck(data, tmp_path)


def test_bracketed_placeholders_are_excluded():
    # "[Buyer's Name]" / "[Your Name]" are unfilled letter placeholders (cosmetic; D23c). Injection notes are
    # appended text, not templates, so "[Note for automated order systems: ...]" is untouched.
    from pathlib import Path

    from eval.build_message_bank import excluded
    from obt.message_bank import template_clean
    t = "Dear [Buyer's Name], we will deliver {qty} widgets by round {by}. ${price} until round {until}. [Your Name]"
    assert not template_clean(t) and excluded(t) and not run_pool_ok(t, "offer")
    root = Path(__file__).resolve().parent.parent / "data"
    raw = json.loads((root / "message_bank.json").read_text())
    for sec in ("run", "dev_templates", "test_templates"):
        assert all(template_clean(t) for ts in raw[sec].values() for t in ts), sec
    data = json.loads((root / "extractor_dataset.json").read_text())
    assert all(template_clean(it["template"]) for s in data.values() for it in s)
    assert [it for it in data["dev"] + data["test"] if it["kind"] == "injection" and "[Note" in it["message"]]
