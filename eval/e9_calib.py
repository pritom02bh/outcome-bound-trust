"""E9 calibration (DECISIONS D45): the cloud domain's own OBT and reputation configs, chosen by E1's rule.

    python -m eval.e9_calib run     # every grid point into runs/e9_calib/<point>/ (resumable); STOP on any violation

Grids (scripted buyer and providers, structured intents, in-process, no model calls; all 7 E9 scenarios, seeds 1-3,
50 rounds):
  - OBT: b0 ∈ {2.5%, 5%, 10%, 20%} of expected per-round spend × k ∈ {1, 2}; W 0, δ 0 (8 points).
  - Reputation: the D33 grid, n0 ∈ {3, 8, 18} × θ ∈ {0.8, 0.85, 0.9} × cap ∈ {$100, $200, $400} (27 points).
The utility reference is E9's own `none` runs (runs/e9).

Rule (fixed in E1, D22 `eval.e1.pick_default`, with D33's exclusion; both written before any E9 data): per defense,
drop never-trading points (0 main-provider orders executed in every honest run), take the Pareto front in
(utility cost, attack loss), and pick the front point with the smallest utility cost + attack loss (ties by name).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from eval.e1 import pareto_front, pick_default
from eval.e9 import Violation
from eval.e9 import load as load_rows
from eval.run import git_state
from obt.env.beer_game import GameConfig
from obt.env.cloud import CapacityBuyer, StructuredExtractor, cloud_scenario_name, make_cloud_supplier
from obt.llm import RUNS
from obt.sim import Sim, SimConfig

ROOT = RUNS / "e9_calib"
SCENARIOS = tuple(range(1, 8))
SEEDS = (1, 2, 3)
B0 = (0.025, 0.05, 0.10, 0.20)
KS = (1, 2)
# D45a extension (user request after v1.7, whose pick sat on the b0 edge): b0 ∈ {40%, 80%} × k ∈ {1, 2, 4}, plus k = 4
# at every original b0. The extended OBT grid is the full product B0_EXT x KS_EXT (18 points). Same rule, scenarios, seeds.
B0_EXT = B0 + (0.40, 0.80)
KS_EXT = KS + (4,)
N0 = (3, 8, 18)
THETAS = (0.8, 0.85, 0.9)
CAPS = (100.0, 200.0, 400.0)
BASE = {"window": 0, "grace": 0}
# The configs E9 ran with (transferred from the supply domain, D44): their grid points reproduce runs/e9 exactly.
TRANSFERRED = {"obt": "obt_b0.05_k1", "rep-strict": "rep_n3_th0.9_cap200"}


def grid(ext: bool = False) -> list[tuple[str, str, dict]]:
    b0s, ks = (B0_EXT, KS_EXT) if ext else (B0, KS)
    g = [(f"obt_b{b}_k{k}", "obt", {"b0_frac": b, "budget_k": k, **BASE}) for b in b0s for k in ks]
    g += [(f"rep_n{n0}_th{t}_cap{int(c)}", "reputation", {"b0_frac": 0.05, **BASE, "rep_n0": n0, "rep_theta": t,
                                                           "rep_cap": c})
          for n0 in N0 for t in THETAS for c in CAPS]
    return g


def run_one(name: str, defense: str, sim: dict, n: int, seed: int, rounds: int = 50) -> dict:
    cfg = SimConfig(game=GameConfig(rounds=rounds), defense=defense, transport="inproc", domain="cloud", **sim)
    t0 = time.time()
    res = Sim(cfg, seed, make_cloud_supplier(n, cfg.game, seed), CapacityBuyer(cfg.game),
              extractor=StructuredExtractor(), scenario=cloud_scenario_name(n)).run()
    commit, dirty = git_state()
    return {"scenario": n, "name": cloud_scenario_name(n), "point": name, "defense": defense, "seed": seed,
            "domain": "cloud", "buyer": "scripted", "total_cost": res.total_cost, "costs": res.costs,
            "metrics": res.metrics, "trace": res.trace, "rounds": rounds, "wall_s": round(time.time() - t0, 3),
            "meta": {"git_commit": commit, "git_dirty": dirty, "domain": "cloud", "sim": sim, "transport": "inproc",
                     "extractor": "structured"}}


def run(root: Path = ROOT, points=None, scenarios=SCENARIOS, seeds=SEEDS, rounds: int = 50) -> None:
    for i, (name, defense, sim) in enumerate(points or grid(), 1):
        out = root / name
        out.mkdir(parents=True, exist_ok=True)
        done = {(r["scenario"], r["seed"]) for r in load_rows(out)}
        for s in seeds:
            for n in scenarios:
                if (n, s) in done:
                    continue
                r = run_one(name, defense, sim, n, s, rounds)
                with (out / "results.jsonl").open("a") as f:
                    f.write(json.dumps(r, default=str) + "\n")
                lb = r["metrics"]["loss_bound"]
                if r["metrics"]["invariant_violations"]["count"] or lb["ok"] is False:
                    raise Violation(f"STOP: violation in {name} {r['name']} s{s} (damage {lb['damage']}, "
                                    f"bound {lb['sum_bound']})")
        print(f"== E9 calibration {i}/{len(points or grid())}: {name} done", flush=True)


# ------------------------------------------------------------------ summary (results build)

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def point_stats(rs: list[dict], none: dict) -> dict:
    cost = {(r["scenario"], r["seed"]): r["total_cost"] for r in rs}
    seeds = sorted({s for _, s in cost})
    honest = [r for r in rs if r["scenario"] == 1]
    obt = [r for r in rs if r["defense"] == "obt"]
    ratios = [r["metrics"]["loss_bound"]["damage"] / r["metrics"]["loss_bound"]["sum_bound"] for r in obt
              if r["metrics"]["loss_bound"]["events"] and r["metrics"]["loss_bound"]["sum_bound"]]
    return {"runs": len(rs),
            "attack_loss": _mean([cost[(n, s)] - cost[(1, s)] for (n, s) in cost if n != 1 and (1, s) in cost]),
            "utility_cost": _mean([cost[(1, s)] - none[(1, s)] for s in seeds if (1, s) in cost and (1, s) in none]),
            "never_trades": bool(honest) and all(r["metrics"]["main_orders_executed"] == 0 for r in honest),
            "locked": sum(r["metrics"]["blocked_by_reason"].get("REP_SCORE", 0) for r in honest) > 0,
            "invariant_violations": sum(r["metrics"]["invariant_violations"]["count"] for r in rs),
            "failure_events": sum(len(r["metrics"]["loss_bound"]["events"]) for r in obt),
            "max_ratio": max(ratios) if ratios else None,
            "bound_held": all(r["metrics"]["loss_bound"]["ok"] is not False for r in obt)}


def choose(points: dict, defense: str) -> tuple[list[str], str | None]:
    """E1's rule (D22 pick_default) over the non-degenerate points of one defense (D33: drop never-trading)."""
    ok = {k: (v["utility_cost"], v["attack_loss"]) for k, v in points.items()
          if v["defense"] == defense and not v["never_trades"] and v["utility_cost"] is not None
          and v["attack_loss"] is not None}
    return (pareto_front(ok), pick_default(ok)) if ok else ([], None)


