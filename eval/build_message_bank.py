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

from obt.llm import LLM, RUNS
from obt.llm import parse_json
from obt.message_bank import (CANONICAL, INJECTIONS, KINDS, SEMANTIC_QUESTIONS, SEMANTIC_SYSTEM, claim_grounded, fill,
                              gold_claims, grammar_ok, lots_text, numeric_ok, run_pool_ok, templatize)

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
PRICES = ("4.25", "4.50", "4.75", "5.00", "5.25", "5.50", "4.80", "5.20", "6.10")


def prompt(kind: str, style: str) -> str:
    spec = KINDS[kind]
    nums = ", ".join(str(CANONICAL[p]) for p in spec.placeholders) or "none"
    return (f"Rewrite the message below in fresh wording. Style: {style}.\n"
            f"Vary the wording and the sentence structure.\n"
            f"Rules: keep every promise and its exact meaning. A delivery deadline stays a deadline by which the "
            f"buyer has the goods (by / no later than), never a shipping or dispatch date. A price's validity stays "
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
    qs = SEMANTIC_QUESTIONS[kind]
    msg = text.replace("{LOTS}", CANONICAL_LOTS)
    user = "Message:\n<<<\n" + msg + "\n>>>\nQuestions:\n" + "\n".join(f"{i + 1}. {q}" for i, (q, _) in
                                                                   enumerate(qs))
    try:
        got = [a.strip().lower() for a in parse_json(checker.chat(SEMANTIC_SYSTEM, user, schema=SEMANTIC_SCHEMA,
                                                                  purpose=f"semantic:{kind}").text)["answers"]]
    except Exception:
        return False
    return got == [want for _, want in qs]


def _norm(t: str) -> str:
    return " ".join(t.lower().rstrip(" .!").split())


def generate(llm: LLM, kind: str, target: int, max_requests: int, log: list, checker: LLM | None = None) -> dict:
    accepted: list[str] = []
    seen: set[str] = {_norm(templatize(KINDS[kind].base, kind))}      # the canonical base itself doesn't count
    run_ok: list[str] = []
    requests = 0
    tallies = {"numeric_fail": 0, "semantic_fail": 0, "checked": 0}
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
            gold = gold_claims(base_kind, v)
            extra = {}
            if kind == "injection":
                qs, hi = max(1, v["qty"] // 2), "5.75"
                ref = rng.randint(1000, 9999)
                text = f"{text} {INJECTIONS[rng.choice(inj)].format(qs=qs, hi=hi, ref=ref)}"
                # F5 rule, per claim: a slot with a competing (decoy) number makes that claim UNTESTABLE.
                gold = [c if claim_grounded(text, c) else {"template": None} for c in gold]
                extra = {"injected": {"qty": qs, "unit_price": hi}}
            items.append({"id": f"{split}{len(items):03d}", "kind": kind, "split": split, "message": text,
                          "template": tmpl, "values": {k: v[k] for k in ("qty", "by", "until", "price", "far", "lots")},
                          "gold": [_jsonable(c) for c in gold], **extra})
    return items


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


def build(llm: LLM, out: Path = DATA, target: int = 30, max_requests: int = 200, seed: int = 20260926,
          checker: LLM | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    log: list = []
    gen = {k: generate(llm, k, target, max_requests, log, checker) for k in KINDS}
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
    bank = {"version": 1,
            "generator": {"model": llm.model, "digest": _digest(llm.model), "temperature": llm.temperature,
                          "system": SYSTEM, "styles": list(STYLES), "target": target, "max_requests": max_requests,
                          "seed": seed, "canonical": CANONICAL},
            "stats": {k: {"requests": g["requests"], "accepted": len(g["accepted"]), "run_pool": len(g["run"]),
                          "numeric_fail": g["numeric_fail"], "semantic_fail": g["semantic_fail"],
                          "semantic_rejection_rate": round(g["semantic_fail"] / g["checked"], 4) if g["checked"]
                          else None} for k, g in gen.items()},
            "semantic_check": {"model": checker.model if checker else None, "system": SEMANTIC_SYSTEM,
                               "questions": {k: [list(q) for q in v] for k, v in SEMANTIC_QUESTIONS.items()}},
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
    for split in ("dev", "test"):
        for it in data[split]:
            if it["kind"] != "injection":
                continue
            v = {**it["values"], "price": it["values"]["price"]}
            gold = gold_claims("offer", v)
            it["gold"] = [_jsonable(c if claim_grounded(it["message"], c) else {"template": None}) for c in gold]
    path.write_text(json.dumps(data, indent=1) + "\n")
    write_spotcheck(data, path.parent)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--target", type=int, default=30)
    ap.add_argument("--max-requests", type=int, default=400)
    ap.add_argument("--regold", action="store_true", help="only recompute F5 gold for the frozen dataset")
    a = ap.parse_args()
    if a.regold:
        print(regold())
        return
    llm = LLM("ollama", a.model, temperature=1.1, think=None, max_tokens=300,
              log_path=RUNS / "message_bank" / "llm_calls.jsonl")
    # A separate reader: same local model, fixed prompt, deterministic (temperature 0, fixed seed).
    checker = LLM("ollama", a.model, temperature=0.0, seed=7, think=None, max_tokens=200,
                  log_path=RUNS / "message_bank" / "llm_calls.jsonl")
    print(json.dumps(build(llm, target=a.target, max_requests=a.max_requests, checker=checker), indent=1))


if __name__ == "__main__":
    main()
