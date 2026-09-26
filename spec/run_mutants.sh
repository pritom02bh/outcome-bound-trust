#!/usr/bin/env bash
# Model-check OBT.tla unmutated and with each guard removed (FIXES F6).
#   spec/run_mutants.sh          full bounds: 2 suppliers, 2 items, 6 rounds
#   spec/run_mutants.sh quick    small bounds for the test suite
#   spec/run_mutants.sh fallbackA2|fallbackB  the two exhaustive configs in results/README.md (A: stopped)
#   spec/run_mutants.sh tiny     2 rounds, for the symmetry cross-check
#   ONLY="I2 I7" ...             run only these (summary gets a suffix)
#   SYM=0 spec/run_mutants.sh    without symmetry reduction (for the reduction-ratio comparison)
# Every mutant runs at exactly the bounds the unmutated spec uses.
# Writes spec/results/<bounds>_<mutant>.out and spec/results/<bounds>_summary.txt.
# Exit code is non-zero if the unmutated spec fails or any mutant goes uncaught.
set -uo pipefail
cd "$(dirname "$0")"
JAVA=$(ls -d ../tools/jdk-*/Contents/Home/bin/java 2>/dev/null | head -1)
JAVA=${JAVA:-java}
[ -f tla2tools.jar ] || curl -sSL -o tla2tools.jar https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
MODE=${1:-full}
if [ "$MODE" = tiny ]; then
  # Symmetry cross-check bounds: small enough to finish without symmetry.
  BOUNDS='Sups = {s1}
    Items = {i1}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 2
    B0 = 2
    MinLead = 1'
elif [ "$MODE" = fallbackA ]; then
  # Exhaustive config A: two suppliers (cross-supplier binding). See results/README.md.
  BOUNDS='Sups = {s1, s2}
    Items = {i1}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 3
    B0 = 2
    MinLead = 1'
elif [ "$MODE" = fallbackA2 ]; then
  # Config A': two suppliers (cross-supplier binding), 2 rounds. Config A (3 rounds) did not finish;
  # see results/README.md and results/fallbackA_partial/.
  BOUNDS='Sups = {s1, s2}
    Items = {i1}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 2
    B0 = 2
    MinLead = 1'
  # ITEM is a no-op with one item; I2 and I7 can't act in 2 rounds (caught in quick and B instead).
  SKIP=${SKIP-ITEM I2 I7}
elif [ "$MODE" = fallbackB ]; then
  # Exhaustive config B: two items (cross-item binding; the ITEM mutant needs it).
  BOUNDS='Sups = {s1}
    Items = {i1, i2}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 3
    B0 = 2
    MinLead = 1'
elif [ "$MODE" = quick ]; then
  BOUNDS='Sups = {s1}
    Items = {i1}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 3
    B0 = 2
    MinLead = 1'
else
  BOUNDS='Sups = {s1, s2}
    Items = {i1, i2}
    Claims = {k1, k2, k3}
    Orders = {o1, o2}
    Pays = {p1}
    Notes = {n1}
    MaxRound = 6
    B0 = 1
    MinLead = 2'
