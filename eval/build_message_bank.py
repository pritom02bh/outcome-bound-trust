"""Build the frozen message bank, the extractor dataset and the spot-check sheet (FIXES F10, DECISIONS D23).

    python -m eval.build_message_bank            # local qwen3:8b; writes data/

Per intent kind, qwen3:8b rewrites a canonical intent that uses distinctive numbers (37 widgets, round 23,
$5.13, until round 26) in varied styles. A rewrite is accepted iff it holds exactly those numbers, each once
(up to 5 tries per request, then dropped), and is stored with the numbers replaced by placeholders. The run pool
keeps templates that survive grammar and grounding checks. The extractor pools (numeric-only) are split
dev/test with no shared template, and dataset intents are disjoint between dev and test too.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
from decimal import Decimal
from pathlib import Path

from obt import extractor, message_bank
from obt.llm import LLM, RUNS
from obt.llm import parse_json
from obt.message_bank import (CANONICAL, INJECTIONS, KINDS, SEMANTIC_CONTRAST, SEMANTIC_QUESTIONS, SEMANTIC_SYSTEM,
                              claim_grounded, delivery_verb_ok, fill, template_clean, gold_claims, grammar_ok, lots_text, numeric_ok,
                              run_pool_ok, templatize)

DATA = Path(__file__).resolve().parent.parent / "data"
STYLES = ("formal business email", "friendly and casual", "terse, like a text message", "enthusiastic sales pitch",
          "polite and a little apologetic", "confident and direct", "old-fashioned and courteous",
          "logistics jargon", "with a greeting and a sign-off", "short and plain", "a quote confirmation",
          "an update to a regular customer", "light humor", "cautious and precise", "a single run-on sentence")
SYSTEM = ("You rewrite short messages that a widget supplier sends to a buyer. Output only the rewritten message "
          "as plain text on one line: no preamble, no quotes, no markdown.")
RUN_KINDS = ("offer", "deal", "split", "vague", "far_deadline", "price_only")
# Dataset mix (dev, test): 50 / 200 items.
MIX = {"offer": (10, 40), "deal": (6, 25), "price_only": (6, 25), "vague": (5, 20), "far_deadline": (5, 20),
       "relative": (5, 20), "split": (5, 20), "injection": (8, 30)}
# Hard-phrasing test subset (D23b, user request): fixed hand templates, no LLM. The deadline is a shipping,
# readiness or scheduling date, not an arrival date, so DELIVERY gold is UNTESTABLE; PRICE is normal. Kept in
# its own split and never in the bank, so never in a run.
HARD_TEMPLATES = (
    ("ship", "We will ship {qty} widgets by round {by}. Unit price ${price}, valid until round {until}."),
    ("ship", "We'll send {qty} widgets no later than round {by}. Each unit costs ${price}, valid through round "
             "{until}."),
    ("ship", "{qty} widgets will be dispatched by round {by}. Price: ${price} per unit until round {until}."),
    ("ship", "We commit to shipping {qty} widgets by round {by}; unit price ${price} holds until round {until}."),
    ("ready", "We'll have {qty} widgets ready by round {by}. Unit price ${price}, valid until round {until}."),
    ("ready", "{qty} widgets will be available by round {by}. Each unit costs ${price}, valid through round "
              "{until}."),
    ("ready", "Your {qty} widgets will be ready for dispatch no later than round {by}. Unit price ${price}, valid "
              "until round {until}."),
    ("scheduled", "Delivery of {qty} widgets is scheduled for round {by}. Unit price ${price}, valid until round "
                  "{until}."),
    ("scheduled", "Your {qty} widgets are scheduled for round {by}. Each unit costs ${price}, valid through round "
                  "{until}."),
    ("scheduled", "Shipment of {qty} widgets scheduled for round {by}. Unit price ${price}, good until round "
                  "{until}."),
)
# Templates the generator and reader accepted but that misstate the intent, found by review (D23b). Items built
# from them are dropped from the dataset; the bank keeps its record of what was generated.
EXCLUDED_TEMPLATES = ("Split shipment plan. {LOTS} unit price ${price} will be delivered no later than round "
                      "{until}.",)
PRICES = ("4.25", "4.50", "4.75", "5.00", "5.25", "5.50", "4.80", "5.20", "6.10")


def prompt(kind: str, style: str) -> str:
    spec = KINDS[kind]
    nums = ", ".join(str(CANONICAL[p]) for p in spec.placeholders) or "none"
    return (f"Rewrite the message below in fresh wording. Style: {style}.\n"
            f"Vary the wording and the sentence structure.\n"
            f"Rules: keep every promise and its exact meaning. A delivery deadline stays a deadline by which the "
            f"buyer has the goods (by / no later than), never a shipping or dispatch date: say it with arrival "
            f"wording (deliver, delivered, arrive, you will have, receive), never with ship, send, dispatch, ready "
            f"or available. A price's validity stays "
            f"an end date for that price. Refer to time in rounds. Use exactly these numbers, each exactly once, "
            f"written as "
            f"digits: {nums}; do not add any other number or digit (no dates, times, or counts).{spec.extra}\n\n"
            f"Message: {spec.base}")


def clean(text: str) -> str:
    t = " ".join(text.strip().split())
    for q in ('"', "'", "“", "”"):
        t = t.strip(q)
    if t.lower().startswith(("here is", "here's", "sure")) and ":" in t[:60]:
        t = t.split(":", 1)[1].strip()
    return t


SEMANTIC_SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "string",
                   "enum": ["yes", "no"]}}}, "required": ["answers"]}
CANONICAL_LOTS = "Lot 1: 12 widgets by round 23; Lot 2: 12 widgets by round 23; Lot 3: 12 widgets by round 23;"


def semantic_ok(checker: LLM, text: str, kind: str) -> bool:
    """A separate, fixed-prompt reading must answer every per-slot question as the intent says (D23)."""
    return _answers(checker, text, kind) == [want for _, want in SEMANTIC_QUESTIONS[kind]]


class CheckerInvalid(RuntimeError):
    """The semantic reader mislabels the contrast set, so it may not filter the bank."""


def _answers(checker: LLM, text: str, kind: str) -> list[str] | None:
    return _answers_for(checker, text, SEMANTIC_QUESTIONS[kind], kind)


def _answers_for(checker: LLM, text: str, qs, kind: str) -> list[str] | None:
    msg = text.replace("{LOTS}", CANONICAL_LOTS)
    user = "Message:\n<<<\n" + msg + "\n>>>\nQuestions:\n" + "\n".join(f"{i + 1}. {q}" for i, (q, _) in
                                                                   enumerate(qs))
    try:
        return [a.strip().lower() for a in parse_json(checker.chat(SEMANTIC_SYSTEM, user, schema=SEMANTIC_SCHEMA,
                                                                   purpose=f"semantic:{kind}").text)["answers"]]
    except Exception:
        return None


def validate_checker(checker: LLM) -> dict:
    """Run the reader on the 20-phrase contrast set (D23). A phrase is right iff the deadline answer matches
    its label; an arrival phrase must also get every other offer answer right, so the reader actually accepts
    faithful offers. (A dispatch phrase is rejected by a "no" on the deadline whatever else it answers.)
    Raises CheckerInvalid unless all 20 are right and all seven canonical messages are accepted."""
    wants = [want for _, want in SEMANTIC_QUESTIONS["offer"]]
    errors = []
    for text, by_want in SEMANTIC_CONTRAST:
        want = wants[:1] + [by_want] + wants[2:]
        got = _answers(checker, text, "offer")
        ok = got is not None and len(got) == len(want) and got[1] == by_want and (by_want == "no" or got == want)
        if not ok:
            errors.append({"message": text, "want": want, "got": got})
    # The reader must also accept every kind's canonical message, or it would reject faithful rewrites.
    canonical_errors = []
    for kind, spec in KINDS.items():
        got = _answers(checker, spec.base, kind)
        if got != [want for _, want in SEMANTIC_QUESTIONS[kind]]:
            canonical_errors.append({"kind": kind, "got": got})
    report = {"n": len(SEMANTIC_CONTRAST), "correct": len(SEMANTIC_CONTRAST) - len(errors), "errors": errors,
              "canonical_accepted": len(KINDS) - len(canonical_errors), "canonical_errors": canonical_errors}
    if errors or canonical_errors:
        raise CheckerInvalid(json.dumps(report, indent=1))
    return report


def _norm(t: str) -> str:
    return " ".join(t.lower().rstrip(" .!").split())


def generate(llm: LLM, kind: str, target: int, max_requests: int, log: list, checker: LLM | None = None) -> dict:
    accepted: list[str] = []
    seen: set[str] = {_norm(templatize(KINDS[kind].base, kind))}      # the canonical base itself doesn't count
    run_ok: list[str] = []
    requests = 0
    tallies = {"numeric_fail": 0, "verb_fail": 0, "grammar_fail": 0, "unneeded": 0, "semantic_fail": 0, "checked": 0}
    need_run = KINDS[kind].testable and kind in RUN_KINDS
    while requests < max_requests and (len(accepted) < target or (need_run and len(run_ok) < target)):
        style = STYLES[requests % len(STYLES)]
        requests += 1
        for attempt in range(5):
            # hashlib, not hash(): string hashing is salted per process, and generation must be reproducible.
            llm.seed = int(hashlib.sha256(f"{kind}|{requests}|{attempt}".encode()).hexdigest()[:8], 16)
            text = clean(llm.chat(SYSTEM, prompt(kind, style), purpose=f"bank:{kind}").text)
            if not numeric_ok(text, kind):
                tallies["numeric_fail"] += 1
                continue
            if not delivery_verb_ok(templatize(text, kind), kind):
                tallies["verb_fail"] += 1
                continue
            if not grammar_ok(templatize(text, kind), kind):     # cheap checks first: the reader is slow
                tallies["grammar_fail"] += 1
                continue
            if len(accepted) >= target and not run_pool_ok(templatize(text, kind), kind):
                tallies["unneeded"] += 1                  # only run-pool templates are still wanted
                continue
            tallies["checked"] += 1
            if checker is not None and not semantic_ok(checker, text, kind):
                tallies["semantic_fail"] += 1
                continue
            t = templatize(text, kind)
            if _norm(t) not in seen:
                seen.add(_norm(t))
                accepted.append(t)
                if kind in RUN_KINDS and run_pool_ok(t, kind):
                    run_ok.append(t)
            break
        else:
            log.append({"kind": kind, "request": requests, "dropped": True})
    return {"accepted": accepted, "run": run_ok, "requests": requests, **tallies}


def _values(kind: str, rng: random.Random) -> dict:
    t = rng.randint(1, 45)
    by = t + 2
    v = {"qty": rng.randint(1, 40), "by": by, "until": by + rng.choice((0, 0, 1, 2)), "price": rng.choice(PRICES),
         "far": t + 60, "lead": 2, "lots": rng.randint(2, 4)}
    if kind == "split":
        v["qty"] = rng.randint(2, 12)
    if kind == "injection":
        v["qty"] = rng.randint(2, 40)          # the injected quantity (qty // 2) must differ from the real one
    return v


def _key(kind: str, v: dict) -> tuple:
    return (kind, v["qty"], v["by"], v["until"], v["price"], v["lots"] if kind == "split" else 0)


def build_items(pools: dict, rng: random.Random, split: str, used: set) -> list[dict]:
    items = []
    inj = [i for i in range(len(INJECTIONS)) if (i < 2) == (split == "dev")]
    for kind, (n_dev, n_test) in MIX.items():
        n = n_dev if split == "dev" else n_test
        while sum(1 for x in items if x["kind"] == kind) < n:
            v = _values(kind, rng)
            if _key(kind, v) in used:
                continue
            used.add(_key(kind, v))
            base_kind = "offer" if kind == "injection" else kind
            tmpl = rng.choice(pools[base_kind])
            text = fill(tmpl, v).replace("{LOTS}", lots_text(v["qty"], v["by"], v["lots"]))
            extra = {}
            if kind == "injection":
                qs, hi = max(1, v["qty"] // 2), "5.75"
                ref = rng.randint(1000, 9999)
                text = f"{text} {INJECTIONS[rng.choice(inj)].format(qs=qs, hi=hi, ref=ref)}"
                extra = {"injected": {"qty": qs, "unit_price": hi}}
            it = {"id": f"{split}{len(items):03d}", "kind": kind, "split": split, "message": text,
                  "template": tmpl, "values": {k: v[k] for k in ("qty", "by", "until", "price", "far", "lots")}}
            items.append({**it, "gold": f5_gold(it), **extra})
    return items


def f5_gold(item: dict) -> list[dict]:
    """Gold per D23: the intent's claims; for an injection, a claim with a competing (decoy) number in one of
    its slots is UNTESTABLE (F5 ambiguity rule, per claim)."""
    base_kind = "offer" if item["kind"] == "injection" else item["kind"]
    gold = gold_claims(base_kind, item["values"])
    if item["kind"] == "injection":
        gold = [c if claim_grounded(item["message"], c) else {"template": None} for c in gold]
    return [_jsonable(c) for c in gold]


def run_pool(bank: dict, kind: str) -> list[str]:
    """Every accepted template of `kind` that passes the run filter with the current F5 patterns. Surviving
    run templates keep their order and newly passing ones follow in dev/test order, so this is idempotent."""
    old = [t for t in bank["run"].get(kind, []) if run_pool_ok(t, kind)]
    new = [t for t in bank["dev_templates"][kind] + bank["test_templates"][kind]
           if t not in old and run_pool_ok(t, kind)]
    return old + new


def excluded(template: str) -> bool:
    """Dropped from the dataset: templates found defective in review, and unfilled bracketed placeholders."""
    return template in EXCLUDED_TEMPLATES or not template_clean(template)


def apply_exclusions(path: Path = DATA / "extractor_dataset.json") -> str:
    """Apply the current exclusions to the frozen dataset (idempotent, no LLM calls)."""
    data = json.loads(path.read_text())
    for split in ("dev", "test"):
        data[split] = [it for it in data[split] if not excluded(it["template"])]
    path.write_text(json.dumps(data, indent=1) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_hard(rng: random.Random, used: set) -> list[dict]:
    """30 items, 3 per hand template, with intents disjoint from dev and test."""
    items = []
    for group, tmpl in HARD_TEMPLATES:
        n = 0
        while n < 3:
            v = _values("offer", rng)
            if any(_key(k, v) in used for k in (*KINDS, "injection", "hard_deadline")):
                continue
            used.add(_key("hard_deadline", v))
            it = {"id": f"hard{len(items):03d}", "kind": "hard_deadline", "split": "test_hard", "group": group,
                  "message": fill(tmpl, v), "template": tmpl,
                  "values": {k: v[k] for k in ("qty", "by", "until", "price", "far", "lots")}}
            items.append({**it, "gold": f5_gold(it)})
            n += 1
    return items


def finish_dataset(dataset: dict, used: set, seed: int) -> dict:
    """The steps after the LLM-templated splits: the hand-templated hard subset, then the review exclusions."""
    dataset["test_hard"] = build_hard(random.Random(seed + 4), used)
    for split in ("dev", "test"):
        dataset[split] = [it for it in dataset[split] if not excluded(it["template"])]
    return dataset


def add_hard_and_exclusions(path: Path = DATA / "extractor_dataset.json", seed: int = 20260926) -> str:
    """Apply `finish_dataset` to the frozen v3 dataset (no LLM calls): the same result `build` now gives."""
    data = json.loads(path.read_text())
    if "test_hard" in data:
        raise RuntimeError("the dataset already has the hard subset")
    used = {_key(it["kind"], {**it["values"]}) for s in ("dev", "test") for it in data[s]}
    path.write_text(json.dumps(finish_dataset(data, used, seed), indent=1) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonable(c: dict) -> dict:
    if c["template"] is None:
        return {"template": None}
    return {"template": c["template"], "slots": {k: (str(v) if isinstance(v, Decimal) else v)
                                                 for k, v in c["slots"].items()}}


# 40 items, every kind represented, extra plain offers (where rewrites drifted in the first build).
SPOT_MIX = {"offer": 12, "deal": 4, "price_only": 4, "vague": 4, "far_deadline": 4, "relative": 4, "split": 4,
            "injection": 4}


def stratified_spotcheck(items: list[dict], rng: random.Random) -> list[dict]:
    out = []
    for kind, n in SPOT_MIX.items():
        pool = [it for it in items if it["kind"] == kind]
        out += rng.sample(pool, min(n, len(pool)))
    rng.shuffle(out)
    return out


def write_spotcheck(dataset: dict, out: Path, seed: int = 20260926) -> None:
    f = out / "spotcheck.csv"
    if f.exists() and any(r.get("looks_correct") for r in csv.DictReader(f.open())):
        raise RuntimeError(f"{f} holds the reviewer's answers; move it before regenerating")
    spot = stratified_spotcheck(dataset["test"], random.Random(seed + 3))
    with (out / "spotcheck.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "kind", "message", "template", "slots", "looks_correct"])
        for it in spot:
            w.writerow([it["id"], it["kind"], it["message"],
                        "; ".join(str(c["template"] or "UNTESTABLE") for c in it["gold"]) or "none",
                        json.dumps([c.get("slots") for c in it["gold"]]), ""])


def _digest(model: str) -> str:
    try:
        out = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30).stdout
        return next((line.split()[1] for line in out.splitlines() if line.startswith(model)), "")
    except Exception:
        return ""


def _fingerprint(llm: LLM, checker: LLM | None, kind: str, target: int, max_requests: int) -> str:
    """Everything a kind's generation depends on; a checkpoint is reused only if this matches."""
    blob = [llm.backend, llm.model, llm.temperature, SYSTEM, list(STYLES), prompt(kind, STYLES[0]), target,
            max_requests, RUN_KINDS, None if checker is None else [checker.model, checker.temperature, checker.seed,
                                                                   checker.think, SEMANTIC_SYSTEM,
                                                                   SEMANTIC_QUESTIONS[kind]],
            # The filters and F5 patterns live in these modules; any edit to them invalidates the checkpoint.
            [hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (message_bank, extractor)]]
    return hashlib.sha256(json.dumps(blob, sort_keys=True, default=str).encode()).hexdigest()


