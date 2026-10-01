#!/bin/bash
# E8 chain (DECISIONS D43): 42 LLM-adversary runs (local models only), then refresh, verify, test, tag v1.5-results.
#   nohup caffeinate -i bash eval/e8.sh >> runs/e8.log 2>&1 &
# Stops on an invariant or loss-bound violation (eval.run raises) or any failed step. No paid call; never pushes.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
unset OBT_ALLOW_PAID
PY=.venv/bin/python
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "STOP: $*"; exit 1; }
step() { log "== $1"; shift; "$@" || fail "step failed (exit $?): $*"; }

log "e8 armed at $(git rev-parse --short HEAD)"
step "E8: 42 attack runs (black-box, white-box) x 7 defenses x seeds 1-3" $PY -m eval.e8 run
step "refresh: results" $PY -m eval.results --runs runs --out results
step "refresh: paper tables, figures, NUMBERS.md (E8 under RQ3)" $PY -m eval.paper
step "refresh: INDEX.md E8 row and D43 outcome" $PY -m eval.e8 notes
step "refresh: workbook + paper pack (verified against NUMBERS.md and paper/tables)" $PY -m eval.pack
step "verify: every prior number identical to v1.4.1-results" $PY -m eval.verify_release v1.4.1-results --additive
step "tests (default)" $PY -m pytest -q
step "tests (slow: TLC)" $PY -m pytest -q -m slow
step "tests (local LLM)" $PY -m pytest -q -m llm
step "commit" git add results paper paper_pack paper_pack_v1.5.zip docs
git commit -q -m "v1.5-results: E8 LLM adversarial supplier (D43), refreshed NUMBERS.md (RQ3), tables, workbook, paper pack; every prior number identical to v1.4.1-results

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || fail "commit"
step "tag" git tag -a v1.5-results -m "v1.5-results: + E8 (LLM adversarial supplier, black-box and white-box, 7 defenses, seeds 1-3)"
log "DONE at $(git rev-parse --short HEAD) (not pushed)"
