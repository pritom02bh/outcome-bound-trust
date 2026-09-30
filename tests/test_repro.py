"""F12: run provenance, resumable eval, and results rebuilt from runs/ only."""
import json

import pytest

import eval.run as er
from eval.run import EvalConfig, run_eval
from obt import config
from obt.llm import CostMeter


def ec(**kw):
    base = dict(backend="fake", model="fake", buyer="scripted", scenarios=(1, 2), defenses=("obt",), rounds=8,
                extractor_limit=5)
    return EvalConfig(**{**base, **kw})


def rows(d):
    return [json.loads(line) for line in (d / "results.jsonl").read_text().splitlines() if line.strip()]


def test_every_run_records_its_provenance(tmp_path, rule_llm):
    run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    for r in rows(tmp_path):
        m = r["meta"]
        assert len(m["git_commit"]) == 40 and isinstance(m["git_dirty"], bool)
        assert len(m["config_hash"]) == 64 and m["seed"] == r["seed"] and m["model"] == "fake"
        assert m["model_digest"] == "fake"
        assert m["message_bank_sha256"] == config.MESSAGE_BANK_SHA256
        assert m["extractor_prompt_sha256"] == config.EXTRACTOR_PROMPT_SHA256
        assert m["extractor_dataset_sha256"] == config.EXTRACTOR_DATASET_SHA256
        assert m["transport"] == "a2a" and m["python"]


def test_config_hash_tracks_the_config_not_the_paths(tmp_path):
    a = er.config_hash(ec())
    assert a == er.config_hash(ec(log_dir=tmp_path, scenarios=(7,), seeds=(4,), defenses=("none",)))
    assert a != er.config_hash(ec(rounds=9)) and a != er.config_hash(ec(transport="inproc"))
    assert a != er.config_hash(ec(model="other"))


def test_resume_skips_completed_runs(tmp_path, rule_llm, monkeypatch):
    run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    done = []
    real = er.run_one
    monkeypatch.setattr(er, "run_one", lambda e, n, d, s, m, f=None: done.append((n, d, s)) or real(e, n, d, s, m, f))
    rep = run_eval(ec(scenarios=(1, 2, 7)), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    assert done == [(7, "obt", 1)]
    assert rep["n_runs"] == 3 and len(rows(tmp_path)) == 3
    assert set(rep["summary"]["loss_from_lies"]) == {"1|obt", "2|obt", "7|obt"}


def test_resume_redoes_a_torn_last_line(tmp_path, rule_llm):
    run_eval(ec(scenarios=(1,)), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    with (tmp_path / "results.jsonl").open("a") as f:
        f.write('{"scenario": 2, "defense": "ob')                 # a crash mid-write
    rep = run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    assert rep["n_runs"] == 2 and {r["scenario"] for r in rows(tmp_path)} == {1, 2}


def test_resume_never_mixes_configs(tmp_path, rule_llm):
    run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    rep = run_eval(ec(rounds=9), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    assert rep["n_runs"] == 2                                     # only this config's runs are summarized
    assert len({r["meta"]["config_hash"] for r in rows(tmp_path)}) == 2 and len(rows(tmp_path)) == 4


def test_extractor_eval_is_resumed_when_its_inputs_match(tmp_path, rule_llm, monkeypatch):
    run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    monkeypatch.setattr(er, "extractor_eval", lambda *a, **k: pytest.fail("extractor eval rerun"))
    rep = run_eval(ec(), tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    assert "llm:fake" in rep["extractor"]


def test_make_results_rebuilds_from_runs_only(tmp_path, rule_llm, monkeypatch):
    from eval import results
    runs = tmp_path / "runs"
    rep = run_eval(ec(scenarios=(1, 2, 7), defenses=("obt", "none")), runs / "eval_a",
                   meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    # Nothing may be simulated or called: the builder reads the run records.
    import obt.sim
    monkeypatch.setattr(obt.sim.Sim, "run", lambda self: pytest.fail("results must not simulate"))
    out = tmp_path / "results"
    built = results.build(runs, out)
    assert (out / "eval_a" / "summary.md").exists() and (out / "eval_a" / "loss_from_lies.csv").exists()
    assert (out / "eval_a" / "extractor.md").exists() and (out / "evals.md").exists()
    assert "95% CI" in (out / "eval_a" / "ci.md").read_text()
    assert built["eval_a"]["summary"]["loss_from_lies"] == rep["summary"]["loss_from_lies"]
    first = {p.name: p.read_bytes() for p in (out / "eval_a").iterdir()}
    results.build(runs, out)
    assert first == {p.name: p.read_bytes() for p in (out / "eval_a").iterdir()}     # deterministic
