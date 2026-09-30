#!/usr/bin/env bash
# DECISIONS D36: K = 1 must reproduce the committed quick and A' results exactly (states, depth, verdict);
# then K = 2 at the same bounds with every applicable mutant. Stops at the first failure.
set -uo pipefail
cd "$(dirname "$0")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
# $1 committed summary, $2 reproduced: every verdict, and the states and depth of every exhaustive (PASS) run,
# must be identical. A caught mutant's counts are where a worker first hit the violation (TLC -workers auto),
# so they can vary between runs; any difference there is logged, not a failure.
cmp_run() {
  diff <(grep -v '^#' "$1" | awk '{s=($2 ~ /^PASS/)?$4" "$5:""; print $1, $2, s}') \
       <(grep -v '^#' "$2" | awk '{s=($2 ~ /^PASS/)?$4" "$5:""; print $1, $2, s}') || return 1
  # The violation column has spaces, so count fields from the end.
  diff <(grep -v '^#' "$1" | awk '$2 != "N/A" {print $1, $(NF-2), $(NF-1)}') \
       <(grep -v '^#' "$2" | awk '$2 != "N/A" {print $1, $(NF-2), $(NF-1)}') \
    || log "note: caught-mutant counterexample counts differ (above); verdicts identical"
  return 0
}
for mode in quick fallbackA2; do
  log "K=1 $mode (reproduction)"
  RESULTS=results/k1_repro K=1 ./run_mutants.sh $mode || { log "STOP: K=1 $mode failed"; exit 1; }
  cmp_run results/${mode}_summary.txt results/k1_repro/${mode}_summary.txt \
    || { log "STOP: K=1 $mode differs from the committed results"; exit 1; }
  log "K=1 $mode identical to the committed results"
done
for mode in quick fallbackA2; do
  log "K=2 $mode"
  K=2 ./run_mutants.sh $mode || { log "STOP: K=2 $mode failed"; exit 1; }
done
log "== done"
