"""E5: paid runs are prepared, never executed. Projection from measured local usage; abort over $12."""
import pytest

from eval import e5_paid
from obt import llm


PLAN = e5_paid.plan()


def test_plan_matches_fixes():
    luna = [p for p in PLAN if p["model"] == e5_paid.LUNA]
    terra = [p for p in PLAN if p["model"] == e5_paid.TERRA]
    assert {(p["scenario"], p["defense"]) for p in luna if p["kind"] == "run"} == {
        (n, d) for n in range(1, 13) for d in ("none", "obt")}
    assert {(p["scenario"], p["defense"]) for p in terra if p["kind"] == "run"} == {
        (n, "obt") for n in (1, 3, 5, 8, 9, 11)}
    assert all(p["seed"] == 1 for p in PLAN if p["kind"] == "run")
    assert sum(p["kind"] == "extractor_eval" for p in PLAN) == 2


USAGE = {("buyer", "none"): (1500, 60), ("buyer", "obt"): (1600, 60), ("extract", "obt"): (430, 45),
         ("selfcheck", "none"): (0, 0)}


def test_projection_uses_measured_usage_and_a_margin(monkeypatch):
    monkeypatch.setattr(llm, "PAID_PRICES", {e5_paid.LUNA: (1.0, 4.0), e5_paid.TERRA: (2.0, 8.0)})
    proj = e5_paid.project(PLAN, per_round=USAGE, rounds=50, extractor_items=229)
    luna_obt = next(p for p in proj["items"] if p["model"] == e5_paid.LUNA and p["defense"] == "obt")
    tin = (1600 + 430) * 50 * e5_paid.MARGIN
    tout = (60 + 45) * 50 * e5_paid.MARGIN
    assert luna_obt["usd"] == pytest.approx((tin * 1.0 + tout * 4.0) / 1e6)
    assert proj["total_usd"] == pytest.approx(sum(p["usd"] for p in proj["items"]))


def test_aborts_without_prices(monkeypatch):
    monkeypatch.setattr(llm, "PAID_PRICES", {})
    with pytest.raises(e5_paid.Abort, match="price"):
        e5_paid.check(e5_paid.project(PLAN, per_round=USAGE, rounds=50, extractor_items=229))


def test_aborts_over_twelve_dollars(monkeypatch):
    monkeypatch.setattr(llm, "PAID_PRICES", {e5_paid.LUNA: (100.0, 400.0), e5_paid.TERRA: (100.0, 400.0)})
    proj = e5_paid.project(PLAN, per_round=USAGE, rounds=50, extractor_items=229)
    assert proj["total_usd"] > 12
    with pytest.raises(e5_paid.Abort, match="12"):
        e5_paid.check(proj)


def test_under_budget_prints_commands_and_never_runs_them(monkeypatch, capsys):
    monkeypatch.setattr(llm, "PAID_PRICES", {e5_paid.LUNA: (0.1, 0.4), e5_paid.TERRA: (0.2, 0.8)})
    monkeypatch.delenv("OBT_ALLOW_PAID", raising=False)
    monkeypatch.setattr(e5_paid, "measured_usage", lambda: (USAGE, "test"))
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("E5 must not execute anything"))
    e5_paid.main([])
    out = capsys.readouterr().out
    assert "OBT_ALLOW_PAID=1" in out and "--backend openai" in out and "projected" in out
    assert "not run" in out.lower()
