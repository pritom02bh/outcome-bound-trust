"""Release check (D41): compare this build with a previous tag.

    python -m eval.verify_release v1.3-paper-pack      # exit 1 and list every difference if one is unexpected

Every number that depends neither on the new E5 seeds nor on the new per-unit metric (D40) must be identical to
the base tag. What may change or be new, and nothing else:
  - tables.json `e5` (every seed now), the E5 rows of `bound_tightness`, and the new per-unit tables;
  - `main`: one new column (loss per 100 S_main units); its old columns must be identical;
  - NUMBERS.md rows sourced from those; results/e5__* files; the workbook's E5, E2 (main block), E6 (bound
    tightness block) and new per-unit sheets.
Every new number must trace to its source: the per-unit table and the E5 loss means are recomputed from the
per-run trace (results/per_unit/runs.csv) and must match what is exported.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
NUM = re.compile(r"(?<![A-Za-z0-9.])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z\d])")
CHANGED_TABLES = {"e5"}
NEW_TABLES = {"loss_per_unit", "loss_per_unit_by_scenario", "e5_loss_per_unit_by_scenario"}
CHANGED_SHEETS = {"E2", "E5", "E6"}          # checked block by block through tables.json instead
NEW_SHEETS = {"loss per unit"}


def _old(tag: str, path: str, binary: bool = False):
    r = subprocess.run(["git", "show", f"{tag}:{path}"], cwd=ROOT, capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()


def _e5ish(source: str) -> bool:
    return "e5[" in source or "bound_tightness[eval=E5" in source or "loss_per_unit" in source


def check_tables(tag: str) -> list:
    bad = []
    old, new = json.loads(_old(tag, "results/tables.json")), json.loads((ROOT / "results/tables.json").read_text())
    for name, t in old.items():
        if name in CHANGED_TABLES:
            continue
        if name not in new:
            bad.append(("tables.json", name, "missing"))
            continue
        n = new[name]
        if name == "main":
            nrows = {r[0]: dict(zip(n["columns"], r)) for r in n["rows"]}
            for r in t["rows"]:
                o = dict(zip(t["columns"], r))
                if any(nrows.get(r[0], {}).get(c) != v for c, v in o.items()):
                    bad.append(("tables.json", "main", r[0], o, nrows.get(r[0])))
            continue
        if name == "bound_tightness":
            keep = lambda rows: [r for r in rows if not str(r[0]).startswith("E5")]  # noqa: E731
            if t["columns"] != n["columns"] or keep(t["rows"]) != keep(n["rows"]):
                bad.append(("tables.json", name, "non-E5 rows differ"))
            continue
        if t["columns"] != n["columns"] or t["rows"] != n["rows"]:
            bad.append(("tables.json", name, "rows differ"))
    for name in NEW_TABLES:
        if name not in new and name != "e5_loss_per_unit_by_scenario":
            bad.append(("tables.json", name, "new table missing"))
    # Every unchanged .tex table has the same numbers.
    for tex in sorted((ROOT / "paper" / "tables").glob("*.tex")):
        if tex.stem in CHANGED_TABLES | NEW_TABLES | {"main", "bound_tightness"}:
            continue
        try:
            o = _old(tag, f"paper/tables/{tex.name}")
        except subprocess.CalledProcessError:
            bad.append(("tex", tex.name, "not in base"))
            continue
        if Counter(NUM.findall(o)) != Counter(NUM.findall(tex.read_text())):
            bad.append(("tex", tex.name, "numbers differ"))
    return bad


def _rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in line.strip("|").split(" | ")] for line in text.splitlines()
            if line.startswith("| ") and not line.startswith("| claim")]


def check_numbers(tag: str) -> list:
    bad = []
    new = defaultdict(list)
    for r in _rows((ROOT / "paper" / "NUMBERS.md").read_text()):
        new[r[4]].append(r)
    for r in _rows(_old(tag, "paper/NUMBERS.md")):
        if _e5ish(r[4]):
            continue
        cands = new.get(r[4], [])
        if not any((c[1], c[2], c[3]) == (r[1], r[2], r[3]) for c in cands):
            bad.append(("NUMBERS.md", r[0], r[1], [c[1] for c in cands]))
    return bad


def check_csvs(tag: str) -> list:
    """Per-eval CSVs that feed the workbook: every one not from E5 is byte-identical to the base."""
    bad = []
    for f in sorted((ROOT / "results").glob("*/*.csv")):
        rel = str(f.relative_to(ROOT))
        if rel.startswith("results/e5") or rel.startswith("results/per_unit"):
            continue
        try:
            if _old(tag, rel) != f.read_text():
                bad.append(("csv", rel, "differs"))
        except subprocess.CalledProcessError:
            bad.append(("csv", rel, "not in base"))
    return bad


def check_workbook(tag: str) -> list:
    from openpyxl import load_workbook
    bad = []
    old = load_workbook(io.BytesIO(_old(tag, "paper_pack/results_all.xlsx", binary=True)))
    new = load_workbook(ROOT / "paper_pack" / "results_all.xlsx")
    for ws in old.worksheets:
        if ws.title in CHANGED_SHEETS or ws.title == "README":
            continue
        if ws.title not in new.sheetnames:
            bad.append(("xlsx", ws.title, "missing"))
            continue
        a = [list(r) for r in ws.iter_rows(values_only=True)]
        b = [list(r) for r in new[ws.title].iter_rows(values_only=True)]
        if a != b:
            bad.append(("xlsx", ws.title, "cells differ"))
    return bad


def check_trace() -> list:
    """The per-unit table and E5 loss means, recomputed from the per-run trace."""
    import csv
    bad = []
    t = json.loads((ROOT / "results/tables.json").read_text())
    t |= json.loads((ROOT / "results/per_unit/loss_per_unit.json").read_text())     # D40: kept off the paper
    runs = list(csv.DictReader((ROOT / "results/per_unit/runs.csv").open()))
    groups = defaultdict(list)
    for r in runs:
        groups[(r["eval"], r["defense"])].append(r)
    cols = t["loss_per_unit"]["columns"]
    for row in t["loss_per_unit"]["rows"]:
        x = dict(zip(cols, row))
        g = groups[(x["eval"], x["defense"])]
        scen = {r["scenario"] for r in g}
        seeds = [s for s in sorted({r["seed"] for r in g}) if {r["scenario"] for r in g if r["seed"] == s} == scen]
        ratio = [100 * sum(float(r["loss_from_lies"]) for r in g if r["seed"] == s)
                 / sum(int(r["s_main_units"]) for r in g if r["seed"] == s) for s in seeds]
        loss = [mean(float(r["loss_from_lies"]) for r in g if r["seed"] == s) for s in seeds]
        for label, got, want in (("per-unit", x["loss per 100 S_main units"], mean(ratio)),
                                 ("loss", x["loss from lies"], mean(loss))):
            if abs(float(got.split(" [")[0].replace(",", "")) - want) > 0.051:
                bad.append(("trace", x["eval"], x["defense"], label, got, round(want, 3)))
        if int(x["seeds"]) != len(seeds):
            bad.append(("trace", x["eval"], x["defense"], "seeds", x["seeds"], len(seeds)))
    e5 = {(r[0].replace("GPT-5.6 ", "E5 "), r[1]): dict(zip(t["e5"]["columns"], r)) for r in t["e5"]["rows"]}
    for row in t["loss_per_unit"]["rows"]:
        x = dict(zip(cols, row))
        if (x["eval"], x["defense"]) in e5 and e5[(x["eval"], x["defense"])]["loss from lies"] != x["loss from lies"]:
            bad.append(("trace", "e5 vs loss_per_unit", x["eval"], x["defense"]))
    return bad


# ------------------------------------------------------------------ v1.4.1: the D40 metric leaves the paper

PU_COL = "loss per 100 S_main units"
PU_TABLES = ("loss_per_unit", "loss_per_unit_by_scenario", "e5_loss_per_unit_by_scenario")
NEW_ROWS = ("`obt` vs `rep-strict`: loss from lies at matched utility cost (derived)",
            "`obt+planner` vs `rep-strict`: S_main share (honest) and loss from lies (derived)")


def check_drop_per_unit(tag: str) -> dict:
    """Against `tag` (v1.4-results): the per-unit column, tables, NUMBERS rows and sheet are gone from the paper
    outputs, the metric itself is unchanged under results/per_unit/, two derived RQ1 rows are new, and every other
    number is identical."""
    bad: dict = {k: [] for k in ("tables", "tex", "numbers", "csvs", "workbook", "per_unit")}
    old, new = json.loads(_old(tag, "results/tables.json")), json.loads((ROOT / "results/tables.json").read_text())
    for name, t in old.items():
        if name in PU_TABLES:
            if name in new:
                bad["tables"].append((name, "still exported"))
            continue
        if name not in new:
            bad["tables"].append((name, "missing"))
            continue
        cols, rows = t["columns"], t["rows"]
        if PU_COL in cols:
            i = cols.index(PU_COL)
            cols, rows = cols[:i] + cols[i + 1:], [r[:i] + r[i + 1:] for r in rows]
        if (cols, rows) != (new[name]["columns"], new[name]["rows"]):
            bad["tables"].append((name, "differs"))
    kept = json.loads((ROOT / "results/per_unit/loss_per_unit.json").read_text())
    for name in PU_TABLES:
        if name in old and kept.get(name, {}).get("rows") != old[name]["rows"]:
            bad["per_unit"].append((name, "computation changed"))
    for name in PU_TABLES:
        if (ROOT / "paper" / "tables" / f"{name}.tex").exists() or (ROOT / "paper_pack" / "tables" / f"{name}.tex").exists():
            bad["tex"].append((name, "table still in paper/ or the pack"))
    for tex in sorted((ROOT / "paper" / "tables").glob("*.tex")):
        if tex.stem in ("main", "e5"):
            continue                                     # compared cell by cell through tables.json above
        if Counter(NUM.findall(_old(tag, f"paper/tables/{tex.name}"))) != Counter(NUM.findall(tex.read_text())):
            bad["tex"].append((tex.name, "numbers differ"))
    newrows = defaultdict(list)
    for r in _rows((ROOT / "paper" / "NUMBERS.md").read_text()):
        newrows[r[4]].append(r)
    oldrows = _rows(_old(tag, "paper/NUMBERS.md"))
    for r in oldrows:
        if "loss_per_unit" in r[4]:
            if r[4] in newrows:
                bad["numbers"].append(("per-unit row still present", r[0]))
            continue
        if not any((c[1], c[2], c[3]) == (r[1], r[2], r[3]) for c in newrows.get(r[4], [])):
            bad["numbers"].append(("changed", r[0], r[1]))
    added = [r[0] for rs in newrows.values() for r in rs
             if not any((o[0], o[1]) == (r[0], r[1]) for o in oldrows)]
    if sorted(added) != sorted(NEW_ROWS):
        bad["numbers"].append(("unexpected new rows", added))
    for f in sorted((ROOT / "results").glob("*/*.csv")):
        rel = str(f.relative_to(ROOT))
        if _old(tag, rel) != f.read_text():
            bad["csvs"].append((rel, "differs"))
    from openpyxl import load_workbook
    ow = load_workbook(io.BytesIO(_old(tag, "paper_pack/results_all.xlsx", binary=True)))
    nw = load_workbook(ROOT / "paper_pack" / "results_all.xlsx")
    if "loss per unit" in nw.sheetnames:
        bad["workbook"].append(("loss per unit", "sheet still present"))
    for ws in ow.worksheets:
        if ws.title in ("README", "E2", "E5", "loss per unit"):
            continue                                     # E2/E5: through tables.json; README lists columns
        if [list(r) for r in ws.iter_rows(values_only=True)] != [list(r) for r in nw[ws.title].iter_rows(values_only=True)]:
            bad["workbook"].append((ws.title, "cells differ"))
    return bad


# ------------------------------------------------------------------ v1.5: E8 added, nothing else may change

def check_additive(tag: str, new_tables=("e8", "e8_strategies"), new_sheets=("E8",), marker="e8[",
                   new_csvs=()) -> dict:
    """Against `tag`: every table, .tex, NUMBERS.md row, per-eval CSV and workbook sheet that existed is identical;
    the only additions are the listed new tables, sheets and NUMBERS rows (sources containing `marker`)."""
    bad: dict = {k: [] for k in ("tables", "tex", "numbers", "csvs", "workbook")}
    old, new = json.loads(_old(tag, "results/tables.json")), json.loads((ROOT / "results/tables.json").read_text())
    for name, t in old.items():
        if name not in new or (t["columns"], t["rows"]) != (new[name]["columns"], new[name]["rows"]):
            bad["tables"].append((name, "missing or differs"))
    extra = sorted(set(new) - set(old) - set(new_tables))
    if extra:
        bad["tables"].append(("unexpected new tables", extra))
    for tex in sorted((ROOT / "paper" / "tables").glob("*.tex")):
        if tex.stem in new_tables:
            continue
        try:
            o = _old(tag, f"paper/tables/{tex.name}")
        except subprocess.CalledProcessError:
            bad["tex"].append((tex.name, "not in base"))
            continue
        if Counter(NUM.findall(o)) != Counter(NUM.findall(tex.read_text())):
            bad["tex"].append((tex.name, "numbers differ"))
    newrows = defaultdict(list)
    for r in _rows((ROOT / "paper" / "NUMBERS.md").read_text()):
        newrows[r[4]].append(r)
    oldrows = _rows(_old(tag, "paper/NUMBERS.md"))
    for r in oldrows:
        if not any((c[1], c[2], c[3]) == (r[1], r[2], r[3]) for c in newrows.get(r[4], [])):
            bad["numbers"].append(("changed or missing", r[0], r[1]))
    oldkeys = {(o[0], o[1], o[4]) for o in oldrows}
    for rs in newrows.values():
        for r in rs:
            if (r[0], r[1], r[4]) not in oldkeys and marker not in r[4]:
                bad["numbers"].append(("unexpected new row", r[0]))
    for f in sorted((ROOT / "results").glob("*/*.csv")):
        rel = str(f.relative_to(ROOT))
        if rel.startswith(("results/e8/", "results/e9/", *new_csvs)):
            continue
        try:
            if _old(tag, rel) != f.read_text():
                bad["csvs"].append((rel, "differs"))
        except subprocess.CalledProcessError:
            bad["csvs"].append((rel, "not in base"))
    from openpyxl import load_workbook
    ow = load_workbook(io.BytesIO(_old(tag, "paper_pack/results_all.xlsx", binary=True)))
    nw = load_workbook(ROOT / "paper_pack" / "results_all.xlsx")
    for ws in ow.worksheets:
        if ws.title == "README":
            continue
        if ws.title not in nw.sheetnames or [list(r) for r in ws.iter_rows(values_only=True)] != \
                [list(r) for r in nw[ws.title].iter_rows(values_only=True)]:
            bad["workbook"].append((ws.title, "missing or differs"))
    extra = sorted(set(nw.sheetnames) - set(ow.sheetnames) - set(new_sheets))
    if extra:
        bad["workbook"].append(("unexpected new sheets", extra))
    return bad


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    if "--additive" in argv:
        tag = [a for a in argv if not a.startswith("--")][0]
        opt = lambda k, d: next((a.split("=", 1)[1] for a in argv if a.startswith(f"--{k}=")), d)  # noqa: E731
        report = check_additive(tag, new_tables=tuple(opt("tables", "e8,e8_strategies").split(",")),
                                new_sheets=tuple(x for x in opt("sheets", "E8").split(",") if x),
                                marker=opt("marker", "e8["),
                                new_csvs=tuple(x for x in opt("csvs", "").split(",") if x))
        for k, v in report.items():
            print(f"{k}: {'identical' if not v else f'{len(v)} DIFFERENCES'}")
            for d in v:
                print("   ", d)
        if any(report.values()):
            print(f"STOP: prior numbers differ from {tag}")
            sys.exit(1)
        print(f"OK: every prior number is identical to {tag}; the only additions are the listed new tables, rows "
              "and sheets")
        return
    if "--drop-per-unit" in argv:
        tag = [a for a in argv if not a.startswith("--")][0]
        report = check_drop_per_unit(tag)
        for k, v in report.items():
            print(f"{k}: {'as expected' if not v else f'{len(v)} DIFFERENCES'}")
            for d in v:
                print("   ", d)
        if any(report.values()):
            print(f"STOP: differences against {tag}")
            sys.exit(1)
        print(f"OK against {tag}: the per-unit metric is off every paper output and unchanged in results/per_unit/; "
              "the two derived RQ1 rows are the only new numbers; everything else is identical")
        return
    tag = (argv or ["v1.3-paper-pack"])[0]
    report = {"tables": check_tables(tag), "numbers": check_numbers(tag), "csvs": check_csvs(tag),
              "workbook": check_workbook(tag), "trace": check_trace()}
    for k, v in report.items():
        print(f"{k}: {'identical / traced' if not v else f'{len(v)} DIFFERENCES'}")
        for d in v:
            print("   ", d)
    if any(report.values()):
        print(f"STOP: differences against {tag}")
        sys.exit(1)
    print(f"OK: every number not depending on the new seeds or the new metric is identical to {tag}; "
          "every new number traces to results/per_unit/runs.csv")


if __name__ == "__main__":
    main(sys.argv[1:])
