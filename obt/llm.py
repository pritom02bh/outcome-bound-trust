"""LLM backends: local ollama by default, OpenAI only with OBT_ALLOW_PAID=1.

Every call (cache hits included) is appended to `runs/llm_calls.jsonl` with model,
tokens and latency. Paid calls also go through `CostMeter`, which keeps a running
total on disk and refuses any call once the hard cap is reached.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RUNS = Path(__file__).resolve().parent.parent / "runs"

DEFAULT_MODEL = "gpt-oss:20b"
HARD_CAP_USD = 13.0

# USD per 1M tokens (input, output). Fill in real prices before any paid run; a
# model missing here can't be called on the paid backend (fails closed).
PAID_PRICES: dict[str, tuple[float, float]] = {}


class PaidCallRefused(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class LLMReply:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    cached: bool = False


class CostMeter:
    """Persistent running total of paid spend with a hard stop."""

    def __init__(self, path: Path | None = None, cap: float = HARD_CAP_USD) -> None:
        self.path = path or RUNS / "cost_ledger.json"
        self.cap = cap

    def spent(self) -> float:
        try:
            return float(json.loads(self.path.read_text())["spent_usd"])
        except (FileNotFoundError, KeyError, ValueError):
            return 0.0

    def price(self, model: str) -> tuple[float, float]:
        if model not in PAID_PRICES:
            raise PaidCallRefused(f"no price configured for {model}; refusing paid call")
        return PAID_PRICES[model]

    def check(self, model: str, est_prompt_tokens: int, max_completion_tokens: int) -> None:
        pin, pout = self.price(model)
        worst = (est_prompt_tokens * pin + max_completion_tokens * pout) / 1e6
        if self.spent() + worst > self.cap:
            raise BudgetExceeded(f"${self.spent():.4f} spent; next call could pass the ${self.cap} cap")

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pin, pout = self.price(model)
        cost = (prompt_tokens * pin + completion_tokens * pout) / 1e6
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"spent_usd": self.spent() + cost}))
        return cost


class LLM:
    def __init__(self, backend: str = "ollama", model: str = DEFAULT_MODEL, *, temperature: float = 0.0,
                 seed: int = 0, think: str | None = "low", log_path: Path | None = None,
                 cache_dir: Path | None = None, fake: Callable[[str, str], str] | None = None,
                 max_tokens: int = 4096, meter: CostMeter | None = None, run_tag: str = "") -> None:
        if backend not in ("ollama", "openai", "fake"):
            raise ValueError(backend)
        if backend == "openai" and os.environ.get("OBT_ALLOW_PAID") != "1":
            raise PaidCallRefused("openai backend needs OBT_ALLOW_PAID=1")
        if backend == "fake" and fake is None:
            raise ValueError("fake backend needs a callable")
        self.backend = backend
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.think = think
        self.log_path = log_path or RUNS / "llm_calls.jsonl"
        self.cache_dir = cache_dir
        self.fake = fake
        self.max_tokens = max_tokens
        self.meter = meter or CostMeter()
        self.run_tag = run_tag
        self.calls = 0
        self.tokens = 0
        self.latency = 0.0
        self.by_purpose: dict[str, dict[str, float]] = {}

    def _key(self, system: str, user: str, schema: dict | None) -> str:
        blob = json.dumps([self.backend, self.model, self.temperature, self.seed, self.think,
                           system, user, schema], sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def chat(self, system: str, user: str, schema: dict | None = None, purpose: str = "") -> LLMReply:
        key = self._key(system, user, schema)
        cache_file = self.cache_dir / f"{key}.json" if self.cache_dir else None
        if cache_file is not None and cache_file.exists():
            d = json.loads(cache_file.read_text())
            reply = LLMReply(d["text"], d["prompt_tokens"], d["completion_tokens"], 0.0, cached=True)
        else:
            t0 = time.perf_counter()
            if self.backend == "fake":
                text, pt, ct = self.fake(system, user), len(system + user) // 4, 0
            elif self.backend == "ollama":
                text, pt, ct = self._ollama(system, user, schema)
            else:
                text, pt, ct = self._openai(system, user, schema)
            reply = LLMReply(text, pt, ct, time.perf_counter() - t0)
            if cache_file is not None:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"text": text, "prompt_tokens": pt, "completion_tokens": ct}))
        self.calls += 1
        self.tokens += reply.prompt_tokens + reply.completion_tokens
        self.latency += reply.latency_s
        p = self.by_purpose.setdefault(purpose or "?", {"calls": 0, "tokens": 0, "latency_s": 0.0})
        p["calls"] += 1
        p["tokens"] += reply.prompt_tokens + reply.completion_tokens
        p["latency_s"] += reply.latency_s
        self._log(reply, purpose, key)
        return reply

    def record_cached(self, purpose: str = "") -> None:
        """Count a call answered from an external cache (e.g. the extraction cache): 0 tokens, 0 latency."""
        self.calls += 1
        p = self.by_purpose.setdefault(purpose or "?", {"calls": 0, "tokens": 0, "latency_s": 0.0})
        p["calls"] += 1
        p["cache_hits"] = p.get("cache_hits", 0) + 1
        self._log(LLMReply("", 0, 0, 0.0, cached=True), purpose, "extraction-cache")

    def _ollama(self, system: str, user: str, schema: dict | None) -> tuple[str, int, int]:
        import ollama
        kwargs: dict = {}
        if self.think is not None and self.model.startswith("gpt-oss"):
            kwargs["think"] = self.think
        elif self.model.startswith("qwen3"):
            kwargs["think"] = self.think is True          # off unless explicitly asked for (bank checker)
        r = ollama.chat(model=self.model,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        format=schema, options={"temperature": self.temperature, "seed": self.seed,
                                                "num_predict": self.max_tokens, "num_ctx": 8192},
                        **kwargs)
        return r.message.content or "", int(r.prompt_eval_count or 0), int(r.eval_count or 0)

    def _openai(self, system: str, user: str, schema: dict | None) -> tuple[str, int, int]:
        if os.environ.get("OBT_ALLOW_PAID") != "1":
            raise PaidCallRefused("openai backend needs OBT_ALLOW_PAID=1")
        from openai import OpenAI
        self.meter.check(self.model, (len(system) + len(user)) // 3, self.max_tokens)
        fmt = ({"type": "json_schema", "json_schema": {"name": "out", "schema": schema, "strict": False}}
               if schema else None)
        client = OpenAI()
        kwargs = {"response_format": fmt} if fmt else {}
        r = client.chat.completions.create(
            model=self.model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_completion_tokens=self.max_tokens, seed=self.seed, **kwargs)
        pt, ct = r.usage.prompt_tokens, r.usage.completion_tokens
        self.meter.add(self.model, pt, ct)
        return r.choices[0].message.content or "", pt, ct

    def _log(self, reply: LLMReply, purpose: str, key: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "backend": self.backend, "model": self.model, "purpose": purpose,
               "run": self.run_tag, "prompt_tokens": reply.prompt_tokens,
               "completion_tokens": reply.completion_tokens, "latency_s": round(reply.latency_s, 4),
               "cached": reply.cached, "key": key[:16]}
        with self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")


def parse_json(text: str):
    """Parse a JSON object from model output, tolerating a code fence around it."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in output")
    return json.loads(t[start:end + 1])
