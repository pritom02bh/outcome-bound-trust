"""Inter-annotator agreement (DECISIONS D42): an independent annotator's labels against ours.

    python -m eval.agreement annotation/returned/spotcheck_blind.csv annotation/returned/enron_blind.csv
        -> runs/agreement/agreement.json and a printed report (not run until the annotator's files are back)

Spot-check: `looks_correct` (yes/no) per row, joined on `id`, against data/spotcheck.csv.
Enron: `is_commitment` (yes/no) per row, joined on `row` (1-based, the file order), against
data/enron_candidates.csv; plus slot agreement on the rows both mark yes.

Cohen's kappa is reported with raw agreement. When one side gives the same label to every row (our spot-check
labels are all "yes"), expected agreement equals observed agreement or kappa is 0 whatever the annotator does:
kappa is then reported as degenerate and raw agreement plus the disagreement list carry the information.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YES, NO = "yes", "no"
SLOTS = ("has_delivery_claim", "qty", "deadline", "has_price_claim", "price", "valid_until")


def yn(v) -> str | None:
    s = str(v or "").strip().lower()
    return YES if s in ("yes", "y", "true", "1") else NO if s in ("no", "n", "false", "0") else None


def kappa(a: list[str], b: list[str]) -> dict:
    """Cohen's kappa for two equal-length lists of yes/no labels."""
    if len(a) != len(b) or not a:
        raise ValueError("need two non-empty label lists of equal length")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(x == YES for x in a) / n, sum(x == YES for x in b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    degenerate = pa in (0.0, 1.0) or pb in (0.0, 1.0)
    k = None if pe == 1 else (po - pe) / (1 - pe)
    return {"n": n, "raw_agreement": round(po, 4), "kappa": None if k is None else round(k, 4),
            "expected_agreement": round(pe, 4), "ours_yes_rate": round(pa, 4), "theirs_yes_rate": round(pb, 4),
            "degenerate": degenerate,
            "note": ("one side gives every row the same label, so kappa is uninformative; use raw agreement and "
                     "the disagreements") if degenerate else ""}


def _num(v: str):
    s = str(v or "").strip().replace("$", "").replace(",", "")
    try:
        return round(float(s), 4)
    except ValueError:
        return re.sub(r"\s+", " ", str(v or "").strip().lower()) or None


def _date(v: str):
    s = str(v or "").strip()
    parts = [p.strip() for p in s.split("/") if p.strip()] if " / " in s else [s]
    return tuple(sorted(p.lower() for p in parts)) or None


def spotcheck(theirs: Path, ours: Path = ROOT / "data" / "spotcheck.csv") -> dict:
    o = {r["id"]: yn(r["looks_correct"]) for r in csv.DictReader(ours.open(newline=""))}
    t = {r["id"]: yn(r["looks_correct"]) for r in csv.DictReader(theirs.open(newline=""))}
    missing = sorted(i for i in o if t.get(i) is None)
    if missing:
        raise ValueError(f"annotator left {len(missing)} spot-check rows unlabeled, e.g. {missing[:5]}")
    ids = sorted(o)
    k = kappa([o[i] for i in ids], [t[i] for i in ids])
    k["disagreements"] = [{"id": i, "ours": o[i], "theirs": t[i]} for i in ids if o[i] != t[i]]
    return k


def enron(theirs: Path, ours: Path = ROOT / "data" / "enron_candidates.csv") -> dict:
    o = list(csv.DictReader(ours.open(newline="")))
    t = list(csv.DictReader(theirs.open(newline="")))
    if len(o) != len(t):
        raise ValueError(f"row count differs: ours {len(o)}, theirs {len(t)}")
    for i, (a, b) in enumerate(zip(o, t), 1):
        if str(b.get("row", i)).strip() not in ("", str(i)) or a["message"] != b["message"]:
            raise ValueError(f"row {i} does not line up with our file (order or text changed)")
    lo, lt = [yn(r["is_commitment"]) for r in o], [yn(r["is_commitment"]) for r in t]
    missing = [i for i, x in enumerate(lt, 1) if x is None]
    if missing:
        raise ValueError(f"annotator left {len(missing)} Enron rows without is_commitment, e.g. rows {missing[:5]}")
    k = kappa(lo, lt)
    k["disagreements"] = [{"row": i, "ours": a, "theirs": b, "message": o[i - 1]["message"][:120],
                           "our_notes": o[i - 1]["notes"], "their_notes": t[i - 1].get("notes", "")}
                          for i, (a, b) in enumerate(zip(lo, lt), 1) if a != b]
    both = [i for i, (a, b) in enumerate(zip(lo, lt)) if a == b == YES]
    per_slot = {}
    slot_diffs = []
    for s in SLOTS:
        norm = yn if s.startswith("has_") else (_date if s in ("deadline", "valid_until") else _num)
        same = [norm(o[i][s]) == norm(t[i].get(s, "")) for i in both]
        per_slot[s] = {"rows": len(both), "agree": sum(same)}
        slot_diffs += [{"row": i + 1, "slot": s, "ours": o[i][s], "theirs": t[i].get(s, "")}
                       for i, ok in zip(both, same) if not ok]
    k["slot_agreement_on_rows_both_yes"] = per_slot
    k["slot_disagreements"] = slot_diffs
    return k


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        sys.exit(2)
    rep = {"spotcheck": spotcheck(Path(argv[0])), "enron": enron(Path(argv[1]))}
    out = ROOT / "runs" / "agreement"
    out.mkdir(parents=True, exist_ok=True)
    (out / "agreement.json").write_text(json.dumps(rep, indent=1) + "\n")
    for name, r in rep.items():
        print(f"{name}: n={r['n']} raw agreement {r['raw_agreement']} kappa {r['kappa']}"
              + (f" (degenerate: {r['note']})" if r["degenerate"] else "")
              + f"; {len(r['disagreements'])} disagreements")
    for s, v in rep["enron"]["slot_agreement_on_rows_both_yes"].items():
        print(f"  enron slot {s}: {v['agree']}/{v['rows']}")
    print(f"written to {out / 'agreement.json'}")


if __name__ == "__main__":
    main()