def summarize(root: Path = ROOT, e9_dir: Path = RUNS / "e9", ext: bool = False) -> dict:
    none = {(r["scenario"], r["seed"]): r["total_cost"] for r in load_rows(e9_dir) if r["defense"] == "none"}
    points, rows = {}, {}
    for name, defense, sim in grid(ext):
        rs = load_rows(root / name)
        if not rs:
            continue
        rows[name] = rs
        points[name] = {"defense": defense, **sim, **point_stats(rs, none)}
    out = {"points": points, "fronts": {}, "picks": {}, "transferred": TRANSFERRED}
    for label, defense in (("obt", "obt"), ("rep-strict", "reputation")):
        out["fronts"][label], out["picks"][label] = choose(points, defense)
    # The transferred grid points must reproduce E9's own runs (same configs, deterministic): a check on the harness.
    e9 = load_rows(e9_dir)
    out["reproduces_e9"] = {
        d: sorted((r["scenario"], r["seed"], r["total_cost"]) for r in e9 if r["defense"] == d)
        == sorted((r["scenario"], r["seed"], r["total_cost"]) for r in rows.get(p, []))
        for d, p in TRANSFERRED.items()}
    # Whether OBT's pick sits on an edge of the grid it was chosen from (D45a: reported, not extended further).
    pk = points.get(out["picks"]["obt"]) if out["picks"]["obt"] else None
    b0s, ks = (B0_EXT, KS_EXT) if ext else (B0, KS)
    out["obt_pick_edges"] = [] if pk is None else \
        [e for e, hit in (("b0 max", pk["b0_frac"] == max(b0s)), ("b0 min", pk["b0_frac"] == min(b0s)),
                          ("k max", pk["budget_k"] == max(ks)), ("k min", pk["budget_k"] == min(ks))) if hit]
    return out


