#!/usr/bin/env bash
# Model-check OBT.tla. Needs Java (tools/jdk-* or system java) and spec/tla2tools.jar.
#   spec/check.sh          -> correct gate, expect "No error has been found" (~5 min, ~80M states)
#   spec/check.sh mutant   -> budget check removed, expect "Action property I1 is violated"
set -euo pipefail
cd "$(dirname "$0")"
JAVA=$(ls -d ../tools/jdk-*/Contents/Home/bin/java 2>/dev/null | head -1 || true)
JAVA=${JAVA:-java}
[ -f tla2tools.jar ] || curl -sSL -o tla2tools.jar https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
CFG=OBT.cfg; [ "${1:-}" = mutant ] && CFG=OBT_mutant.cfg
exec "$JAVA" -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC -workers auto -deadlock -config "$CFG" OBT.tla
