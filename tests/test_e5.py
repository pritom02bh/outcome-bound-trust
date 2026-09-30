"""E5 (D37): Plan B, the paid-call path (reasoning effort, prices, ledger), and the D24 extractor split.
No test makes a paid or network call: the OpenAI client is replaced by a fake."""
import json
import sys
import types

import pytest

from eval import e5_paid
from eval import run as er
from obt import llm

PLAN = e5_paid.plan()


def test_plan_is_plan_b():
    runs = {(p["model"], p["defense"], p["scenario"]) for p in PLAN if p["kind"] == "run"}
    assert runs == {(m, d, n) for m in (e5_paid.LUNA, e5_paid.TERRA) for d in ("obt+planner", "none")
                    for n in range(1, 13)}                                # v2: Terra has its own none (D37a)
    assert all(p["seed"] == 1 for p in PLAN if p["kind"] == "run")
    assert [p["items"] for p in PLAN if p["kind"] == "extractor_eval"] == [229, 229]


def test_eval_config_pays_only_for_the_buyer():
    ec = e5_paid.eval_config(e5_paid.TERRA)
    assert (ec.backend, ec.model, ec.extractor_model, ec.extractor_backend) == (
        "openai", e5_paid.TERRA, "gpt-oss:20b", "ollama")                      # D24: frozen local extractor
    assert ec.extractor_eval_model == e5_paid.TERRA                            # paid extraction: eval only
    assert ec.cache and ec.cap_usd == 16.0 and ec.sim == {"b0_frac": 0.05, "window": 0, "grace": 0}
    assert er.extractor_backend(ec) == "ollama"
    assert er.config_hash(ec) != er.config_hash(e5_paid.eval_config(e5_paid.TERRA).__class__(
        **{**ec.__dict__, "extractor_backend": None}))                          # the backend is part of a run


def test_prices_are_the_verified_ones():
    assert llm.PAID_PRICES == {"gpt-5.6-luna": (0.20, 1.20), "gpt-5.6-terra": (2.00, 12.00)}


BUYER = {(d, n): (100_000.0, 5_000.0) for d in ("obt+planner", "none") for n in range(1, 13)}


def test_projection_prices_the_buyer_and_the_extractor_eval():
    proj = e5_paid.project(PLAN, BUYER, (500.0, 50.0), scale=(2.0, 3.0), margin=1.25)
    terra = next(p for p in proj["items"] if p["model"] == e5_paid.TERRA and p["kind"] == "run")
    assert terra["usd"] == pytest.approx((100_000 * 2 * 1.25 * 2.0 + 5_000 * 3 * 1.25 * 12.0) / 1e6)
    ext = next(p for p in proj["items"] if p["model"] == e5_paid.LUNA and p["kind"] == "extractor_eval")
    assert ext["usd"] == pytest.approx((500 * 229 * 1.25 * 0.2 + 50 * 229 * 1.25 * 1.2) / 1e6)
    with pytest.raises(e5_paid.Abort, match="14"):
        e5_paid.check({**proj, "total_usd": 14.01})


def test_dry_run_makes_no_call(monkeypatch, capsys):
    monkeypatch.delenv("OBT_ALLOW_PAID", raising=False)
    monkeypatch.setattr(e5_paid, "measured_buyer", lambda *a: BUYER)
    monkeypatch.setattr(e5_paid, "measured_extract_item", lambda *a: (500.0, 50.0))
    monkeypatch.setitem(sys.modules, "openai", None)                  # importing openai would fail
    e5_paid.main([])
    out = capsys.readouterr().out
    assert "projected total" in out and "Not run" in out


class _FakeOpenAI:
    seen: list = []

    def __init__(self, *a, **k):
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        _FakeOpenAI.seen.append(kw)
        usage = types.SimpleNamespace(
            prompt_tokens=1000, completion_tokens=300,
            completion_tokens_details=types.SimpleNamespace(reasoning_tokens=200),
            prompt_tokens_details=types.SimpleNamespace(cached_tokens=0))
        msg = types.SimpleNamespace(content='{"ok": true}')
        return types.SimpleNamespace(usage=usage, choices=[types.SimpleNamespace(message=msg)])


