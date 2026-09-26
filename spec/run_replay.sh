#!/usr/bin/env bash
# Spec-code trace replay campaigns (FIXES F6 conformance check 2). Writes spec/results/replay/*.json.
#   uniform/none   1,000 traces sampled from the full-bounds simulation distribution
#   guided/none    GuidedSpec traces (offer pairs, same-supplier/item citations) until >= 1,000 gate decisions
#   controls       mutated gates, properties off in TLC: the replay must report mismatches
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
mkdir -p spec/results/replay
status=0
run() { "$PY" -m spec.replay campaign "$@" > /dev/null || status=1; }
run uniform none 1000 0    20260925 spec/results/replay/uniform_none.json
run guided  none 1000 1000 20261000 spec/results/replay/guided_none.json
run guided  I1   3000 0    101      spec/results/replay/control_guided_I1.json
run uniform ITEM 5000 0    201      spec/results/replay/control_uniform_ITEM.json
"$PY" - <<'PYEOF'
import json, pathlib
rows = []
for f in sorted(pathlib.Path("spec/results/replay").glob("*.json")):
    d = json.loads(f.read_text())
    rows.append(f"{f.stem:22} traces {d['traces']:>6}  to final round {d['traces_to_final_round']:>6}  "
                f"avg length {d['avg_trace_length']:>5}  with decisions {d['traces_with_decisions']:>5}  "
                f"decisions {d['decisions']:>6}  spec {d['spec_verdicts']}  mismatches {d['mismatch_count']}")
    rows.append(" " * 24 + "python reasons: " + ", ".join(f"{k} {v}" for k, v in d["reasons"].items()))
pathlib.Path("spec/results/replay/summary.txt").write_text("\n".join(rows) + "\n")
print("\n".join(rows))
PYEOF
exit $status