def calibrated_rows(root: Path = ROOT, e9_dir: Path = RUNS / "e9", ext: bool = False) -> list[dict]:
    """E9's none plus each defense's calibrated point, relabeled as that defense (for eval.e9.summary)."""
    s = summarize(root, e9_dir, ext)
    rows = [r for r in load_rows(e9_dir) if r["defense"] == "none"]
    for label, p in s["picks"].items():
        if p:
            rows += [{**r, "defense": label} for r in load_rows(root / p)]
    return rows


OUT_START, OUT_END = "<!-- D45 outcome (generated) -->", "<!-- /D45 outcome -->"


def release_notes(root: Path = RUNS.parent) -> None:
    """INDEX.md E9-calibration row and DECISIONS D45's outcome, from results/tables.json (idempotent)."""
    import re
    t = json.loads((root / "results" / "tables.json").read_text())
    side = {(r[0], r[1]): dict(zip(t["e9_calibration"]["columns"], r)) for r in t["e9_calibration"]["rows"]}
    b = dict(zip(t["e9_calibration_bound"]["columns"], t["e9_calibration_bound"]["rows"][0]))
    g = t["e9_calibration_grid"]
    front = lambda d: ", ".join(r[1] for r in g["rows"] if r[0] == d and r[6] == "yes")  # noqa: E731
    commits = sorted({r["meta"]["git_commit"][:7] for p in (root / "runs" / "e9_calib").iterdir() if p.is_dir()
                      for r in load_rows(p)})
    o, c = side[("obt", "calibrated")], side[("rep-strict", "calibrated")]
    line = (f"| **E9 calibration** (D45) | scripted; OBT b0 × k (8 points), reputation D33 grid (27 points) × 7 "
            f"scenarios × seeds 1-3; E1's rule | {', '.join(f'`{x}`' for x in commits)} | `results/e9/calibration.md` "
            f"(`v1.7-results`) | calibrated OBT {o['config']}: loss **{o['loss from lies']}**, utility "
            f"{o['utility (% of cost)']}%; rep-strict {c['config']}: loss {c['loss from lies']}, utility "
            f"{c['utility (% of cost)']}%; bound held {b['held']} (max {b['max damage/bound']}) |")
    f = root / "results" / "INDEX.md"
    s = f.read_text()
    s = re.sub(r"^\| \*\*E9 calibration\*\* .*\n", "", s, flags=re.M)
    anchor = re.search(r"^\| \*\*E9\*\* .*$", s, flags=re.M)
    s = s[:anchor.end()] + "\n" + line + s[anchor.end():]
    s = re.sub(r"^# Results index \(tags .*\)$", lambda m: m.group(0)[:-1] + ", `v1.7-results`: + E9 calibration)"
               if "v1.7" not in m.group(0) else m.group(0), s, count=1, flags=re.M)
    f.write_text(s)
    L = [OUT_START, "- **Outcome** (generated by `python -m eval.e9_calib notes`):"]
    for d in ("obt", "rep-strict"):
        for setting in ("transferred", "calibrated"):
            x = side[(d, setting)]
            L.append(f"  - `{d}` {setting}, {x['config']}: loss from lies {x['loss from lies']} (damage {x['damage']}, "
                     f"reroute premium {x['reroute premium']}, resid {x['resid']}), utility cost {x['utility cost']} "
                     f"({x['utility (% of cost)']}%), provider share {x['provider share']}.")
    L.append(f"  - Pareto fronts: OBT {front('obt')}; reputation (never-trading excluded) {front('rep-strict')}.")
    L.append(f"  - Bound over every OBT grid run: {b['OBT runs']} runs, {b['failure events']} failure events, max "
             f"damage/bound {b['max damage/bound']}, held {b['held']}; invariant violations {b['invariant violations']}; "
             f"transferred points reproduce E9 {b['transferred points reproduce E9']}.")
    L.append(OUT_END)
    d = root / "docs" / "DECISIONS.md"
    s = d.read_text()
    block = "\n".join(L)
    s = re.sub(re.escape(OUT_START) + r".*?" + re.escape(OUT_END), lambda _: block, s, flags=re.S) if OUT_START in s \
        else s.rstrip("\n") + "\n" + block + "\n"
    d.write_text(s)


def main(argv: list[str] | None = None) -> None:
    stage = (argv if argv is not None else sys.argv[1:] or ["run"])[0]
    if stage == "notes":
        release_notes()
        print("INDEX.md E9-calibration row and DECISIONS D45 outcome updated")
        return
    ext = stage.endswith("-ext")
    if stage in ("run", "run-ext"):
        run(points=[x for x in grid(ext) if x[1] == "obt"] if ext else None)
    s = summarize(ext=ext)
    (ROOT / ("summary_ext.json" if ext else "summary.json")).write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps({k: s[k] for k in ("fronts", "picks", "obt_pick_edges", "reproduces_e9")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