def test_paid_call_sends_low_reasoning_effort_and_ledgers_every_call(monkeypatch, tmp_path):
    monkeypatch.setenv("OBT_ALLOW_PAID", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-SECRET")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))
    _FakeOpenAI.seen.clear()
    meter = llm.CostMeter(tmp_path / "ledger.json", cap=16.0)
    m = llm.LLM("openai", e5_paid.TERRA, meter=meter, log_path=tmp_path / "calls.jsonl", run_tag="t",
                cache_dir=tmp_path / "cache")
    m.chat("sys", "user", purpose="buyer")
    m.chat("sys", "user", purpose="buyer")                            # cached: not sent, not paid again
    assert len(_FakeOpenAI.seen) == 1 and _FakeOpenAI.seen[0]["reasoning_effort"] == "low"
    assert meter.spent() == pytest.approx((1000 * 2.0 + 300 * 12.0) / 1e6)
    lines = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    assert len(lines) == 1 and lines[0]["reasoning_tokens"] == 200 and lines[0]["run"] == "t"
    log = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert log[0]["reasoning_tokens"] == 200 and log[1]["cached"]
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert "SECRET" not in f.read_text()                       # the key is never written anywhere


def test_hard_stop_at_sixteen(monkeypatch, tmp_path):
    meter = llm.CostMeter(tmp_path / "ledger.json", cap=16.0)
    meter.add(e5_paid.TERRA, 7_000_000, 0)                             # $14
    meter.check(e5_paid.TERRA, 100_000, 4096)                           # $0.25 more fits
    meter.add(e5_paid.TERRA, 900_000, 0)                                # $15.80
    with pytest.raises(llm.BudgetExceeded):
        meter.check(e5_paid.TERRA, 100_000, 4096)


def test_load_key_never_prints(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "")                          # so teardown restores the real env
    monkeypatch.delenv("OPENAI_API_KEY")
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-test-SECRET\n")
    e5_paid._load_key(env)
    import os
    assert os.environ["OPENAI_API_KEY"] == "sk-test-SECRET"
    assert "SECRET" not in capsys.readouterr().out


def _paid_llm(monkeypatch, tmp_path, scope):
    monkeypatch.setenv("OBT_ALLOW_PAID", "1")
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=_FakeOpenAI))
    m = llm.LLM("openai", e5_paid.LUNA, meter=llm.CostMeter(tmp_path / "ledger.json", cap=16.0),
                log_path=tmp_path / "calls.jsonl", cache_dir=tmp_path / "cache", run_tag=scope)
    m.cache_scope = scope
    return m


def test_run_scoped_cache_never_reuses_across_runs_but_resumes_a_run(monkeypatch, tmp_path):
    # D37a: v1 answered byte-identical prompts in another run from the cache. Now the key holds the run scope and
    # the call index: another run (or scenario) pays for its own sample; a resumed run replays its calls for free.
    _FakeOpenAI.seen.clear()
    a = _paid_llm(monkeypatch, tmp_path, "3_farm_then_lie|obt+planner|s1|m|h")
    a.chat("sys", "same prompt")
    a.chat("sys", "same prompt")                     # same run, next call index: a fresh sample
    b = _paid_llm(monkeypatch, tmp_path, "1_honest|obt+planner|s1|m|h")
    b.chat("sys", "same prompt")                     # another run: never the other run's answer
    assert len(_FakeOpenAI.seen) == 3
    resumed = _paid_llm(monkeypatch, tmp_path, "3_farm_then_lie|obt+planner|s1|m|h")
    assert resumed.chat("sys", "same prompt").cached and resumed.chat("sys", "same prompt").cached
    assert len(_FakeOpenAI.seen) == 3                # resuming the interrupted run paid nothing


def test_unscoped_llms_keep_their_old_cache_keys(tmp_path):
    m = llm.LLM("fake", "m", fake=lambda s, u: "x")
    old = __import__("hashlib").sha256(json.dumps(["fake", "m", 0.0, 0, "low", "s", "u", None],
                                                  sort_keys=True).encode()).hexdigest()
    assert m._key("s", "u", None, 0) == old


