"""Mutant coverage per K (DECISIONS D36a): every mutant must be caught in at least one config for each K.

    python spec/coverage_k.py      # reads results/*summary*.txt, writes results/k_coverage.txt; exit 1 if not
"""
import sys
from pathlib import Path

R = Path(__file__).parent / "results"
MUTANTS = ("I1", "I2", "I4", "I6", "I7", "ITEM", "XSUP-RECEIPT", "XSUP-BUDGET")
# (config label, summary file) per K. B at K = 2 runs ITEM only: it is the one mutant caught nowhere else.
CONFIGS = {
    1: [("quick", "quick_summary.txt"), ("A'", "fallbackA2_summary.txt"), ("B", "fallbackB_summary.txt"),
        ("quick B0=1", "quick_b01_summary.txt"), ("A' B0=1", "fallbackA2_b01_summary.txt")],
    2: [("quick", "quick_k2_summary.txt"), ("A'", "fallbackA2_k2_summary.txt"),
        ("B (ITEM only)", "fallbackB_k2_summary_only_ITEM.txt"),
        ("quick B0=1", "quick_b01_k2_summary.txt"), ("A' B0=1", "fallbackA2_b01_k2_summary.txt")],
}


def verdicts(f: Path) -> dict[str, str]:
    rows = [l.split() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")]
    return {r[0]: r[1] for r in rows[1:]}


def main() -> int:
    ok, lines = True, []
    for k, cfgs in CONFIGS.items():
        table = {name: verdicts(R / f) for name, f in cfgs}
        lines.append(f"K = {k}: " + " | ".join(name for name, _ in cfgs))
        for m in MUTANTS:
            cells = [table[name].get(m, "-") for name, _ in cfgs]
            caught = [name for (name, _), v in zip(cfgs, cells) if v.startswith("CAUGHT")]
            ok &= bool(caught)
            lines.append(f"  {m:13s} {'OK ' if caught else 'MISSING'} " + " | ".join(cells))
        pas = [name for name in table if not table[name].get("none", "PASS").startswith("PASS")]
        ok &= not pas
        lines.append(f"  none          {'OK ' if not pas else 'FAIL'} "
                     + " | ".join(table[name].get("none", "-") for name, _ in cfgs))
    lines.append("RESULT: " + ("every mutant caught in >= 1 config for each K" if ok else "COVERAGE FAILURE"))
    (R / "k_coverage.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
