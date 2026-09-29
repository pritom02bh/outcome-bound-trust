#!/bin/bash
# Overnight chain (DECISIONS D35). Local models only: no paid call, E5 is never run.
#   nohup caffeinate -i bash eval/overnight.sh <E2c pid> >> runs/overnight.log 2>&1 &
# Waits for E2c's process to exit, then runs each step in order. Any failed step stops the chain: eval.run exits
# non-zero on any invariant or loss-bound violation (STOP rule), and every other step on any error.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
PY=.venv/bin/python
SIM=b0_frac=0.05,window=0,grace=0
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "STOP: $*"; exit 1; }
step() { log "== $1"; shift; "$@" || fail "step failed: $*"; }

log "armed; waiting for E2c (pid ${1:-none}) to exit"
if [ -n "${1:-}" ]; then while kill -0 "$1" 2>/dev/null; do sleep 60; done; fi
log "E2c exited"
tail -n 1 runs/e2c/e2c.log | grep -q "^EXIT 0" || fail "E2c did not finish cleanly: $(tail -n 1 runs/e2c/e2c.log)"
grep -E "^(invariant|loss-bound) violations: [1-9]" runs/e2c/e2c.log && fail "E2c reported a violation"
grep -q "^STOP" runs/e2c/e2c.log && fail "E2c stopped on a violation"

# 0. E2c fix-up (D32a): obt+planner ran with the NullExtractor, so its 60 runs are invalid. Move them (never
#    delete) and re-run obt+planner on the fixed harness; then write E2c's report.
step "0a quarantine the invalid obt+planner runs" $PY - <<'EOF'
import json, os
from pathlib import Path
f = Path("runs/e2c/results.jsonl")
rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
bad = [r for r in rows if r["defense"] == "obt+planner" and r["usage"]["extractor"] == "null"]
keep = [r for r in rows if r not in bad]
with open("runs/e2c/_invalid_obt_planner_nullextractor.jsonl", "a") as q:
    q.write("".join(json.dumps(r, default=str) + "\n" for r in bad))
tmp = f.with_suffix(".tmp")
tmp.write_text("".join(json.dumps(r, default=str) + "\n" for r in keep))
os.replace(tmp, f)
print(f"moved {len(bad)} invalid obt+planner runs; kept {len(keep)}")
EOF
step "0b re-run obt+planner (12 scenarios x 5 seeds, gpt-oss buyer)" $PY -m eval.run --buyer llm --model gpt-oss:20b \
    --scenarios 1-12 --defenses obt+planner --seeds 1-5 --sim $SIM --no-extractor-eval --out runs/e2c
step "0c E2c report (make results)" make results

# 1. Paper assets from results/ only.
step "1 paper assets" $PY -m eval.paper

# 2. Horizon check: 100 rounds, scripted buyer.
step "2 horizon check (T=100)" $PY -m eval.horizon

# 3. E3b: qwen3:8b buyer, gpt-oss extractor, planner defenses, seed 1.
step "3 E3b (qwen3 buyer, obt+planner and rep+planner)" $PY -m eval.run --buyer llm --model qwen3:8b \
    --extractor-model gpt-oss:20b --scenarios 1-12 --defenses obt+planner,rep+planner --seeds 1 --sim $SIM \
    --no-extractor-eval --out runs/e3b

# Refresh every table and figure with the horizon and E3b results.
step "final refresh (make results, paper assets)" bash -c "make results && $PY -m eval.paper"
log "DONE (E5 not run)"
