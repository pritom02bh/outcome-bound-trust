"""Held-out reader test (D23a): fresh phrasings, disjoint from the tuning contrast set and the few-shot."""
import json
import re

from eval.checker_holdout import HOLDOUT_RUN1, HOLDOUT_RUN2, message, questions, run_holdout

HOLDOUT = HOLDOUT_RUN1
from obt.llm import LLM
from obt.message_bank import SEMANTIC_CONTRAST, SEMANTIC_SYSTEM

TUNING_VERBS = ("deliver", "arriv", "receiv", "ship", "send", "dispatch", "ready", "available", "leave", "loaded",
                "hand", "production", "complet", "post", "go out", "pack", "transit", "mail", "facility", "reach",
                "dock", "land", "possession", "get ", "warehouse", "door", "pickup", "collection")


def test_holdout_is_balanced():
    labels = [h[-1] for h in HOLDOUT]
    assert len(HOLDOUT) == 20 and labels.count("yes") == 10 and labels.count("no") == 10
    assert len({h[0] for h in HOLDOUT}) == 20


def test_holdout_shares_no_sentence_verb_or_number_with_tuning():
    tuning = [m for m, _ in SEMANTIC_CONTRAST] + [SEMANTIC_SYSTEM]
    tuning_nums = {n for t in tuning for n in re.findall(r"\d+(?:\.\d+)?", t)}
    for sent, q, b, p, u, _ in HOLDOUT:
        low = sent.lower()
        assert not any(v in low for v in TUNING_VERBS), sent
        assert not {str(q), str(b), p, str(u)} & tuning_nums, sent
        assert all(sent.format(q=q, b=b) not in t for t in tuning)


def test_questions_are_the_frozen_wording_with_numbers_swapped():
    qs = questions(14, 31, "4.60", 34)
    assert "14 widgets" in qs[0][0] and "round 31" in qs[1][0] and "$4.60" in qs[2][0] and "round 34" in qs[3][0]
    assert "round 34" in qs[4][0] and not any(n in q for q, _ in qs for n in ("37", "23", "5.13", "26"))


def test_scoring(tmp_path):
    def reader(system, user):
        msg = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
        label = next(h[-1] for h in HOLDOUT if message(*h[:5]) == msg)
        return json.dumps({"answers": ["yes", label, "yes", "yes", "no"]})
    rep = run_holdout(LLM("fake", "r", fake=reader, log_path=tmp_path / "c.jsonl"), 1)
    assert rep["correct"] == 20 and rep["deadline_correct"] == 20
    yes = LLM("fake", "r", fake=lambda s, u: json.dumps({"answers": ["yes"] * 4 + ["no"]}),
              log_path=tmp_path / "c.jsonl")
    assert run_holdout(yes, 1)["correct"] == 10


RUN1_WORDS = ("turn", "premises", "bring", "unload", "shel", "sitting", "stock", "holding", "storeroom", "building",
              "courier", "gate", "box", "roll", "assembl", "crate", "freight", "depart", "depot", "stage", "vessel",
              "manufactur", "passed", "released", "transport", "plant", "guarantee", "count on")


def test_run2_is_balanced_fresh_and_disjoint_from_tuning_and_run1():
    labels = [h[-1] for h in HOLDOUT_RUN2]
    assert len(HOLDOUT_RUN2) == 20 and labels.count("yes") == 10 and labels.count("no") == 10
    tuning = [m for m, _ in SEMANTIC_CONTRAST] + [SEMANTIC_SYSTEM]
    tuning_nums = {n for t in tuning for n in re.findall(r"\d+(?:\.\d+)?", t)}
    run1_nums = {str(x) for h in HOLDOUT_RUN1 for x in h[1:5]}
    for sent, q, b, p, u, _ in HOLDOUT_RUN2:
        low = sent.lower()
        assert not any(v in low for v in TUNING_VERBS + RUN1_WORDS), sent
        assert not {str(q), str(b), p, str(u)} & (tuning_nums | run1_nums), sent
        assert sent not in {h[0] for h in HOLDOUT_RUN1}


def test_run2_validity_round_never_equals_delivery_round():
    # Run 1's two misses were answer-key errors from exactly this (D23b).
    assert all(u != b for _, _, b, _, u, _ in HOLDOUT_RUN2)


def test_run1_is_kept_as_recorded():
    # Four items share b == u; only the two arrival ones are scored on the "round U is not the deadline" answer.
    assert {(b, u, lab) for _, _, b, _, u, lab in HOLDOUT_RUN1 if b == u} == {
        (13, 13, "yes"), (15, 15, "yes"), (13, 13, "no"), (15, 15, "no")}


def test_run2_scoring(tmp_path):
    def reader(system, user):
        msg = user.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
        label = next(h[-1] for h in HOLDOUT_RUN2 if message(*h[:5]) == msg)
        return json.dumps({"answers": ["yes", label, "yes", "yes", "no"]})
    assert run_holdout(LLM("fake", "r", fake=reader, log_path=tmp_path / "c.jsonl"), 2)["correct"] == 20
