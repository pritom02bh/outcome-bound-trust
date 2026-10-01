#!/bin/bash
# E9 chain (DECISIONS D44). Run only after E8's chain has finished, from the repo root, with the E9 code committed:
#   nohup caffeinate -i bash eval/e9.sh >> runs/e9.log 2>&1 &
# 1. Prove the supply domain unchanged (byte-identical vs v1.4.1-results) or stop. 2. All tests. 3. E9's 84 scripted
# runs (stop on any violation). 4. Refresh, verify every prior number unchanged vs v1.5-results, all tests, tag
# v1.6-results. No model call except the frozen extractor's cache reads; never pushes.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
unset OBT_ALLOW_PAID
PY=.venv/bin/python
OLD="$(cd .. && pwd)/obt-v141"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fail() { log "STOP: $*"; exit 1; }
step() { log "== $1"; shift; "$@" || fail "step failed (exit $?): $*"; }

log "e9 armed at $(git rev-parse --short HEAD)"
[ -d "$OLD" ] || git worktree add --detach "$OLD" v1.4.1-results || fail "old worktree"
mkdir -p results/e9_equivalence
# Run the script from a neutral directory: from eval/ its sibling eval/numbers.py would shadow the stdlib module, and
# from the repo root the new code would shadow the old. Only the code root on PYTHONPATH is then importable.
EQ="$(mktemp -d)"; cp eval/e9_equivalence.py "$EQ/"; ROOT="$(pwd)"; PYA="$ROOT/.venv/bin/python"
step "equivalence: dump under v1.4.1-results" bash -c "cd '$EQ' && PYTHONPATH='$OLD' '$PYA' e9_equivalence.py dump \
     '$ROOT/results/e9_equivalence/old.json' '$ROOT/runs/cache/extract'"
step "equivalence: dump under the E9 code" bash -c "cd '$EQ' && PYTHONPATH='$ROOT' '$PYA' e9_equivalence.py dump \
     '$ROOT/results/e9_equivalence/new.json' '$ROOT/runs/cache/extract'"
step "equivalence: byte-identical ledgers, costs, verdicts and gate differential" bash -c "cd '$EQ' && '$PYA' \
     e9_equivalence.py compare '$ROOT/results/e9_equivalence/old.json' '$ROOT/results/e9_equivalence/new.json' \
     '$ROOT/results/e9_equivalence/report.json'"
step "tests (default)" $PY -m pytest -q
step "tests (slow: TLC)" $PY -m pytest -q -m slow
step "tests (local LLM)" $PY -m pytest -q -m llm
step "E9: 84 runs (7 scenarios x 4 defenses x seeds 1-3)" $PY -m eval.e9 run
step "refresh: results" $PY -m eval.results --runs runs --out results
step "refresh: paper tables, figures, NUMBERS.md (E9 under RQ5)" $PY -m eval.paper
step "refresh: INDEX.md E9 row and D44 outcome" $PY -m eval.e9 notes
step "refresh: workbook + paper pack" $PY -m eval.pack
step "verify: every prior number identical to v1.5-results" $PY -m eval.verify_release v1.5-results --additive \
     --tables=e9,e9_damage_vs_bound --sheets=E9 --marker='e9'
step "tests (default, after refresh)" $PY -m pytest -q
step "commit" git add results paper paper_pack paper_pack_v1.6.zip docs
git commit -q -m "v1.6-results: E9 second domain (cloud/API capacity, D44): supply domain proven byte-identical to v1.4.1-results; 84 scripted runs; refreshed NUMBERS.md (RQ5), tables, workbook, paper pack; every prior number identical to v1.5-results" || fail "commit"

step "tag" git tag -a v1.6-results -m "v1.6-results: + E9 (second domain: cloud/API capacity, SLA and QUOTA templates)"
log "DONE at $(git rev-parse --short HEAD) (not pushed)"
