#!/usr/bin/env bash
# Thin wrapper: model-check the unmutated spec only. Default: quick bounds (about 3 min).
#   spec/check.sh [quick|fallbackA2|fallbackB|tiny]
cd "$(dirname "$0")" && ONLY=none ./run_mutants.sh "${1:-quick}" | head -1
