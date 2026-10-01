"""E9 (DECISIONS D44, docs/E9_PLAN.md): the cloud/API-capacity domain. Scripted buyer and providers, structured
intents (no natural-language extraction), in-process, no model calls.

    python -m eval.e9 run       # 7 scenarios x 4 defenses x seeds 1-3 = 84 runs into runs/e9 (resumable)

Defenses: none, rep-strict, rep-n18, obt (the OBT default: b0 5%, W 0, delta 0). Any invariant or loss-bound
violation stops the run (STOP rule).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from eval.run import git_state
from obt.env.beer_game import GameConfig
from obt.env.cloud import CapacityBuyer, StructuredExtractor, cloud_scenario_name, make_cloud_supplier
from obt.llm import RUNS
from obt.sim import Sim, SimConfig

OUT = RUNS / "e9"
SCENARIOS = tuple(range(1, 8))
SEEDS = (1, 2, 3)
OBT_DEFAULT = {"b0_frac": 0.05, "window": 0, "grace": 0}
DEFENSES = {"none": ("none", {}), "rep-strict": ("reputation", {"rep_cap": 200.0, "rep_theta": 0.9}),
            "rep-n18": ("reputation", {"rep_n0": 18, "rep_theta": 0.9, "rep_cap": 200.0}),
            "obt": ("obt", {})}


class Violation(RuntimeError):
    pass


def sim_config(defense: str, rounds: int = 50) -> SimConfig:
    base, extra = DEFENSES[defense]
    return SimConfig(game=GameConfig(rounds=rounds), defense=base, transport="inproc", domain="cloud",
                     **{**OBT_DEFAULT, **extra})


def run_one(n: int, defense: str, seed: int, rounds: int = 50) -> dict:
    cfg = sim_config(defense, rounds)
    t0 = time.time()
    sim = Sim(cfg, seed, make_cloud_supplier(n, cfg.game, seed), CapacityBuyer(cfg.game),
              extractor=StructuredExtractor(), scenario=cloud_scenario_name(n))
    res = sim.run()
    commit, dirty = git_state()
    return {"scenario": n, "name": cloud_scenario_name(n), "defense": defense, "seed": seed, "domain": "cloud",
            "buyer": "scripted", "total_cost": res.total_cost, "costs": res.costs, "metrics": res.metrics,
            "trace": res.trace, "rounds": rounds, "wall_s": round(time.time() - t0, 3),
            "meta": {"git_commit": commit, "git_dirty": dirty, "domain": "cloud", "sim": {**OBT_DEFAULT,
                     **DEFENSES[defense][1]}, "transport": "inproc", "extractor": "structured"}}


def load(out: Path = OUT) -> list[dict]:
    f = out / "results.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def run(out: Path = OUT, scenarios=SCENARIOS, defenses=tuple(DEFENSES), seeds=SEEDS, rounds: int = 50) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    done = {(r["scenario"], r["defense"], r["seed"]) for r in load(out)}
    for s in seeds:
        for d in defenses:
            for n in scenarios:
                if (n, d, s) in done:
                    continue
                r = run_one(n, d, s, rounds)
                with (out / "results.jsonl").open("a") as f:
                    f.write(json.dumps(r, default=str) + "\n")
                lb = r["metrics"]["loss_bound"]
                print(f"{r['name']:18s} {d:10s} s{s} cost {r['total_cost']:9.1f} damage {lb['damage']} "
                      f"bound {lb['sum_bound']} wall {r['wall_s']}s", flush=True)
                if r["metrics"]["invariant_violations"]["count"] or lb["ok"] is False:
                    raise Violation(f"STOP: violation in {r['name']} {d} s{s}")
    return load(out)


# ------------------------------------------------------------------ summary (results build)

def summary(rows: list[dict]) -> dict:
    """Per defense over seeds: loss from lies (mean of scenarios 2-7) and its split, utility cost (scenario 1 vs
    none) in $ and %, main-provider share (honest), and OBT damage vs bound per event type."""
    from statistics import mean

    from eval.stats import attack_loss_by_seed, loss_split, main_share, utility_cost_by_seed, utility_pct_by_seed
    out = {"defenses": {}, "bound": {}}
    for d in DEFENSES:
        rs = [r for r in rows if r["defense"] == d]
        if not rs:
            continue
        sh = [x for x in (main_share(r) for r in rs if r["scenario"] == 1) if x is not None]
        out["defenses"][d] = {"loss": list(attack_loss_by_seed(rows, d).values()), "split": loss_split(rows, d),
                              "util": list(utility_cost_by_seed(rows, d).values()),
                              "util_pct": list(utility_pct_by_seed(rows, d).values()),
                              "share": mean(sh) if sh else None,
                              "violations": sum(r["metrics"]["invariant_violations"]["count"] for r in rs)}
    obt = [r for r in rows if r["defense"] == "obt"]
    for kind in ("QUOTA", "SLA"):
        ev = [(r, e) for r in obt for e in r["metrics"]["loss_bound"]["events"] if e["template"] == kind]
        out["bound"][kind] = {"events": len(ev), "runs": len({(r["scenario"], r["seed"]) for r, _ in ev}),
                              "sum_bound": sum(e["bound"] for _, e in ev)}
    ratios = [r["metrics"]["loss_bound"]["damage"] / r["metrics"]["loss_bound"]["sum_bound"] for r in obt
              if r["metrics"]["loss_bound"]["events"] and r["metrics"]["loss_bound"]["sum_bound"]]
    # Per run: damage against the sum of its events' a-priori (budget-form) bounds, as E7 reports it.
    apri = [r["metrics"]["loss_bound"]["damage"] / sum(e["apriori"] for e in r["metrics"]["loss_bound"]["events"])
            for r in obt if r["metrics"]["loss_bound"]["events"]
            and sum(e["apriori"] for e in r["metrics"]["loss_bound"]["events"])]
    out["bound"]["all"] = {"runs_with_events": len(ratios),
                           "damage": sum(r["metrics"]["loss_bound"]["damage"] for r in obt
                                         if r["metrics"]["loss_bound"]["events"]),
                           "sum_bound": sum(r["metrics"]["loss_bound"]["sum_bound"] for r in obt
                                            if r["metrics"]["loss_bound"]["events"]),
                           "max_ratio": max(ratios) if ratios else None,
                           "held": all(r["metrics"]["loss_bound"]["ok"] is not False for r in obt),
                           "max_apriori_ratio": max(apri) if apri else None}
    return out


OUT_START, OUT_END = "<!-- D44 outcome (generated) -->", "<!-- /D44 outcome -->"


def release_notes(root: Path = RUNS.parent) -> None:
    """INDEX.md E9 row and DECISIONS D44's outcome, from results/tables.json and results/e9_equivalence (idempotent)."""
    import re
    t = json.loads((root / "results" / "tables.json").read_text())
    rows = {r[0]: dict(zip(t["e9"]["columns"], r)) for r in t["e9"]["rows"]}
    b = {r[0]: dict(zip(t["e9_damage_vs_bound"]["columns"], r)) for r in t["e9_damage_vs_bound"]["rows"]}
    eq = json.loads((root / "results" / "e9_equivalence" / "report.json").read_text())
    commits = sorted({r["meta"]["git_commit"][:7] for r in load(root / "runs" / "e9")})
    line = (f"| **E9** second domain (cloud capacity) | scripted, structured intents; 7 scenarios × none, rep-strict, "
            f"rep-n18, obt × seeds 1-3 (D44) | {', '.join(f'`{c}`' for c in commits)} | `results/e9/report.md` "
            f"(`v1.6-results`) | OBT loss **{rows['obt']['loss from lies']}** vs none {rows['none']['loss from lies']}; "
            f"max damage/bound {b['all']['max damage/bound']} (QUOTA {b['QUOTA']['failure events']}, SLA "
            f"{b['SLA']['failure events']} events); supply domain byte-identical: {eq['identical']} |")
    f = root / "results" / "INDEX.md"
    s = f.read_text()
    s = re.sub(r"^\| \*\*E9\*\* .*\n", "", s, flags=re.M)
    anchor = re.search(r"^\| \*\*E8\*\* .*$", s, flags=re.M) or re.search(r"^\| \*\*E7\*\* .*$", s, flags=re.M)
    s = s[:anchor.end()] + "\n" + line + s[anchor.end():]
    s = re.sub(r"^# Results index \(tags .*\)$", lambda m: m.group(0)[:-1] + ", `v1.6-results`: + E9)"
               if "v1.6" not in m.group(0) else m.group(0), s, count=1, flags=re.M)
    f.write_text(s)
    L = [OUT_START, "- **Outcome** (generated by `python -m eval.e9 notes`):",
         f"  - Supply domain unchanged: E1 default runs byte-identical {eq['e1_identical']} (ledger, costs, verdicts, 12 "
         f"scenarios); gate differential byte-identical {eq['gate_differential']['identical']} "
         f"({eq['gate_differential']['new']['examples']} examples, {eq['gate_differential']['new']['disagreements']} "
         f"gate/monitor disagreements); uncached extractor calls {eq['uncached_llm_calls']}."]
    for d, x in rows.items():
        L.append(f"  - `{d}`: loss from lies {x['loss from lies']} (damage {x['damage']}, reroute premium "
                 f"{x['reroute premium']}, resid {x['resid']}), utility cost {x['utility cost']} "
                 f"({x['utility (% of cost)']}%), provider share {x['provider share']}.")
    L.append(f"  - OBT damage vs bound: {b['all']['damage']} vs {b['all']['sum of bounds']}, max ratio "
             f"{b['all']['max damage/bound']}, max a-priori ratio {b['all']['max damage/a-priori']}, held "
             f"{b['all']['held']}; QUOTA events {b['QUOTA']['failure events']}, SLA events {b['SLA']['failure events']}.")
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
        print("INDEX.md E9 row and DECISIONS D44 outcome updated")
        return
    if stage == "run":
        rows = run()
        print(json.dumps({k: v for k, v in summary(rows)["bound"].items()}, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
