#!/bin/bash
# Overnight batch 2 (DECISIONS D41): E5 seeds 2-3 (paid), loss per 100 S_main units (D40), full refresh, v1.4-results.
#   nohup caffeinate -i bash eval/overnight2.sh >> runs/overnight2.log 2>&1 &
# Strictly one step after another. The chain stops on an invariant or loss-bound violation, a test failure, or an
# API billing/quota/auth error; also on any failed build or verification step (it can't safely go on). Transient
# API errors are retried inside Part A. OBT_ALLOW_PAID=1 is set for the Part A command only. Never pushes.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
unset OBT_ALLOW_PAID
PY=.venv/bin/python
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "STOP: $*"; exit 1; }
step() { log "== $1"; shift; "$@" || fail "step failed (exit $?): $*"; }

log "overnight2 armed at $(git rev-parse --short HEAD)"

# PART A: E5 seeds 2-3, paid. Exit 2 violation, 3 billing/quota/auth, 4 persistent error.
log "== PART A: E5 seeds 2-3 (Luna, then Terra)"
OBT_ALLOW_PAID=1 $PY -m eval.e5_paid seeds
rc=$?
case $rc in
  0) log "PART A done" ;;
  2) fail "PART A: invariant or loss-bound violation" ;;
  3) fail "PART A: API billing/quota/auth error" ;;
  *) fail "PART A: exit $rc (see above)" ;;
esac

# PART B + C: the new metric is computed by the results build from the run records (no model calls).
step "PART B/C: results (E5 seeds 1-3, loss per 100 S_main units)" $PY -m eval.results --runs runs --out results
step "PART C: paper tables, figures, NUMBERS.md" $PY -m eval.paper
step "PART C: INDEX.md and D41 outcome" $PY -m eval.release_notes
step "PART C: workbook + paper pack (verified against NUMBERS.md and paper/tables)" $PY -m eval.pack
step "PART C: every unaffected number identical to v1.3-paper-pack; new numbers traced" \
     $PY -m eval.verify_release v1.3-paper-pack
step "tests (default)" $PY -m pytest -q
step "tests (slow: TLC)" $PY -m pytest -q -m slow
step "tests (local LLM)" $PY -m pytest -q -m llm

# The key must not be in anything about to be committed.
step "key scan" $PY - <<'EOF'
import sys
from pathlib import Path
key = next((l.split("=", 1)[1].strip().strip("'\"") for l in Path(".env").read_text().splitlines()
            if l.startswith("OPENAI_API_KEY=")), None)
hits = [str(p) for root in ("results", "paper", "paper_pack", "docs", "eval", "obt", "tests", "spec")
        for p in Path(root).rglob("*") if key and p.is_file() and key.encode() in p.read_bytes()]
hits += [z for z in ("paper_pack_v1.4.zip",) if key and key.encode() in Path(z).read_bytes()]
print("files containing the key:", len(hits))
sys.exit(1 if hits else 0)
EOF

step "commit" git add results paper paper_pack paper_pack_v1.4.zip docs
git commit -q -m "v1.4-results: E5 seeds 2-3 (paid, D41), loss per 100 S_main units (D40), full refresh; every unaffected number identical to v1.3-paper-pack

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || fail "commit"
step "tag" git tag -a v1.4-results -m "v1.4-results: E5 over seeds 1-3, loss per 100 S_main units, refreshed tables, NUMBERS.md, workbook and paper pack"
log "DONE at $(git rev-parse --short HEAD) (not pushed)"
