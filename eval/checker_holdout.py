"""Held-out test of the frozen semantic reader (F10, DECISIONS D23a; user request).

    python -m eval.checker_holdout          # local qwen3:8b, the frozen reader; writes runs/message_bank/v3/

The reader's prompt was iterated against SEMANTIC_CONTRAST, so that score is not a clean estimate. This is a
second, fresh set of 20 deadline phrasings written after the prompt was frozen: new verbs, new sentence
structures, new numbers, and no sentence, deadline verb or number shared with SEMANTIC_CONTRAST or the few-shot
examples. It is run once with no prompt change. The question wording is the frozen offer question set with only
its numbers substituted to match each phrase.
"""
from __future__ import annotations

import json

from obt.llm import LLM, RUNS
from obt.message_bank import SEMANTIC_QUESTIONS

# (deadline sentence, qty, by, price, until, label). label: does the buyer HAVE the goods by `by`?
# Run 1 (D23b): 18/20 overall, 20/20 on the deadline question. Its two misses were answer-key errors: in two
# items the validity round equalled the delivery round, so "is round U the delivery deadline?" was truly yes.
# Kept unchanged as the record of run 1.
HOLDOUT_RUN1: tuple[tuple[str, int, int, str, int, str], ...] = (
    ("Plan on {q} widgets turning up at your plant by round {b}.", 14, 31, "4.60", 34, "yes"),
    ("By round {b}, {q} widgets will be on your premises.", 22, 18, "4.95", 19, "yes"),
    ("Our driver brings {q} widgets to your unloading bay no later than round {b}.", 10, 40, "5.35", 42, "yes"),
    ("Count on having {q} widgets on your shelves by round {b}.", 30, 13, "4.40", 13, "yes"),
    ("The {q} widgets will be sitting in your stockroom by round {b}.", 16, 27, "5.65", 29, "yes"),
    ("Your team will unload our {q} widgets at your plant no later than round {b}.", 8, 35, "4.85", 36, "yes"),
    ("You can expect to be holding {q} widgets by round {b}.", 25, 20, "5.45", 21, "yes"),
    ("All {q} widgets will be stocked in your storeroom by round {b}.", 11, 44, "4.70", 47, "yes"),
    ("Guaranteed: {q} widgets physically in your building by round {b}.", 19, 15, "5.15", 15, "yes"),
    ("Our courier sets {q} widgets down inside your gates by round {b}.", 27, 38, "4.55", 39, "yes"),
    ("We will box up {q} widgets by round {b}.", 14, 31, "4.60", 34, "no"),
    ("By round {b}, {q} widgets will roll off our assembly line.", 22, 18, "4.95", 19, "no"),
    ("{q} widgets will be crated at our plant no later than round {b}.", 10, 40, "5.35", 42, "no"),
    ("We'll put {q} widgets on the freight train by round {b}.", 30, 13, "4.40", 13, "no"),
    ("The {q} widgets will depart our depot by round {b}.", 16, 27, "5.65", 29, "no"),
    ("Our crew will pick and stage {q} widgets for transport no later than round {b}.", 8, 35, "4.85", 36, "no"),
    ("{q} widgets will be booked onto a vessel by round {b}.", 25, 20, "5.45", 21, "no"),
    ("We will manufacture {q} widgets by round {b}.", 11, 44, "4.70", 47, "no"),
    ("{q} widgets will be passed to the courier by round {b}.", 19, 15, "5.15", 15, "no"),
    ("The {q} widgets will be released from our stock for transport by round {b}.", 27, 38, "4.55", 39, "no"),
)
# Run 2 (user decision, option C): a completely fresh set, written after run 1 and run exactly once. New verbs,
# structures and numbers (disjoint from the tuning set and from run 1), and the validity round never equals the
# delivery round (enforced by a test).
HOLDOUT_RUN2: tuple[tuple[str, int, int, str, int, str], ...] = (
    ("Rest assured, {q} widgets will be in your inventory by round {b}.", 6, 17, "4.35", 24, "yes"),
    ("You will own {q} widgets, on your floor, no later than round {b}.", 7, 24, "5.05", 28, "yes"),
    ("{q} widgets will be standing in your yard no later than round {b}.", 3, 33, "4.65", 41, "yes"),
    ("Our truck drops {q} widgets off with your staff by round {b}.", 24, 41, "5.55", 43, "yes"),
    ("Round {b} is the latest your crew signs for our {q} widgets.", 28, 46, "4.45", 48, "yes"),
    ("Consider {q} widgets yours, on your racks, by round {b}.", 32, 45, "5.25", 49, "yes"),
    ("We'll haul {q} widgets right to your front office by round {b}.", 33, 28, "4.75", 32, "yes"),
    ("By round {b} your storekeeper will have counted in our {q} widgets.", 41, 32, "5.60", 33, "yes"),
    ("Expect {q} widgets to be on your factory floor by round {b}.", 43, 53, "4.90", 55, "yes"),
    ("It is our pledge that {q} widgets rest in your vault by round {b}.", 48, 57, "5.30", 58, "yes"),
    ("Rest assured, {q} widgets will be machined by round {b}.", 6, 17, "4.35", 24, "no"),
    ("{q} widgets will be painted and labeled no later than round {b}.", 7, 24, "5.05", 28, "no"),
    ("{q} widgets will be lifted onto our lorry no later than round {b}.", 3, 33, "4.65", 41, "no"),
    ("Our mill finishes {q} widgets by round {b}.", 24, 41, "5.55", 43, "no"),
    ("Round {b} is the latest we wrap our {q} widgets for the road.", 28, 46, "4.45", 48, "no"),
    ("Consider {q} widgets tested and approved in our lab by round {b}.", 32, 45, "5.25", 49, "no"),
    ("We'll invoice and tag {q} widgets for the haulier by round {b}.", 33, 28, "4.75", 32, "no"),
    ("By round {b} our foreman will have signed out {q} widgets to the trucking firm.", 41, 32, "5.60", 33, "no"),
    ("Expect {q} widgets to be on a flatbed heading your way by round {b}.", 43, 53, "4.90", 55, "no"),
    ("It is our pledge that {q} widgets exit our compound by round {b}.", 48, 57, "5.30", 58, "no"),
)
HOLDOUT_SETS = {1: HOLDOUT_RUN1, 2: HOLDOUT_RUN2}
TAIL = " Each widget costs ${p}, a price good through round {u}."


