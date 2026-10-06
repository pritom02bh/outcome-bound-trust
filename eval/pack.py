"""Paper pack: paper_pack/ and paper_pack_<VERSION>.zip, from results/, paper/, docs/ and spec/results/ only.

    python -m eval.pack          # build, verify, zip; exits non-zero if any number in the workbook disagrees

Nothing is simulated and no run record is read: every table is copied from results/tables.json (the same cells
as paper/tables/*.tex), every per-eval block from a results/ CSV, and the TLA+ sheet from spec/results/. The
verification checks the workbook against paper/tables/*.tex, paper/NUMBERS.md and each source CSV.
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "paper_pack"
VERSION = "v1.9.2"               # the release this pack belongs to
TAG = "v1.9.2-paper"
ZIP = ROOT / f"paper_pack_{VERSION}.zip"
TJ = "results/tables.json"
NUMERIC = re.compile(r"^-?[\d,]*\d(\.\d+)?$")
TOKEN = re.compile(r"(?<![A-Za-z0-9.])-?\d[\d,]*(?:\.\d+)?(?![A-Za-z\d])")

# Meaning of every column the workbook uses (README sheet).
COLUMNS = {
    "defense": "defense (OBT variants, reputation variants, baselines)", "seeds": "seeds in the mean",
    "loss from lies": "mean over attack scenarios 2-12 of cost − cost of the honest run (same defense, seed), $ per run; "
                      "[95% bootstrap CI over seeds] where shown",
    "utility cost": "cost(defense) − cost(none) on the honest scenario, same seed, $ per run",
    "utility (% of cost)": "utility cost as a % of the honest run's total cost without a defense",
    "S_main share": "share of executed order units bought from S_main, honest scenario",
    "damage": "cost against the same decisions with every relied-on promise kept (DESIGN §6), $",
    "reroute premium": "backup premium on quantity rerouted after the defense's own blocks, differenced vs the honest "
                       "run, $ per run", "resid": "loss from lies − damage − reroute premium, $ per run",
    "sum of bounds": "sum of per-event bounds Σ L_e, $", "max damage/bound": "largest per-run damage / Σ L_e",
    "failure events": "FAILED claims with consumed units", "runs": "runs (or attacker evaluations)",
    "held": "damage ≤ Σ L_e in every run", "config": "config: E1, OBT b0 fraction, window W, grace δ; E9 calibration, grid point and its settings",
    "default": "the chosen default (D22 rule)", "k": "budget growth multiplier (D36)", "rounds": "game length T",
    "max damage/a-priori": "largest damage / k-scaled a-priori bound",
    "extractor": "extraction model (frozen prompt) or rule baseline", "precision": "test set (199), template + slots",
    "recall": "test set (199), template + slots", "exact": "share of items with exactly the gold claims",
    "hard: LLM alone": "hard subset (30): shipping/ready dates wrongly recorded as deadlines, no code guard",
    "hard: with guard": "hard subset (30): the same with the code deadline guard",
    "stratum": "Enron sample stratum", "commitments": "rows labeled is_commitment = yes",
    "claims UNTESTABLE": "labeled commitment claims not recorded (schema coverage limit)",
    "recorded": "claims recorded (PENDING)", "wrong recorded": "recorded claims matching no label (target 0)",
    "from non-commitments": "claims recorded from rows labeled no", "attacker": "E6 attacker picked by ratio or damage",
    "damage / bound": "damage / Σ L_e, worst of 3 seeds", "n0": "reputation probation length",
    "theta": "reputation threshold", "cap": "reputation order-value cap, $", "locks out": "never trades after a lock-out",
    "never trades": "never trades with an honest S_main", "chosen": "the config chosen by the selection rule (D33 reputation grid; D45 E9 calibration)",
    "run": "E3 or E3b", "attack runs": "attack runs in the mean", "buyer": "paid buyer model (E5 v2)",
    "scenario": "scenario (1 honest ... 12 sybil re-entry)",
    "mutant": "guard removed in the spec (none = unmutated)", "verdict": "TLC result: PASS, CAUGHT(property) or N/A",
    "violation": "property TLC reported violated", "distinct_states": "distinct states when TLC stopped",
    "depth": "search depth (PASS) or counterexample length (CAUGHT)",
    "runtime_s": "wall-clock seconds (B: not reported, host sleep)",
    "loss per 100 S_main units": "100 x loss from lies / units bought from S_main in the attack runs (D40), "
                                 "$ per 100 units; mean [95% CI over seeds] where shown",
    "S_main units per attack run": "mean units bought from S_main per attack run (D40)",
    "S_main share (attack runs)": "S_main units / all executed order units, attack runs (D40)",
    "eval": "experiment the row comes from", "seed": "seed", "loss_from_lies": "cost − cost of the honest run, $",
    "s_main_units": "units bought from S_main in the run", "all_units": "all executed order units in the run",
    "knowledge": "E8 attacker knowledge: black-box or white-box (D43)",
    "attacker profit": "payments received by the attacker − $3 × units it delivered, $ per run",
    "farm then defect": "identities that shipped in full at least twice before a short order",
    "claim splitting": "rounds whose message names two or more quantities", "injection or decoy":
    "rounds whose message addresses the buyer's software or quotes two or more prices",
    "provider share": "share of reserved capacity units bought from the main provider, honest scenario (E9)",
    "events": "failure-event type (QUOTA, SLA, all)", "runs with events": "OBT runs with at least one event",
    "setting": "E9 config source: transferred from the supply domain (D44) or calibrated on the cloud domain (D45)",
    "group": "simulation, runs or data", "item": "what the row describes",
    "value": "the count or setting, as computed from the source", "source": "file (and key) the value is read from",
    "set": "label set compared (D42a)", "raw agreement": "share of rows with the same label",
    "kappa": "Cohen's kappa (None when undefined)", "kappa degenerate": "one side gives every row the same label",
    "detection rate": "seeded errors the annotator marked no", "disagreements": "rows labeled differently",
    "slot": "Enron slot column", "agree": "rows where both give the same slot value",
    "point": "E9 calibration grid point", "b0": "OBT b0 as a fraction of expected per-round spend",
    "new in D45a": "grid point added by the D45a extension", "pick moved": "the rule's OBT pick differs from D45's",
    "pick on grid edge": "edges of the extended grid the OBT pick sits on (b0/k min or max)", "front": "on the defense's Pareto front (never-trading points excluded)",
    "transferred": "the config E9 ran with (D44)", "OBT runs": "OBT grid runs checked",
    "invariant violations": "invariant violations over every grid run (target 0)",
    "transferred points reproduce E9": "the transferred grid points' costs equal E9's runs exactly",
    "identity resets": "switches to a new identity", "invoice overpricing":
    "orders invoiced above the price the round's message stated ($5.00 if none)",
}


def _num(v):
    """A cell as Excel should hold it: plain numbers become numbers; everything else stays text as printed."""
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if NUMERIC.match(s):
        s = s.replace(",", "")
        return int(s) if "." not in s else float(s)
    return s


def _dec(tok: str):
    try:
        return Decimal(str(tok).replace(",", "")).normalize()
    except InvalidOperation:
        return None


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ------------------------------------------------------------------ blocks: (title, source, columns, rows)

def _tables() -> dict:
    return json.loads((ROOT / TJ).read_text())


def tblock(name: str, keep=lambda d: True) -> tuple:
    t = _tables()[name]
    rows = [r for r in t["rows"] if keep(dict(zip(t["columns"], r)))]
    return (t["caption"], f"{TJ} → {name}", t["columns"], rows)


def cblock(path: str) -> tuple:
    rows = list(csv.reader((ROOT / path).open()))
    return (Path(path).name, path, rows[0], rows[1:])


def _tlc_rows(text: str) -> list[list]:
    rows = []
    for line in text.splitlines():
        if line.startswith("#") or line.startswith("mutant ") or not line.strip():
            continue
        t = line.split()
        if len(t) >= 6 and all(re.match(r"^\d+$|^\?$", x) for x in t[-3:]):
            rows.append([t[0], t[1], " ".join(t[2:-3]), t[-3], t[-2], t[-1]])
        else:
            rows.append([t[0], t[1], " ".join(t[2:]), "-", "-", "-"])
    return rows


def tlc_block(name: str, label: str) -> tuple:
    path = f"spec/results/{name}_summary.txt"
    text = (ROOT / path).read_text()
    bounds = " ".join(re.search(r"^# bounds: (.*)$", text, re.M).group(1).split())
    rows = _tlc_rows(text)
    if name == "fallbackB":                        # cited by states only: its wall-clock time included host sleep
        rows = [r[:5] + ["-"] for r in rows]
    return (f"TLA+ k = 1, {label}: {bounds}", path,
            ["mutant", "verdict", "violation", "distinct_states", "depth", "runtime_s"], rows)


def coverage_block() -> tuple:
    path = "spec/results/k_coverage.txt"
    lines = (ROOT / path).read_text().splitlines()
    cfgs = [c.strip() for c in lines[0].split(":", 1)[1].split("|")]
    rows = []
    for l in lines[1:]:
        if l.startswith("RESULT"):
            rows.append(["RESULT", l.split(":", 1)[1].strip()] + [""] * len(cfgs))
            continue
        m, ok, rest = l.split(None, 2)
        rows.append([m, ok] + [c.strip() for c in rest.split("|")])
    return ("TLA+ k = 1 mutant coverage (every mutant caught in ≥ 1 config)", path, ["mutant", "covered", *cfgs], rows)


def sheets() -> list[tuple[str, list[tuple]]]:
    csvs = lambda d: [cblock(f"results/{d}/{f}") for f in ("loss_from_lies.csv", "loss_bound.csv", "utility.csv")  # noqa: E731
                      if (ROOT / "results" / d / f).exists()]
    pareto = json.loads((ROOT / "results/figdata/pareto.json").read_text())
    grid = ("E1 grid: every OBT config and none (scripted buyer)", "results/figdata/pareto.json → obt, none",
            ["config", "utility cost", "loss from lies", "on the front"],
            [[p["name"], p["utility_cost"], p["attack_loss"], "yes" if p["front"] else ""] for p in pareto["obt"]]
            + [["none", pareto["none"]["utility_cost"], pareto["none"]["attack_loss"], ""]])
    return [
        ("E1", [tblock("e1_obt_front"), grid]),
        ("E2", [tblock("main"), tblock("loss_by_scenario"), tblock("damage_vs_bound"), *csvs("e2")]),
        ("E2b", csvs("e2b")),
        ("E2c", csvs("e2c")),
        ("E3", [tblock("second_model", lambda d: d["run"] == "E3"), *csvs("e3")]),
        ("E3b", [tblock("second_model", lambda d: d["run"] == "E3b"), *csvs("e3b")]),
        ("E4", [tblock("extractor")]),
        ("E5", [tblock("e5"), *csvs("e5__luna"), *csvs("e5__terra")]),
        ("E6", [tblock("e6"), tblock("bound_tightness")]),
        ("E7", [tblock("budget_k")]),
        ("horizon", [tblock("horizon"), *csvs("horizon__t100__none"), *csvs("horizon__t100__obt"),
                     *csvs("horizon__t100__rep-n18")]),
        ("reputation grid", [tblock("reputation_grid")]),
        ("Enron", [tblock("enron")]),
        *([("Simulation at a glance", [tblock("sim_glance")])] if "sim_glance" in _tables() else []),
        *([("Annotator agreement", [tblock("annotator_agreement"), tblock("annotator_slots")])]
          if "annotator_agreement" in _tables() else []),
        *([("E8", [tblock("e8"), tblock("e8_strategies"), cblock("results/e8/runs.csv")])] if "e8" in _tables() else []),
        *([("E9", [tblock("e9"), tblock("e9_damage_vs_bound")])] if "e9" in _tables() else []),
        *([("E9 calibration", [tblock("e9_calibration"), tblock("e9_calibration_bound"),
                                tblock("e9_calibration_grid")])] if "e9_calibration" in _tables() else []),
        *([("E9 calibration ext", [tblock("e9_calibration_ext"), tblock("e9_calibration_ext_bound"),
                                    tblock("e9_calibration_ext_grid")])] if "e9_calibration_ext" in _tables() else []),
        ("TLA+ verification", [tlc_block("quick", "quick"), tlc_block("fallbackA2", "A′"), tlc_block("fallbackB", "B"),
                               tlc_block("quick_b01", "quick, B0 = 1"), tlc_block("fallbackA2_b01", "A′, B0 = 1"),
                               coverage_block()]),
    ]


# ------------------------------------------------------------------ workbook

def workbook(path: Path, sh: list) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    readme = wb.active
    readme.title = "README"
    readme.append([f"Outcome-Bound Trust: all results (tag {TAG}). Built from results/ and spec/results/ "
                   "only by `python -m eval.pack`; numbers are as printed in the paper tables and NUMBERS.md."])
    readme.append([])
    readme.append(["sheet", "block", "source (file → key)", "column", "meaning"])
    for c in readme[3]:
        c.font = Font(bold=True)
    for name, blocks in sh:
        ws = wb.create_sheet(name[:31])
        for title, source, cols, rows in blocks:
            ws.append([title])
            ws.cell(ws.max_row, 1).font = Font(bold=True)
            ws.append([f"source: {source}"])
            ws.append(list(cols))
            for c in ws[ws.max_row]:
                c.font = Font(bold=True)
            for r in rows:
                ws.append([_num(v) for v in r])
            ws.append([])
            for col in cols:
                readme.append([name, title[:80], source, col, COLUMNS.get(col, COLUMNS.get(col.split("|")[0], "as in the source file"))])
    fixed = datetime(2026, 10, 1)
    wb.properties.created = wb.properties.modified = fixed
    wb.save(path)


# ------------------------------------------------------------------ verification

def _tex_rows(tex: str) -> list[list[str]]:
    body = tex.split("\\midrule", 1)[1].split("\\bottomrule", 1)[0]
    unesc = lambda s: re.sub(r"\\([&%$#_{}])", r"\1", s).strip()  # noqa: E731
    return [[unesc(c) for c in line.rstrip().rstrip("\\").split(" & ")] for line in body.strip().splitlines()]


def _same(a, b) -> bool:
    x, y = _num(a), _num(b)
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return Decimal(str(x)) == Decimal(str(y))
    return str(x) == str(y)


def verify(xlsx: Path, sh: list) -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(xlsx)
    bad: list = []
    n_cells = 0
    tables = _tables()
    # 1. Every block equals its source; blocks from tables.json also equal paper/tables/<name>.tex.
    for name, blocks in sh:
        ws = list(wb[name[:31]].iter_rows(values_only=True))
        i = 0
        for title, source, cols, rows in blocks:
            while not (ws[i] and ws[i][0] == title and ws[i + 1][0] == f"source: {source}"):
                i += 1
            got = [list(r[:len(cols)]) for r in ws[i + 3:i + 3 + len(rows)]]
            for r_src, r_x in zip(rows, got):
                for a, b in zip(r_src, r_x):
                    n_cells += 1
                    if not _same(a, "" if b is None else b):
                        bad.append((name, source, a, b))
            if len(got) != len(rows):
                bad.append((name, source, "row count", len(rows), len(got)))
            i += 3 + len(rows)
            if source.startswith(TJ):
                tname = source.split("→ ")[1]
                tex = _tex_rows((ROOT / "paper" / "tables" / f"{tname}.tex").read_text())
                for r_json, r_tex in zip(tables[tname]["rows"], tex):
                    if len(r_json) != len(r_tex) or not all(_same(a, b) for a, b in zip(r_json, r_tex)):
                        bad.append(("tex", tname, r_json, r_tex))
                if len(tables[tname]["rows"]) != len(tex):
                    bad.append(("tex", tname, "row count"))
    # 2. Every number NUMBERS.md cites (except derived percentages and the figure pointer) is in the workbook.
    have = {_dec(t) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for v in row
            if v is not None for t in (TOKEN.findall(v) if isinstance(v, str) else [str(v)])}
    # A cited number with d decimals also matches a workbook number that rounds to it at d decimals: the workbook
    # keeps full precision where its source does (e.g. the E1 grid), and the paper prints it rounded.
    raw = [x for x in have if x is not None]
    cited, by_rounding = 0, []

    def found(tok: str) -> bool:
        d = _dec(tok)
        if d in have:
            return True
        q = Decimal(1).scaleb(d.as_tuple().exponent) if d.as_tuple().exponent < 0 else Decimal(1)
        hit = next((x for x in raw if x.quantize(q) == d.quantize(q)), None)
        if hit is not None:
            by_rounding.append((tok, str(hit)))
        return hit is not None
    for line in (ROOT / "paper" / "NUMBERS.md").read_text().splitlines():
        if not line.startswith("| ") or line.startswith("| claim"):
            continue
        claim, value = [c.strip() for c in line.strip("|").split(" | ")][:2]
        if "(derived)" in claim or value in ("figure",) or value.startswith("not model-checked"):
            continue
        for tok in TOKEN.findall(value):
            cited += 1
            if not found(tok):
                bad.append(("NUMBERS.md", claim, tok))
    return {"cells_checked": n_cells, "numbers_md_values_checked": cited,
            "numbers_md_matched_by_rounding": by_rounding, "mismatches": bad}


# ------------------------------------------------------------------ build

def _decisions_summary() -> str:
    L = ["# DECISIONS: one line per entry", "", "Summary of `docs/DECISIONS.md` (the full file has the reasoning).", ""]
    for line in (ROOT / "docs" / "DECISIONS.md").read_text().splitlines():
        m = re.match(r"^#{2,3} (D\d+[a-z]?)\.\s*(.*)$", line)
        if m:
            L.append(f"- **{m.group(1)}**: {m.group(2)}")
    return "\n".join(L) + "\n"


def build() -> dict:
    if PACK.exists():
        shutil.rmtree(PACK)
    (PACK / "tables").mkdir(parents=True)
    (PACK / "figures").mkdir()
    (PACK / "spec" / "results").mkdir(parents=True)
    shutil.copy(ROOT / "paper" / "NUMBERS.md", PACK / "NUMBERS.md")
    shutil.copy(ROOT / "results" / "INDEX.md", PACK / "INDEX.md")
    for md in ("walkthrough.md", "walkthrough_appendix.md"):
        if (ROOT / "paper" / md).exists():
            shutil.copy(ROOT / "paper" / md, PACK / md)
    shutil.copy(ROOT / "docs" / "DESIGN.md", PACK / "DESIGN.md")
    shutil.copy(ROOT / "spec" / "results" / "README.md", PACK / "spec" / "results" / "README.md")
    (PACK / "DECISIONS_SUMMARY.md").write_text(_decisions_summary())
    tables = _tables()
    for tex in sorted((ROOT / "paper" / "tables").glob("*.tex")):
        shutil.copy(tex, PACK / "tables" / tex.name)
        t = tables[tex.stem]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(t["columns"])
        w.writerows(t["rows"])
        (PACK / "tables" / f"{tex.stem}.csv").write_text(buf.getvalue())
    for pdf in sorted((ROOT / "paper" / "figures").glob("*.pdf")):
        shutil.copy(pdf, PACK / "figures" / pdf.name)
        # PNG preview (macOS Quick Look renders the vector PDF at 1600 px).
        subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", str(PACK / "figures"), str(pdf)],
                       capture_output=True, check=True)
        (PACK / "figures" / f"{pdf.name}.png").rename(PACK / "figures" / f"{pdf.stem}.png")
    sh = sheets()
    xlsx = PACK / "results_all.xlsx"
    workbook(xlsx, sh)
    rep = verify(xlsx, sh)
    if rep["mismatches"]:
        return rep
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(p for p in PACK.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(str(f.relative_to(ROOT)), date_time=(2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    rep["files"] = sorted(_rel(p) for p in PACK.rglob("*") if p.is_file())
    return rep


def main() -> None:
    rep = build()
    print(json.dumps({k: v for k, v in rep.items() if k != "files"}, indent=1, default=str)[:4000])
    if rep["mismatches"]:
        print("STOP: the workbook disagrees with its sources; no zip written")
        sys.exit(1)
    print(f"{len(rep['files'])} files in {PACK.name}/; {ZIP.name} written")


if __name__ == "__main__":
    main()
