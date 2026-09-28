"""E2 setup (user decisions D27): named reputation variants run as separate defenses."""
import json

import eval.run as er
from eval.run import EvalConfig, run_eval
from obt.llm import CostMeter

E2_SIM = {"b0_frac": 0.05, "window": 0, "grace": 0}


def test_variants_are_the_user_decisions():
    assert er.VARIANTS == {"rep-strict": ("reputation", {"rep_cap": 200.0, "rep_theta": 0.9}),
                           "rep-default": ("reputation", {"rep_cap": 200.0, "rep_theta": 0.8})}


def test_variant_resolves_to_reputation_with_its_overrides():
    ec = EvalConfig(sim=E2_SIM)
    s = er.sim_config(ec, "rep-strict")
    assert (s.defense, s.rep_cap, s.rep_theta, s.b0_frac, s.window, s.grace) == ("reputation", 200.0, 0.9, 0.05, 0, 0)
    assert er.sim_config(ec, "rep-default").rep_theta == 0.8
    assert er.sim_config(ec, "obt").defense == "obt"


def test_each_variant_has_its_own_run_identity_but_one_eval_config():
    ec = EvalConfig(sim=E2_SIM)
    assert er.config_hash(ec, "rep-strict") != er.config_hash(ec, "rep-default")
    assert er.config_hash(ec, "obt") == er.config_hash(ec) == er.config_hash(ec, "none")


def test_e2_style_eval_runs_variants_resumes_and_summarizes(tmp_path, rule_llm, monkeypatch):
    ec = EvalConfig(backend="fake", model="fake", buyer="scripted", scenarios=(1, 2), seeds=(1,), rounds=6,
                    defenses=("none", "rep-strict", "rep-default", "obt"), sim=E2_SIM, extractor_eval=False)
    rep = run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    rows = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert {r["defense"] for r in rows} == {"none", "rep-strict", "rep-default", "obt"}
    strict = next(r for r in rows if r["defense"] == "rep-strict")
    assert strict["meta"]["sim"] == {**E2_SIM, "rep_cap": 200.0, "rep_theta": 0.9}
    assert len({r["meta"]["eval_config_hash"] for r in rows}) == 1
    assert rep["summary"]["defenses"] == ["obt", "none", "rep-strict", "rep-default"]
    monkeypatch.setattr(er, "run_one", lambda *a, **k: (_ for _ in ()).throw(AssertionError("rerun")))
    assert run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)["n_runs"] == 8


def test_results_builder_keeps_an_e2_eval_together(tmp_path, rule_llm):
    from eval import results
    ec = EvalConfig(backend="fake", model="fake", buyer="scripted", scenarios=(1, 2), seeds=(1,), rounds=6,
                    defenses=("rep-strict", "rep-default", "obt"), sim=E2_SIM, extractor_eval=False)
    run_eval(ec, tmp_path / "runs" / "e2", meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    built = results.build(tmp_path / "runs", tmp_path / "out")
    assert list(built) == ["e2"]


def test_eval_stops_right_after_the_first_violating_run(tmp_path, rule_llm, monkeypatch):
    import pytest
    real = er.run_one
    done = []

    def bad_second(e, n, d, s, m, f=None):
        r = real(e, n, d, s, m, f)
        done.append(n)
        if len(done) == 2:
            r["metrics"]["invariant_violations"]["count"] = 1
        return r
    monkeypatch.setattr(er, "run_one", bad_second)
    ec = EvalConfig(backend="fake", model="fake", buyer="scripted", scenarios=(1, 2, 3, 4), seeds=(1,), rounds=6,
                    defenses=("obt",), extractor_eval=False)
    with pytest.raises(er.InvariantViolation):
        run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    assert len(done) == 2                                          # no run after the violating one


def test_extractor_model_can_differ_from_the_buyer_model(tmp_path, rule_llm, monkeypatch):
    # E3 (D28): qwen3 buys, gpt-oss extracts. The extractor's model is part of the run config and provenance.
    seen = []
    real = er.make_llm

    def spy(ec, tag, meter, fake=None, model=None):
        seen.append((tag.split("|")[-1] if model is None else model, model))
        return real(ec, tag, meter, fake, model)
    monkeypatch.setattr(er, "make_llm", spy)
    ec = EvalConfig(backend="fake", model="buyer-m", extractor_model="extract-m", buyer="scripted", scenarios=(1,),
                    seeds=(1,), rounds=4, defenses=("obt",), extractor_eval=False)
    run_eval(ec, tmp_path, meter=CostMeter(tmp_path / "c.json"), fake=rule_llm)
    r = json.loads((tmp_path / "results.jsonl").read_text().splitlines()[0])
    assert r["meta"]["extractor_model"] == "extract-m" and r["model"] == "buyer-m"
    assert ("extract-m", "extract-m") in seen
    assert er.config_hash(ec) != er.config_hash(EvalConfig(backend="fake", model="buyer-m", buyer="scripted"))
    assert EvalConfig().extractor_model is None                   # default: the run's own model (E2 unchanged)
