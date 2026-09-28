"""Final-report statistics from run records (used by `make results`): bootstrap CIs over seeds, utility cost as
the primary utility metric, S_main share of supply, and OBT damage vs its per-event bound.

Seeds are the unit of resampling: a run's scenarios share its demand series and supplier seed, so they are not
independent. With few seeds the percentile CI is necessarily coarse (with 3 seeds it spans roughly the smallest
to the largest seed mean) and is reported as such, never as more.
"""
from __future__ import annotations

import random
from statistics import mean

from obt.attacks.suppliers import scenario_name

B = 10_000                  # bootstrap resamples
_SEED = 20260928            # fixed, so `make results` is byte-deterministic


def bootstrap_ci(xs: list[float], level: float = 0.95) -> tuple[float | None, float | None]:
    """Percentile bootstrap CI for the mean, resampling the given per-seed values with replacement."""
    if not xs:
        return None, None
    if len(xs) == 1:
        return xs[0], xs[0]
    rng = random.Random(_SEED)
    ms = sorted(mean(rng.choices(xs, k=len(xs))) for _ in range(B))
    a = (1 - level) / 2
    return ms[int(a * (B - 1))], ms[int((1 - a) * (B - 1))]


def _cost(rows: list[dict]) -> dict:
    return {(r["scenario"], r["defense"], r["seed"]): r["total_cost"] for r in rows}


def attack_loss_by_seed(rows: list[dict], d: str) -> dict[int, float]:
    """seed -> mean over scenarios 2..12 of loss_from_lies (cost − cost of the honest run, same defense, seed)."""
    c = _cost(rows)
    out = {}
    for s in sorted({r["seed"] for r in rows if r["defense"] == d}):
        v = [c[(n, d, s)] - c[(1, d, s)] for n in range(2, 13) if (n, d, s) in c and (1, d, s) in c]
        if v:
            out[s] = mean(v)
    return out


def utility_cost_by_seed(rows: list[dict], d: str, scenario: int = 1) -> dict[int, float]:
    """seed -> cost(d, honest) − cost(none, honest) on the same seed (the primary utility metric)."""
    c = _cost(rows)
    return {s: c[(scenario, d, s)] - c[(scenario, "none", s)] for s in sorted({r["seed"] for r in rows})
            if (scenario, d, s) in c and (scenario, "none", s) in c}


def main_share(r: dict) -> float | None:
    """Share of executed order units that came from S_main (any of its identities)."""
    main = back = 0
    for t in r["trace"]:
        for kind, cp, qty, *rest in t["actions"]:
            if kind == "ORDER" and rest[1] == "EXECUTED":
                if cp.startswith("S_main"):
                    main += qty
                else:
                    back += qty
    return main / (main + back) if main + back else None