def test_v2_projection_counts_every_call_and_what_is_spent(tmp_path, monkeypatch):
    v1 = tmp_path / "e5" / "_v1_shared_cache"
    for d, model in (("luna", e5_paid.LUNA), ("terra", e5_paid.TERRA)):
        (v1 / d).mkdir(parents=True)
        rows = []
        for dfn in ("obt+planner", "none") if d == "luna" else ("obt+planner",):
            for i in range(50):
                rows.append({"backend": "openai", "purpose": "buyer", "run": f"1_honest|{dfn}|s1|{model}",
                             "prompt_tokens": 0 if i < 10 else 1000, "completion_tokens": 0 if i < 10 else 100,
                             "cached": i < 10})
        (v1 / d / "llm_calls.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / "cost_ledger.json").write_text(json.dumps({"spent_usd": 3.0}))
    p = e5_paid.project_v2(tmp_path, margin=1.0)
    assert p["per_call"][f"{e5_paid.TERRA} obt+planner"] == (1000.0, 100.0, 50)   # cached calls: counted, not sampled
    luna = p["parts"][f"{e5_paid.LUNA} obt+planner"]
    assert luna["runs"] == 12 and luna["usd"] == pytest.approx(12 * (50_000 * 0.2 + 5_000 * 1.2) / 1e6)
    assert p["parts"][f"{e5_paid.TERRA} none"]["runs"] == 12
    assert p["total_usd"] == pytest.approx(3.0 + p["rest_usd"])


# ---- D41: seeds 2-3 (overnight batch)

class _Quota(Exception):
    pass


def test_seeds_config_has_no_harness_cap_and_joins_the_seed_1_eval():
    c = e5_paid.eval_config(e5_paid.TERRA, seeds=(2, 3), cap=e5_paid.NO_CAP)
    assert c.seeds == (2, 3) and c.cap_usd == float("inf")
    assert er.config_hash(c) == er.config_hash(e5_paid.eval_config(e5_paid.TERRA))   # resume skips seed 1


def test_classify_stops_only_on_violations_and_billing_quota_auth():
    import httpx
    import openai
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

    def status(code, body):
        return openai.APIStatusError("x", response=httpx.Response(code, request=req), body=body)
    assert e5_paid.classify(er.InvariantViolation("x")) == "violation"
    assert e5_paid.classify(er.LossBoundViolation("x")) == "violation"
    q = openai.RateLimitError("You exceeded your current quota", response=httpx.Response(429, request=req),
                              body={"code": "insufficient_quota"})
    assert e5_paid.classify(q) == "quota"
    assert e5_paid.classify(status(401, {"code": "invalid_api_key"})) == "quota"
    assert e5_paid.classify(openai.RateLimitError("slow down", response=httpx.Response(429, request=req),
                                                  body=None)) == "retry"
    assert e5_paid.classify(status(503, None)) == "retry"
    assert e5_paid.classify(openai.APIConnectionError(request=req)) == "retry"
    assert e5_paid.classify(RuntimeError("a2a hiccup")) == "retry"


def test_seeds_stage_retries_transient_errors_and_stops_on_quota(monkeypatch, tmp_path):
    import httpx
    import openai
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    monkeypatch.setattr(e5_paid, "_load_key", lambda *a: None)
    monkeypatch.setattr(e5_paid, "OUT", tmp_path)
    monkeypatch.setattr(e5_paid, "project_seeds", lambda **k: {"projected_total_usd": 0})
    monkeypatch.setattr(e5_paid, "seed_spend", lambda *a: {})
    calls = []

    def flaky(model, seeds, cap):
        calls.append(model)
        assert seeds == (2, 3) and cap == float("inf")
        if len(calls) == 1:
            raise openai.APIConnectionError(request=req)
    monkeypatch.setattr(e5_paid, "run_models", flaky)
    waits = []
    e5_paid.seeds_stage(sleep=waits.append)
    assert calls == [e5_paid.LUNA, e5_paid.LUNA, e5_paid.TERRA] and waits == [60]     # Luna first, then Terra

    def quota(model, seeds, cap):
        raise openai.RateLimitError("quota sk-live-abcdef123456 exceeded", response=httpx.Response(429, request=req),
                                    body={"code": "insufficient_quota"})
    monkeypatch.setattr(e5_paid, "run_models", quota)
    with pytest.raises(e5_paid.ChainStop) as e:
        e5_paid.seeds_stage(sleep=waits.append)
    assert e.value.kind == "quota" and "abcdef123456" not in str(e.value)             # key-like text scrubbed

    def violation(model, seeds, cap):
        raise er.InvariantViolation("I1")
    monkeypatch.setattr(e5_paid, "run_models", violation)
    with pytest.raises(e5_paid.ChainStop) as e:
        e5_paid.seeds_stage(sleep=waits.append)
    assert e.value.kind == "violation"                                                # never retried
