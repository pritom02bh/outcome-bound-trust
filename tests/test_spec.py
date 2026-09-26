"""F6: TLC on the TLA+ spec. The unmutated spec passes; every guard-removal mutant is caught.

Slow (~3 min): run with `pytest -m slow`. Full bounds are run by hand with spec/run_mutants.sh;
their outputs are committed under spec/results/.
"""
import glob
import shutil
import subprocess
from pathlib import Path

import pytest

SPEC = Path(__file__).resolve().parent.parent / "spec"
HAVE_JAVA = bool(glob.glob(str(SPEC.parent / "tools/jdk-*/Contents/Home/bin/java"))) or shutil.which("java")


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_JAVA, reason="no Java for TLC")
def test_quick_bounds_spec_passes_and_all_mutants_caught():
    r = subprocess.run([str(SPEC / "run_mutants.sh"), "quick"], capture_output=True, text=True, timeout=3600)
    rows = {line.split()[0]: line for line in r.stdout.splitlines() if line.strip()}
    assert "PASS" in rows["none"], r.stdout
    for m in ("I1", "I2", "I4", "I6", "I7"):
        assert f"CAUGHT({m})" in rows[m] and f"{m} is violated" in rows[m], rows[m]
    assert "PASS(no-op)" in rows["ITEM"], rows["ITEM"]            # one item: nothing to mis-bind
    for m in ("XSUP-RECEIPT", "XSUP-BUDGET"):                    # one supplier: nothing to cross
        assert "PASS(no-op)" in rows[m], rows[m]
    assert r.returncode == 0


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_JAVA, reason="no Java for TLC")
def test_cross_supplier_mutants_caught_with_two_suppliers():
    import os
    r = subprocess.run([str(SPEC / "run_mutants.sh"), "fallbackA2"], capture_output=True, text=True,
                       timeout=3600, env={**os.environ, "ONLY": "XSUP-RECEIPT XSUP-BUDGET"})
    rows = {line.split()[0]: line for line in r.stdout.splitlines() if line.strip()}
    assert "CAUGHT(I7)" in rows["XSUP-RECEIPT"] and "CAUGHT(I2)" in rows["XSUP-BUDGET"], r.stdout
    assert r.returncode == 0


@pytest.mark.slow
@pytest.mark.skipif(not HAVE_JAVA, reason="no Java for TLC")
def test_item_binding_mutant_caught_with_two_items():
    import os
    r = subprocess.run([str(SPEC / "run_mutants.sh"), "fallbackB"], capture_output=True, text=True,
                       timeout=3600, env={**os.environ, "ONLY": "ITEM"})
    row = next(line for line in r.stdout.splitlines() if line.startswith("ITEM"))
    assert "CAUGHT(I1)" in row and "I1 is violated" in row, r.stdout
    assert r.returncode == 0
