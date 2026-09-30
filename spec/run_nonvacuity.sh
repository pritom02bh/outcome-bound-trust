#!/usr/bin/env bash
# Non-vacuity check for the budget multiplier K (DECISIONS D36a). At the given bounds and K, TLC must find both
# KProbe.tla witnesses: a reachable decision where the budget binds while earned trust > 0, and one that K = 1
# and K = 2 decide differently. Each probe is an invariant that must be VIOLATED; if either holds exhaustively,
# K is not exercised at these bounds and the config fails (exit 1).
#   K=2 B0V=1 spec/run_nonvacuity.sh quick      -> results/<tag>_nonvacuity.txt, results/<tag>_nv_<probe>.out
set -uo pipefail
cd "$(dirname "$0")"
JAVA=$(ls -d ../tools/jdk-*/Contents/Home/bin/java 2>/dev/null | head -1)
JAVA=${JAVA:-java}
MODE=${1:?mode}; K=${K:-1}; B0V=${B0V:-}; MAXQ=${MAXQ:-2}
TAG=$MODE; [ -z "$B0V" ] || TAG=${TAG}_b0${B0V}; [ "$MAXQ" = 2 ] || TAG=${TAG}_q${MAXQ}; [ "$K" = 1 ] || TAG=${TAG}_k${K}
RESULTS=${RESULTS:-results}
mkdir -p "$RESULTS" states
base=$(CFG_ONLY=1 K=$K B0V=$B0V MAXQ=$MAXQ ./run_mutants.sh "$MODE") || exit 1
OUT=$RESULTS/${TAG}_nonvacuity.txt
{
  echo "# K non-vacuity (KProbe.tla): mode=$MODE K=$K B0=${B0V:-mode default} MaxQty=$MAXQ"
  echo "# date: $(date -u +%Y-%m-%dT%H:%M:%SZ)  host: $(uname -sm)"
  echo "# bounds: $(echo "$base" | sed -n '/CONSTANTS/,/MUTANT/p' | grep -v CONSTANTS | tr -s ' \n' ' ')"
  printf '%-28s %-9s %16s %6s %9s\n' probe result distinct_states length runtime_s
} > "$OUT"
status=0
for inv in BudgetNeverBindsWhenEarned KNeverChangesADecision; do
  cfg=states/${TAG}_nv_${inv}.cfg
  { echo "$base"; echo "INVARIANT TypeOK"; echo "INVARIANT $inv"; } > "$cfg"
  out=$RESULTS/${TAG}_nv_${inv}.out
  start=$(date +%s)
  "$JAVA" -XX:+UseParallelGC -Xmx12g -cp tla2tools.jar tlc2.TLC -workers auto -deadlock \
      -metadir "states/${TAG}_nv_${inv}" -config "$cfg" KProbe.tla > "$out" 2>&1
  secs=$(( $(date +%s) - start ))
  if grep -q "Invariant $inv is violated" "$out"; then r=WITNESS
  elif grep -q "No error has been found" "$out"; then r=VACUOUS; status=1
  else r=ERROR; status=1; fi
  states=$(grep -Eo '[0-9,]+ distinct states found' "$out" | tail -1 | grep -Eo '^[0-9,]+')
  len=$(grep -Eo '^State [0-9]+:' "$out" | grep -Eo '[0-9]+' | sort -n | tail -1)
  printf '%-28s %-9s %16s %6s %9s\n' "$inv" "$r" "${states:-?}" "${len:--}" "$secs" | tee -a "$OUT"
done
exit $status