fi
SYM=${SYM:-1}
TAG=$MODE; [ "$SYM" = 1 ] || TAG=${MODE}_nosym
ONLY=${ONLY:-}
if [ "$SYM" = 1 ]; then SYMLINE='SYMMETRY Symm'; SYMDESC='Permutations(Claims) \cup Permutations(Orders) \cup Permutations(Pays)'
else SYMLINE=''; SYMDESC='none'; fi
mkdir -p results states
SUMMARY=results/${TAG}_summary${ONLY:+_only_${ONLY// /_}}.txt
{
  echo "# OBT.tla model check: mode=$MODE"
  echo "# date: $(date -u +%Y-%m-%dT%H:%M:%SZ)  host: $(uname -sm)  cores: $(sysctl -n hw.ncpu 2>/dev/null || nproc)"
  echo "# tla2tools.jar sha256: $(shasum -a 256 tla2tools.jar | cut -d' ' -f1)"
  echo "# java: $("$JAVA" -version 2>&1 | head -1)"
  echo "# bounds: $(echo "$BOUNDS" | tr -s ' \n' ' ') W = 1"
  echo "# symmetry: $SYMDESC"
  printf '%-12s %-18s %-32s %16s %6s %9s\n' mutant verdict violation distinct_states depth runtime_s
} > "$SUMMARY"
status=0
# Quick bounds use B0 = 2 (a 3-claim pool leaves no room to earn trust before a 2-unit order)
# and MinLead = 1 (so a claim can fail and its cool-down expire within 3 rounds, the I2 witness).
# mutant -> property TLC must report as violated ("" = must pass)
for pair in "none:" "I1:I1" "I2:I2" "I4:I4" "I6:I6" "I7:I7" "ITEM:I1" "XSUP-RECEIPT:I7" "XSUP-BUDGET:I2"; do
  m=${pair%%:*}; want=${pair#*:}
  [ -z "$ONLY" ] || [[ " $ONLY " == *" $m "* ]] || continue
  if [[ " ${SKIP:-} " == *" $m "* ]]; then
    printf '%-12s %-18s %s\n' "$m" "N/A" "not applicable at these bounds (unreachable); see results/README.md" | tee -a "$SUMMARY"
    continue
  fi
  # With one item the ITEM mutant is a no-op: it must then behave like the real spec.
  noop=0; if [ "$m" = ITEM ] && ! echo "$BOUNDS" | grep -q 'Items = {i1, i2'; then want=""; noop=1; fi
  # Likewise the cross-supplier mutants with one supplier.
  if [[ "$m" == XSUP-* ]] && ! echo "$BOUNDS" | grep -q 'Sups = {s1, s2'; then want=""; noop=1; fi
  cfg=states/${TAG}_${m}.cfg
  cat > "$cfg" <<CFG
SPECIFICATION Spec
CONSTANTS
    $BOUNDS
    W = 1
    NoRef = NoRef
    MUTANT = "$m"
$SYMLINE
INVARIANT TypeOK
INVARIANT I4
INVARIANT I6
INVARIANT I7
PROPERTY I1
PROPERTY I2
PROPERTY I3
CFG
  out=results/${TAG}_${m}.out
  start=$(date +%s)
  "$JAVA" -XX:+UseParallelGC -Xmx12g -cp tla2tools.jar tlc2.TLC -workers auto -deadlock \
      -metadir "states/${TAG}_${m}" -config "$cfg" OBT.tla > "$out" 2>&1
  secs=$(( $(date +%s) - start ))
  states=$(grep -Eo '[0-9,]+ distinct states found' "$out" | tail -1)
  if [ -z "$want" ]; then
    if grep -q "No error has been found" "$out"; then verdict=PASS; else verdict=FAIL; status=1; fi
    [ $noop = 1 ] && verdict="${verdict}(no-op)"
  else
    if grep -Eq "(Invariant|Action property|Temporal properties) $want (is )?violated|property $want is violated|Invariant $want is violated" "$out"; then
      verdict="CAUGHT($want)"
    else verdict="NOT-CAUGHT(want $want)"; status=1; fi
  fi
  got=$(grep -Eo '(Invariant|Action property) [A-Za-z0-9]+ is violated' "$out" | head -1)
  # Depth: of the complete search when it passes, of the counterexample when a mutant is caught.
  depth=$(grep -Eo 'depth of the complete state graph search is [0-9]+' "$out" | grep -Eo '[0-9]+$')
  [ -n "$depth" ] || depth=$(grep -Eo '^State [0-9]+:' "$out" | grep -Eo '[0-9]+' | sort -n | tail -1)
  printf '%-12s %-18s %-32s %16s %6s %9s\n' "$m" "$verdict" "${got:-none}" \
      "$(echo "${states:-?}" | grep -Eo '^[0-9,]+')" "${depth:-?}" "$secs" | tee -a "$SUMMARY"
  [ "$m" = none ] && [ "$MODE" = full ] && [ "$SYM" = 1 ] && cp "$cfg" OBT.cfg
done
echo "# tlc: $(grep -h -m1 -Eo 'TLC2 Version .*' results/${TAG}_*.out | head -1)" >> "$SUMMARY"
exit $status
