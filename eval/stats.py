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


def share_by_round(rows: list[dict], d: str, scenario: int = 1) -> list[float]:
    """Per round, the S_main share of executed order units, averaged over seeds (rounds with no orders skipped)."""
    per: dict[int, list[float]] = {}
    for r in rows:
        if r["defense"] != d or r["scenario"] != scenario:
            continue
        for t in r["trace"]:
            main = sum(a[2] for a in t["actions"]
                       if a[0] == "ORDER" and a[4] == "EXECUTED" and a[1].startswith("S_main"))
            back = sum(a[2] for a in t["actions"] if a[0] == "ORDER" and a[4] == "EXECUTED"
                       and not a[1].startswith("S_main"))
            if main + back:
                per.setdefault(t["round"], []).append(main / (main + back))
    return [mean(per[k]) for k in sorted(per)]


def trust_over_time_svg(rows: list[dict], defenses=("obt", "rep-strict", "none"), scenario: int = 1) -> bytes:
    """S_main share of units per round, honest scenario, mean over seeds (5-round moving average drawn)."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "obt"
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for d in defenses:
        ys = share_by_round(rows, d, scenario)
        if not ys:
            continue
        ma = [mean(ys[max(0, i - 4):i + 1]) for i in range(len(ys))]
        ax.plot(range(1, len(ys) + 1), ma, label=d)
    ax.set_xlabel("round")
    ax.set_ylabel("S_main share of units (5-round mean)")
    ax.set_ylim(0, 1)
    ax.set_title("Trust over time: honest S_main", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return buf.getvalue()


def utility_pct_by_seed(rows: list[dict], d: str, scenario: int = 1) -> dict[int, float]:
    """seed -> utility cost as a % of the honest run's total cost without a defense (the utility-cost reference)."""
    c = _cost(rows)
    return {s: 100 * (c[(scenario, d, s)] - c[(scenario, "none", s)]) / c[(scenario, "none", s)]
            for s in sorted({r["seed"] for r in rows}) if (scenario, d, s) in c and (scenario, "none", s) in c}


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
    L = [f"Mean over seeds with a 95% CI (percentile bootstrap over seeds, {B:,} resamples). Seeds per row are given "
         "in the `seeds` column: a defense can have more seeds than another (extra seeds were run for some), and a "
         "utility cost needs the `none` run on the same seed. With few seeds the interval is coarse. $ per run.",
         "", "## Attack loss per defense (loss from lies, mean of scenarios 2-12)", "",
         "| defense | seeds | mean [95% CI] | per seed |", "|---|---|---|---|"]
    for d in defenses:
        v = attack_loss_by_seed(rows, d)
        xs = list(v.values())
        L.append(f"| {d} | {len(xs)} | {_fmt(mean(xs) if xs else None, *bootstrap_ci(xs))} | "
                 + ", ".join(f"s{s}: {x:,.1f}" for s, x in v.items()) + " |")
    L += ["", "## Utility cost per defense (primary utility metric: cost − cost(none), honest S_main, same seed)", "",
          "| defense | seeds | utility cost, honest [95% CI] | utility cost, noisy-honest [95% CI] | S_main unit "
          "share, honest | S_main orders blocked, honest |", "|---|---|---|---|---|---|"]
    for d in defenses:
        u1 = list(utility_cost_by_seed(rows, d, 1).values())
        u9 = list(utility_cost_by_seed(rows, d, 9).values())
        hon = [r for r in rows if r["defense"] == d and r["scenario"] == 1]
        sh = [x for x in (main_share(r) for r in hon) if x is not None]
        blk = [r["metrics"]["main_orders_blocked"] for r in hon]
        share = f"{mean(sh):.3f}" if sh else "-"
        L.append(f"| {d} | {len(u1)} | {_fmt(mean(u1) if u1 else None, *bootstrap_ci(u1))} | "
                 f"{_fmt(mean(u9) if u9 else None, *bootstrap_ci(u9))} | {share} | "
                 f"{f'{mean(blk):.1f}' if blk else '-'} |")
    L += ["", "## Utility cost as a % of the honest run's total cost (cost(none, honest), same seed)", "",
          "| defense | honest [95% CI] | noisy-honest [95% CI] |", "|---|---|---|"]
    for d in defenses:
        p1, p9 = list(utility_pct_by_seed(rows, d, 1).values()), list(utility_pct_by_seed(rows, d, 9).values())
        f = lambda xs: "-" if not xs else (  # noqa: E731
            f"{mean(xs):.2f}% [{bootstrap_ci(xs)[0]:.2f}, {bootstrap_ci(xs)[1]:.2f}]")
        L.append(f"| {d} | {f(p1)} | {f(p9)} |")
    L += ["", "## Scenario 9 (noisy-honest) utility cost, every defense", "",
          "Noisy-honest is an honest supplier with random delays: any cost above no defense is utility lost to false "
          "positives.", "", "| defense | utility cost [95% CI] | S_main unit share | S_main orders blocked |",
          "|---|---|---|---|"]
    for d in defenses:
        u9 = list(utility_cost_by_seed(rows, d, 9).values())
        n9 = [r for r in rows if r["defense"] == d and r["scenario"] == 9]
        sh = [x for x in (main_share(r) for r in n9) if x is not None]
        blk = [r["metrics"]["main_orders_blocked"] for r in n9]
        L.append(f"| {d} | {_fmt(mean(u9) if u9 else None, *bootstrap_ci(u9))} | "
                 f"{f'{mean(sh):.3f}' if sh else '-'} | {f'{mean(blk):.1f}' if blk else '-'} |")
    L += ["", "## Loss from lies per scenario (mean [95% CI] over each defense's seeds, as above)", "",
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


# ---------------------------------------------------------------- E2b (D30): trust-aware buyer view


def series(rows: list[dict], d: str, key: str, scenario: int = 1) -> list[float]:
    """Per round, mean over seeds of a trust quantity: key "B" (OBT budget) or "score" (reputation, trace['rep'])."""
    per: dict[int, list[float]] = {}
    for r in rows:
        if r["defense"] != d or r["scenario"] != scenario:
            continue
        for t in r["trace"]:
            v = t.get("B") if key == "B" else (t.get("rep") or {}).get("score")
            if v is not None:
                per.setdefault(t["round"], []).append(v)
    return [mean(per[k]) for k in sorted(per)]


def e2b_trust_svg(e2b: list[dict], e2: list[dict], e1: dict[str, list[dict]]) -> bytes:
    """Honest S_main. Top: OBT budget B per round. Middle: reputation score per round. Bottom: S_main unit share.
    Each panel overlays E2b (trust-aware LLM buyer), E2 (LLM buyer) and E1 (scripted buyer) where logged."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "obt"
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 8.5), sharex=True)
    runs = (("E2b trust-aware LLM", e2b, "-"), ("E2 LLM", e2, "--"), ("E1 scripted", None, ":"))
    for label, rows, ls in runs:
        obt = e1["obt"] if rows is None else rows
        rep = e1["rep-strict"] if rows is None else rows
        rep_d = "rep-strict"
        b = series(obt, "obt", "B")
        if b:
            axes[0].plot(range(1, len(b) + 1), b, ls, label=label)
        sc = series(rep, rep_d, "score")
        if sc:
            axes[1].plot(range(1, len(sc) + 1), sc, ls, label=label)
        for d, rs, color in (("obt", obt, "C0"), (rep_d, rep, "C1")):
            sh = share_by_round(rs, d)
            if sh:
                ma = [mean(sh[max(0, i - 4):i + 1]) for i in range(len(sh))]
                axes[2].plot(range(1, len(ma) + 1), ma, ls, color=color,
                             label=f"{'obt' if d == 'obt' else 'rep-strict'}, {label}")
    axes[0].set_ylabel("OBT budget B ($)")
    axes[1].set_ylabel("reputation score (rep-strict)")
    axes[2].set_ylabel("S_main unit share (5-round mean)")
    axes[2].set_xlabel("round (honest S_main, mean over seeds)")
    for ax in axes:
        ax.legend(fontsize=6)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return buf.getvalue()


def e2b_report(e2b: list[dict], e2: list[dict]) -> str:
    """E2b vs E2 on the same defenses, scenarios and seeds. E2b runs no `none` defense, so its utility cost uses
    E2's honest `none` run on the same seed as the reference (same game and demand; only the buyer view differs)."""
    scen = sorted({r["scenario"] for r in e2b})
    seeds = sorted({r["seed"] for r in e2b})
    e2 = [r for r in e2 if r["scenario"] in scen and r["seed"] in seeds]
    c2b, c2 = _cost(e2b), _cost(e2)
    none = {s: c2[(1, "none", s)] for s in seeds if (1, "none", s) in c2}

    def ci(xs):
        return _fmt(mean(xs) if xs else None, *bootstrap_ci(xs))

    def share(rows, d):
        xs = [x for x in (main_share(r) for r in rows if r["defense"] == d and r["scenario"] == 1) if x is not None]
        return f"{mean(xs):.3f}" if xs else "-"

    def utility(c, d):
        return [c[(1, d, s)] - none[s] for s in seeds if (1, d, s) in c and s in none]

    def loss(c, d, n):
        return [c[(n, d, s)] - c[(1, d, s)] for s in seeds if (n, d, s) in c and (1, d, s) in c]

    L = ["## E2b: trust-aware buyer view (supplementary; E2 is the main result)", "",
         "gpt-oss buyer with the frozen trust-aware view (D30); scenarios "
         f"{', '.join(scenario_name(n) for n in scen)}; "
         f"seeds {seeds}. Mean [95% bootstrap CI over seeds]. The E2 column is the same defense, scenarios and seeds "
         "with the standard view. Utility cost is against E2's honest `none` run on the same seed.", ""]
    for d in ("obt", "rep-strict"):
        L += [f"### {d}", "", "| metric | E2b trust-aware | E2 standard view |", "|---|---|---|",
              f"| S_main unit share, honest | {share(e2b, d)} | {share(e2, d)} |",
              f"| utility cost, honest ($) | {ci(utility(c2b, d))} | {ci(utility(c2, d))} |"]
        L += [f"| loss from lies, {scenario_name(n)} ($) | {ci(loss(c2b, d, n))} | {ci(loss(c2, d, n))} |"
              for n in scen if n != 1]
        L.append("")
    for label, rows in (("E2b", e2b), ("E2, same scenarios and seeds", e2)):
        db = damage_vs_bound(rows)
        mx = None if db["max_ratio"] is None else round(db["max_ratio"], 3)
        L.append(f"OBT damage vs bound, {label}: {db['events']} failure events in {db['runs_with_events']} runs; "
                 f"damage ${db['total_damage']:,.1f} vs bound ${db['total_bound']:,.1f}; max per-run ratio {mx}; "
                 f"bound held in every run: {db['all_ok']}.")
    return "\n".join(L) + "\n"


def trust_panels_svg(panels: list[tuple[str, list[tuple[str, list[dict], str, str]]]], title: str,
                     scenario: int = 1) -> bytes:
    """Stacked trust-over-time panels. Each line: (label, rows, defense, key) with key "B" (OBT budget), "score"
    (reputation, trace['rep']) or "share" (S_main unit share, 5-round mean). Honest scenario, mean over seeds."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "obt"
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(panels), 1, figsize=(6.5, 2.9 * len(panels)), sharex=True, squeeze=False)
    for ax, (ylabel, lines) in zip(axes[:, 0], panels):
        for label, rows, d, key in lines:
            ys = share_by_round(rows, d, scenario) if key == "share" else series(rows, d, key, scenario)
            if key == "share" and ys:
                ys = [mean(ys[max(0, i - 4):i + 1]) for i in range(len(ys))]
            if ys:
                ax.plot(range(1, len(ys) + 1), ys, label=label)
        ax.set_ylabel(ylabel)
        ax.legend(fontsize=6)
    axes[0, 0].set_title(title, fontsize=9)
    axes[-1, 0].set_xlabel("round (honest S_main, mean over seeds)")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return buf.getvalue()
