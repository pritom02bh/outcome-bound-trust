#!/usr/bin/env bash
# DECISIONS D36a: quick and A' with B0 = 1 at K = 1 and K = 2. Per config and K: the non-vacuity probes first
# (both witnesses required), then the unmutated spec and every mutant. Mutants that find no violation at B0 = 1
# are N/A(no-viol), allowed only if caught in another config for the same K (coverage_k.py). Stops at the first
# failure.
set -uo pipefail
cd "$(dirname "$0")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
ALL="I1 I2 I4 I6 I7 ITEM XSUP-RECEIPT XSUP-BUDGET"
# Control: at the old quick bounds (B0 = 2) K can't matter (D36a), so both probes must come back VACUOUS.
log "control: quick B0=2 K=1 probes must be VACUOUS"
RESULTS=results/k_probe/control ./run_nonvacuity.sh quick && { log "STOP: control found a witness"; exit 1; }
[ "$(grep -c ' VACUOUS ' results/k_probe/control/quick_nonvacuity.txt)" = 2 ] \
  || { log "STOP: control did not return VACUOUS for both probes"; exit 1; }
for K in 1 2; do
  for mode in quick fallbackA2; do
    log "K=$K $mode B0=1: non-vacuity"
    K=$K B0V=1 ./run_nonvacuity.sh $mode || { log "STOP: K=$K $mode B0=1 is vacuous (or TLC error)"; exit 1; }
    log "K=$K $mode B0=1: unmutated + mutants"
    K=$K B0V=1 SKIP= MAYBE_NA="$ALL" ./run_mutants.sh $mode || { log "STOP: K=$K $mode B0=1 failed"; exit 1; }
  done
done
log "K=2 B: ITEM only (caught only where there are two items)"
K=2 ONLY=ITEM ./run_mutants.sh fallbackB || { log "STOP: K=2 B ITEM failed"; exit 1; }
log "coverage"
python3 coverage_k.py || { log "STOP: coverage"; exit 1; }
log "== done"