def damage_vs_bound(rows: list[dict]) -> dict:
    obt = [r for r in rows if r["defense"] == "obt" and r["metrics"]["loss_bound"]["events"]]
    ratios = [r["metrics"]["loss_bound"]["damage"] / r["metrics"]["loss_bound"]["sum_bound"] for r in obt
              if r["metrics"]["loss_bound"]["sum_bound"]]
    per_scenario: dict = {}
    for r in obt:
        lb = r["metrics"]["loss_bound"]
        p = per_scenario.setdefault(r["scenario"], {"runs": 0, "events": 0, "damage": 0.0, "bound": 0.0,
                                                     "apriori": 0.0})
        p["runs"] += 1
        p["events"] += len(lb["events"])
        p["damage"] += lb["damage"]
        p["bound"] += lb["sum_bound"]
        p["apriori"] += sum(e.get("apriori", 0.0) for e in lb["events"])
    return {"runs_with_events": len(obt), "events": sum(len(r["metrics"]["loss_bound"]["events"]) for r in obt),
            "total_damage": round(sum(r["metrics"]["loss_bound"]["damage"] for r in obt), 4),
            "total_bound": round(sum(r["metrics"]["loss_bound"]["sum_bound"] for r in obt), 4),
            "all_ok": all(r["metrics"]["loss_bound"]["ok"] is not False for r in rows if r["defense"] == "obt"),
            "min_ratio": min(ratios) if ratios else None, "median_ratio": sorted(ratios)[len(ratios) // 2]
            if ratios else None, "max_ratio": max(ratios) if ratios else None, "per_scenario": per_scenario}


def _fmt(m, lo, hi) -> str:
    if m is None:
        return "-"
    return f"{m:,.1f} [{lo:,.1f}, {hi:,.1f}]"


def report(rows: list[dict], defenses: list[str] | None = None) -> str:
    defenses = defenses or list(dict.fromkeys(r["defense"] for r in rows))
    seeds = sorted({r["seed"] for r in rows})
    L = [f"Mean over seeds with a 95% CI (percentile bootstrap over the {len(seeds)} seeds, {B:,} resamples; with "
         f"{len(seeds)} seeds the interval is coarse). $ per run.", "",
         "## Attack loss per defense (loss from lies, mean of scenarios 2-12)", "",
         "| defense | mean [95% CI] | per seed |", "|---|---|---|"]
    for d in defenses:
        v = attack_loss_by_seed(rows, d)
        xs = list(v.values())
        L.append(f"| {d} | {_fmt(mean(xs) if xs else None, *bootstrap_ci(xs))} | "
                 + ", ".join(f"s{s}: {x:,.1f}" for s, x in v.items()) + " |")
    L += ["", "## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)", "",
          "| defense | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit share, "
          "honest | S_main orders blocked, honest |", "|---|---|---|---|---|"]
    for d in defenses:
        u1 = list(utility_cost_by_seed(rows, d, 1).values())
        u9 = list(utility_cost_by_seed(rows, d, 9).values())
        hon = [r for r in rows if r["defense"] == d and r["scenario"] == 1]
        sh = [x for x in (main_share(r) for r in hon) if x is not None]
        blk = [r["metrics"]["main_orders_blocked"] for r in hon]
        share = f"{mean(sh):.3f}" if sh else "-"
        L.append(f"| {d} | {_fmt(mean(u1) if u1 else None, *bootstrap_ci(u1))} | "
                 f"{_fmt(mean(u9) if u9 else None, *bootstrap_ci(u9))} | {share} | "
                 f"{f'{mean(blk):.1f}' if blk else '-'} |")
    L += ["", "## Loss from lies per scenario (mean [95% CI] over seeds)", "",
          "| scenario | " + " | ".join(defenses) + " |", "|---|" + "---|" * len(defenses)]
    c = _cost(rows)
    for n in sorted({r["scenario"] for r in rows}):
        cells = []
        for d in defenses:
            xs = [c[(n, d, s)] - c[(1, d, s)] for s in seeds if (n, d, s) in c and (1, d, s) in c]
            cells.append(_fmt(mean(xs) if xs else None, *bootstrap_ci(xs)))
        L.append(f"| {scenario_name(n)} | " + " | ".join(cells) + " |")
    db = damage_vs_bound(rows)
    L += ["", "## OBT damage vs bound (every OBT run with at least one failure event)", "",
          f"{db['events']} failure events in {db['runs_with_events']} runs; total damage ${db['total_damage']:,.1f} vs "
          f"total bound ${db['total_bound']:,.1f}; damage/bound per run: min "
          f"{db['min_ratio'] if db['min_ratio'] is None else round(db['min_ratio'], 3)}, median "
          f"{db['median_ratio'] if db['median_ratio'] is None else round(db['median_ratio'], 3)}, max "
          f"{db['max_ratio'] if db['max_ratio'] is None else round(db['max_ratio'], 3)}; bound held in every run: "
          f"{db['all_ok']}.", "",
          "| scenario | runs | events | damage | Σ bound | Σ a-priori (budget) bound |", "|---|---|---|---|---|---|"]
    for n, p in sorted(db["per_scenario"].items()):
        L.append(f"| {scenario_name(n)} | {p['runs']} | {p['events']} | {p['damage']:,.1f} | {p['bound']:,.1f} | "
                 f"{p['apriori']:,.1f} |")
    return "\n".join(L) + "\n"
