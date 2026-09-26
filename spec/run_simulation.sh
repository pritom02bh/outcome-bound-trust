#!/usr/bin/env bash
# Random-trace simulation of the unmutated spec at full bounds (FIXES F6, tier 3).
#   spec/run_simulation.sh <num_traces> [seed]
# Checks every invariant and action property on every state of every trace.
# Writes spec/results/simulation_full.out and spec/results/simulation_full.txt.
set -uo pipefail
cd "$(dirname "$0")"
JAVA=$(ls -d ../tools/jdk-*/Contents/Home/bin/java 2>/dev/null | head -1)
JAVA=${JAVA:-java}
NUM=${1:?number of traces}
SEED=${2:-20260925}
mkdir -p results states
cfg=states/sim_full.cfg
{ sed -e '/^SYMMETRY/d' results/full_partial/full_none.cfg; echo "INVARIANT SimDepth"; } > "$cfg"
out=results/simulation_full.out
start=$(date +%s)
"$JAVA" -XX:+UseParallelGC -Xmx12g -cp tla2tools.jar tlc2.TLC -simulate num="$NUM" -depth 500 -seed "$SEED" \
    -workers auto -deadlock -metadir states/sim_full -config "$cfg" MCsim.tla > "$out" 2>&1
code=$?
secs=$(( $(date +%s) - start ))
{
  echo "# OBT.tla random simulation, unmutated spec, full bounds (NOT exhaustive)"
  echo "# date: $(date -u +%Y-%m-%dT%H:%M:%SZ)  host: $(uname -sm)  cores: $(sysctl -n hw.ncpu 2>/dev/null || nproc)"
  echo "# tlc: $(grep -m1 -Eo 'TLC2 Version .*' "$out")"
  echo "# tla2tools.jar sha256: $(shasum -a 256 tla2tools.jar | cut -d' ' -f1)"
  echo "# bounds: $(grep -E '^ +[A-Za-z0-9]+ =' "$cfg" | tr -s ' \n' ' ')"
  echo "# symmetry: none (symmetry does not apply to random simulation)"
  echo "seed:              $SEED"
  echo "traces:            $NUM (every trace runs to the end of the final round)"
  echo "states checked:    $(grep -Eo 'Progress: [0-9,]+ states checked' "$out" | tail -1 | grep -Eo '[0-9,]+')"
  echo "max trace depth:   $(grep -Eo 'SIMDEPTH", [0-9]+' "$out" | grep -Eo '[0-9]+$' | sort -n | tail -1) (TLCGet(\"level\") of the last state)"
  echo "runtime_s:         $secs"
  if [ $code -eq 0 ] && grep -q "^Finished" "$out" && ! grep -Eq "is violated|^Error" "$out"; then
    echo "violations:        0"
  else
    echo "violations:        SEE $out (exit $code)"
  fi
} | tee results/simulation_full.txt
exit $code