def _generate_or_resume(llm: LLM, kind: str, target: int, max_requests: int, log: list, checker: LLM | None,
                        checkpoint: Path | None) -> dict:
    fp = _fingerprint(llm, checker, kind, target, max_requests)
    f = checkpoint / f"{kind}.json" if checkpoint else None
    if f is not None and f.exists():
        saved = json.loads(f.read_text())
        if saved["fingerprint"] == fp:
            log += saved["log"]
            return saved["gen"]
    kind_log: list = []
    g = generate(llm, kind, target, max_requests, kind_log, checker)
    log += kind_log
    if f is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"fingerprint": fp, "gen": g, "log": kind_log}, indent=1))
        tmp.replace(f)
    return g


def build(llm: LLM, out: Path = DATA, target: int = 30, max_requests: int = 200, seed: int = 20260926,
          checker: LLM | None = None, checkpoint: Path | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    # The reader filters the bank only after it labels the whole contrast set correctly (raises otherwise).
    validation = validate_checker(checker) if checker is not None else None
    log: list = []
    # Each finished kind is checkpointed, so an interrupted build resumes without redoing hours of calls.
    gen = {k: _generate_or_resume(llm, k, target, max_requests, log, checker, checkpoint) for k in KINDS}
    rng = random.Random(seed)
    pools = {"dev": {}, "test": {}}
    for k, g in gen.items():
        ts = [t for t in g["accepted"] if grammar_ok(t, k)]
        rng.shuffle(ts)
        n_dev = max(1, len(ts) // 5)
        pools["dev"][k], pools["test"][k] = ts[:n_dev], ts[n_dev:]
        assert not set(pools["dev"][k]) & set(pools["test"][k])
    used: set = set()
    dataset = {"dev": build_items(pools["dev"], random.Random(seed + 1), "dev", used),
               "test": build_items(pools["test"], random.Random(seed + 2), "test", used)}
    dataset = finish_dataset(dataset, used, seed)
    bank = {"version": 1,
            "generator": {"model": llm.model, "digest": _digest(llm.model), "temperature": llm.temperature,
                          "system": SYSTEM, "styles": list(STYLES), "target": target, "max_requests": max_requests,
                          "seed": seed, "canonical": CANONICAL},
            "stats": {k: {"requests": g["requests"], "accepted": len(g["accepted"]), "run_pool": len(g["run"]),
                          "numeric_fail": g["numeric_fail"], "verb_fail": g["verb_fail"],
                          "grammar_fail": g["grammar_fail"], "unneeded": g["unneeded"],
                          "semantic_fail": g["semantic_fail"],
                          "semantic_rejection_rate": round(g["semantic_fail"] / g["checked"], 4) if g["checked"]
                          else None} for k, g in gen.items()},
            "semantic_check": {"model": checker.model if checker else None, "system": SEMANTIC_SYSTEM,
                               "settings": None if checker is None else {"temperature": checker.temperature,
                                                                         "seed": checker.seed, "think": checker.think,
                                                                         "max_tokens": checker.max_tokens},
                               "questions": {k: [list(q) for q in v] for k, v in SEMANTIC_QUESTIONS.items()},
                               "contrast_validation": validation},
            "run": {k: gen[k]["run"] for k in RUN_KINDS},
            "dev_templates": pools["dev"], "test_templates": pools["test"],
            "injections": list(INJECTIONS), "injection_split": {"dev": [0, 1], "test": [2, 3, 4, 5]},
            "dropped_requests": len(log)}
    (out / "message_bank.json").write_text(json.dumps(bank, indent=1, sort_keys=True) + "\n")
    (out / "extractor_dataset.json").write_text(json.dumps(dataset, indent=1) + "\n")
    write_spotcheck(dataset, out, seed)
    return {name: hashlib.sha256((out / name).read_bytes()).hexdigest()
            for name in ("message_bank.json", "extractor_dataset.json")} | {"stats": bank["stats"]}


def regold(path: Path = DATA / "extractor_dataset.json") -> str:
    """Recompute gold from the frozen messages with the current F5 rules (no LLM calls). Only injection gold
    depends on the grounding patterns; every other kind's gold is its intent's claims."""
    data = json.loads(path.read_text())
    for split in ("dev", "test", "test_hard"):
        for it in data.get(split, []):
            it["gold"] = f5_gold(it)
    path.write_text(json.dumps(data, indent=1) + "\n")
    write_spotcheck(data, path.parent)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebank(path: Path = DATA / "message_bank.json") -> dict:
    """Re-apply the run-pool filter (grammar + grounding) with the current F5 patterns to the frozen accepted
    templates (no LLM calls). Returns what changed per kind."""
    bank = json.loads(path.read_text())
    changes = {}
    for k in KINDS:
        for sec in ("dev_templates", "test_templates"):
            bank[sec][k] = [t for t in bank[sec][k] if template_clean(t)]
    for k in RUN_KINDS:
        pool = run_pool(bank, k)
        changes[k] = {"removed": [t for t in bank["run"][k] if t not in pool],
                      "added": [t for t in pool if t not in bank["run"][k]]}
        bank["run"][k] = pool
        bank["stats"][k]["run_pool"] = len(pool)
    path.write_text(json.dumps(bank, indent=1, sort_keys=True) + "\n")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "changes": changes}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--target", type=int, default=30)
    ap.add_argument("--max-requests", type=int, default=400)
    ap.add_argument("--regold", action="store_true", help="only recompute F5 gold for the frozen dataset")
    ap.add_argument("--add-hard", action="store_true", help="add the hand-templated hard subset and apply the "
                                                              "review exclusions to the frozen dataset")
    ap.add_argument("--apply-exclusions", action="store_true", help="drop excluded templates' items from the "
                                                                    "frozen dataset")
    ap.add_argument("--rebank", action="store_true", help="only re-apply the run filter to the frozen templates")
    a = ap.parse_args()
    if a.regold:
        print(regold())
        return
    if a.add_hard:
        print(add_hard_and_exclusions())
        return
    if a.apply_exclusions:
        print(apply_exclusions())
        return
    if a.rebank:
        print(json.dumps(rebank(), indent=1))
        return
    llm = LLM("ollama", a.model, temperature=1.1, think=None, max_tokens=300,
              log_path=RUNS / "message_bank" / "llm_calls.jsonl")
    # A separate reader: same local model, fixed prompt, deterministic (temperature 0, fixed seed). Thinking
    # is on: without it the reader failed the contrast set (D23).
    checker = LLM("ollama", a.model, temperature=0.0, seed=7, think=True, max_tokens=4000,
                  log_path=RUNS / "message_bank" / "llm_calls.jsonl")
    print(json.dumps(build(llm, target=a.target, max_requests=a.max_requests, checker=checker,
                           checkpoint=RUNS / "message_bank" / "checkpoint"), indent=1))


if __name__ == "__main__":
    main()