def message(sent: str, q: int, b: int, p: str, u: int) -> str:
    return sent.format(q=q, b=b) + TAIL.format(p=p, u=u)


def questions(q: int, b: int, p: str, u: int) -> list[tuple[str, str]]:
    """The frozen offer questions with the canonical numbers (37, round 23, $5.13, round 26) swapped out."""
    out = []
    for text, want in SEMANTIC_QUESTIONS["offer"]:
        text = (text.replace("37 widgets", "\0Q").replace("round 23", "\0B").replace("$5.13", "\0P")
                .replace("round 26", "\0U"))
        out.append((text.replace("\0Q", f"{q} widgets").replace("\0B", f"round {b}").replace("\0P", f"${p}")
                    .replace("\0U", f"round {u}"), want))
    return out


def run_holdout(checker: LLM, run: int = 2) -> dict:
    from eval.build_message_bank import _answers_for
    items = []
    for sent, q, b, p, u, label in HOLDOUT_SETS[run]:
        qs = questions(q, b, p, u)
        want = [w for _, w in qs]
        want[1] = label
        got = _answers_for(checker, message(sent, q, b, p, u), qs, "holdout")
        by_ok = got is not None and len(got) == len(want) and got[1] == label
        # Same scoring as the contrast set: an arrival phrase must also be fully accepted.
        ok = by_ok and (label == "no" or got == want)
        items.append({"message": message(sent, q, b, p, u), "label": label, "want": want, "got": got,
                      "deadline_ok": by_ok, "ok": ok})
    return {"n": len(items), "correct": sum(i["ok"] for i in items),
            "deadline_correct": sum(i["deadline_ok"] for i in items), "items": items}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True, choices=(1, 2))
    run = ap.parse_args().run
    out = RUNS / "message_bank" / "v3" / f"checker_holdout_run{run}.json"
    if out.exists() or (run == 1 and (RUNS / "message_bank" / "v3" / "checker_holdout.json").exists()):
        raise SystemExit(f"run {run} was already made; a held-out set is run exactly once")
    checker = LLM("ollama", "qwen3:8b", temperature=0.0, seed=7, think=True, max_tokens=4000,
                  log_path=RUNS / "message_bank" / "v3" / "llm_calls.jsonl")
    rep = run_holdout(checker, run)
    out.write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({k: rep[k] for k in ("n", "correct", "deadline_correct")}))
    for i in rep["items"]:
        if not i["ok"]:
            print("WRONG", i["label"], i["got"], i["message"])


if __name__ == "__main__":
    main()
