"""F6 conformance check 2, fast part: the trace parser and spec->code mapping on a committed TLC trace.

The fixture is one GuidedSpec simulation trace at tiny bounds (1 supplier, 2 items, 2 rounds, seed 3) with an
allowed order, a blocked order and a paid invoice. The full campaigns are spec/run_replay.sh.
"""
from pathlib import Path

from spec.replay import decisions, parse_cfg, parse_trace, replay_state

FIX = Path(__file__).parent / "fixtures"


def test_trace_parses_to_full_states():
    states = parse_trace((FIX / "tlc_trace_tiny.tla").read_text())
    assert len(states) > 10
    assert set(states[0]) == {"now", "phase", "cl", "od", "py", "nt", "rq", "rc", "made"}
    assert states[0]["phase"] == "env" and states[0]["now"] == 1
    assert states[0]["py"]["p1"]["ref"] == "NoRef"
    assert all(isinstance(k, tuple) for k in states[0]["rq"])


def test_every_gate_decision_in_fixture_matches_python():
    consts = parse_cfg((FIX / "tlc_trace_tiny.cfg").read_text())
    states = parse_trace((FIX / "tlc_trace_tiny.tla").read_text())
    seen = set()
    for s, kind, ident, spec_ok in decisions(states):
        ok, why, mwhy = replay_state(s, kind, ident, consts)
        assert ok == spec_ok and why == mwhy, (kind, ident, spec_ok, why, mwhy)
        seen.add((kind, spec_ok))
    assert seen == {("ORDER", True), ("ORDER", False), ("PAYMENT", True)}


def test_replay_detects_a_flipped_spec_verdict():
    # Negative control: claim the spec executed an order the Python gate blocks.
    consts = parse_cfg((FIX / "tlc_trace_tiny.cfg").read_text())
    states = parse_trace((FIX / "tlc_trace_tiny.tla").read_text())
    s, kind, ident, spec_ok = next(d for d in decisions(states) if d[1] == "ORDER" and not d[3])
    ok, _, _ = replay_state(s, kind, ident, consts)
    assert ok != (not spec_ok)
