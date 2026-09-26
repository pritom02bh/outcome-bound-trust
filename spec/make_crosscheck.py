"""Build spec/results/symmetry_crosscheck.txt from the run_mutants.sh summaries (FIXES F6).

    python -m spec.make_crosscheck

Tier 1: tiny bounds, every spec, with and without SYMMETRY Symm. Tier 2: quick bounds (3 rounds) for the
I2 and I7 mutants, which need 3 rounds to act. Verdicts must match pairwise; exits 1 otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"


def rows(path: Path) -> dict[str, tuple[str, str, str, str]]:
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("mutant"):
            continue
        p = line.split()
        verdict = "NOT-CAUGHT" if p[1].startswith("NOT-CAUGHT") else p[1]
        out[p[0]] = (verdict, p[-3], p[-2], p[-1])  # verdict, distinct states, depth, seconds
    return out


def header(path: Path) -> list[str]:
    keep = ("# tla2tools.jar", "# java", "# tlc")
    return [line for line in path.read_text().splitlines() if line.startswith(keep)]


def table(title: str, sym: dict, nosym: dict, lines: list[str]) -> bool:
    ok = True
    lines += [title, f"{'mutant':13} {'verdict (sym)':20} {'verdict (no sym)':20} {'states sym':>12} "
                     f"{'states nosym':>13} {'depth s/n':>9} {'secs s/n':>9} match"]
    for m, x in sym.items():
        y = nosym[m]
        same = x[0] == y[0]
        ok &= same
        lines.append(f"{m:13} {x[0]:20} {y[0]:20} {x[1]:>12} {y[1]:>13} {x[2] + '/' + y[2]:>9} "
                     f"{x[3] + '/' + y[3]:>9} {'yes' if same else 'NO'}")
    lines.append("")
    return ok


def main() -> int:
    lines = [
        "Symmetry cross-check for OBT.tla (FIXES F6): verdicts with and without SYMMETRY Symm must match.",
        "Symm = Permutations(Claims) \\cup Permutations(Orders) \\cup Permutations(Pays); every id is a model",
        "value, and the only id-typed sentinel, NoRef, is a model value outside those sets (ASSUME in OBT.tla).",
        "Every run finished: a pass explores the whole state space, and a caught mutant stops at its first violation.",
        "Depth is the complete-search depth for a pass and the counterexample length for a caught mutant. TLC's",
        "parallel BFS doesn't guarantee a shortest counterexample, so depths may differ between columns; verdicts",
        "may not. PASS(no-op) means the mutant can't act at these bounds (ITEM needs 2 items, XSUP-* need 2",
        "suppliers) and must behave exactly like the real spec.",
        "",
    ]
    lines += header(RES / "tiny_summary.txt") + [""]
    ok = table("Tier 1: tiny bounds, all specs. Sups={s1} Items={i1} Claims={k1,k2,k3} Orders={o1,o2} Pays={p1} "
               "Notes={n1} MaxRound=2 B0=2 MinLead=1 W=1",
               rows(RES / "tiny_summary.txt"), rows(RES / "tiny_nosym_summary.txt"), lines)
    lines += ["I2 and I7 can't act in 2 rounds. I2 needs a failure and then the cool-down to expire. I7 needs two",
              "DELIVERY claims plus a PRICE claim at one supplier, but a supplier makes at most 2 claims per round.",
              "Both columns agree they aren't caught; tier 2 checks both where they can act.", ""]
    ok &= table("Tier 2: quick bounds, I2 and I7 mutants. Same as tier 1 but MaxRound=3",
                rows(RES / "quick_summary_only_I2_I7.txt"), rows(RES / "quick_nosym_summary_only_I2_I7.txt"), lines)
    n = sum(1 for line in lines if line.endswith((" yes", " NO")))
    lines.append(f"RESULT: {'all ' + str(n) + ' verdict pairs match' if ok else 'MISMATCH'}")
    (RES / "symmetry_crosscheck.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
