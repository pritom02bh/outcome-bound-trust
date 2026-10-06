"""paper/NUMBERS.md: every headline number the paper cites, from results/ only (and the TLC summaries in
spec/results/). Each number carries its value, unit, seeds and source file + key.

    python -m eval.numbers          # also run by `python -m eval.paper`

Values are copied from the exported tables as printed; a "derived" number (a reduction or a ratio of two
printed values) says which values it was computed from. Nothing is simulated and no run record is read.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The paper's research questions (DESIGN §10), plus the verification group, which is not an RQ (Section 6).
RQS = [("RQ1", "Security: does OBT cut the loss from lies?"),
       ("RQ2", "Utility cost: what does OBT cost honest trade?"),
       ("RQ3", "Tightness under adaptive attack: how close does damage come to the per-event bound?"),
       ("RQ4", "Earning trust: the order planner, trust over time, and the budget growth multiplier k"),
       ("RQ5", "Generalization across buyer models and domains (E3, E3b, E5, E9)"),
       ("RQ6", "Extraction reliability (E4, hard subset, E5 extractors, Enron)"),
       ("S6", "Section 6: verification (not an RQ)")]


# Every exported table NUMBERS.md cites; paper.build writes it only when all are present.
REQUIRED = ("main", "e5", "second_model", "e1_obt_front", "bound_tightness", "horizon", "budget_k", "extractor",
            "enron")


def _mean(cell) -> float:
    """The mean of a printed cell such as '43.1 [37.0, 50.5]' or '2,290.6'."""
    return float(str(cell).split(" [")[0].replace(",", ""))


class Tables:
    def __init__(self, results: Path) -> None:
        self.t = json.loads((results / "tables.json").read_text())

    def row(self, table: str, **match) -> dict:
        t = self.t[table]
        for r in t["rows"]:
            d = dict(zip(t["columns"], r))
            if all(str(d[k]) == str(v) for k, v in match.items()):
                return d
        raise KeyError(f"{table}: no row {match}")


def _tlc(spec_results: Path, name: str) -> dict:
    """The unmutated run of a TLC summary: distinct states, depth, runtime, verdict, and the bounds line."""
    text = (spec_results / f"{name}_summary.txt").read_text()
    bounds = " ".join(re.search(r"^# bounds: (.*)$", text, re.M).group(1).split())
    none = next(l.split() for l in text.splitlines() if l.startswith("none "))
    return {"verdict": none[1], "states": int(none[3]), "depth": int(none[4]), "runtime_s": int(none[5]),
            "bounds": bounds, "caught": sum(" CAUGHT(" in f" {l} " for l in text.splitlines())}


def entries(results: Path = ROOT / "results", spec_results: Path = ROOT / "spec" / "results") -> dict:
    T = Tables(results)
    J = "results/tables.json"
    out: dict = {rq: [] for rq, _ in RQS}

    def add(rq, claim, value, unit, seeds, source):
        out[rq].append((claim, value, unit, seeds, source))

    main = lambda d: T.row("main", defense=d)                            # noqa: E731
    src = lambda d: "E2c" if d in ("obt+planner", "rep-n18", "rep+planner") else "E2"   # noqa: E731
    e5 = lambda m, d: T.row("e5", buyer=m, defense=d)                     # noqa: E731
    e5seeds = lambda m: ("seed 1" if int(e5(m, "obt+planner")["seeds"]) == 1       # noqa: E731
                         else f"{e5(m, 'obt+planner')['seeds']} seeds")
    pareto = json.loads((results / "figdata" / "pareto.json").read_text())
    dflt = T.row("e1_obt_front", default="yes")

    # ---- RQ1 security: loss from lies (gpt-oss buyer; scripted E1)
    for d in ("obt", "obt+planner", "rep-strict", "none"):
        r = main(d)
        add("RQ1", f"{src(d)} loss from lies, `{d}` (gpt-oss buyer; mean [95% CI])", r["loss from lies"], "$ per run",
            f"{r['seeds']} seeds", f"{J} → main[defense={d}].loss from lies")
    none = _mean(main("none")["loss from lies"])
    for d in ("obt", "obt+planner"):
        v = _mean(main(d)["loss from lies"])
        add("RQ1", f"{src(d)} loss reduction vs E2 `none`, `{d}` (derived)", f"{100 * (1 - v / none):.1f}", "%",
            "as above", f"1 − main[{d}] / main[none], loss from lies means ({v:,.1f} / {none:,.1f})")
    # Comparisons with the strictest reputation baseline (derived from the main table's printed values).
    o, p, r = main("obt"), main("obt+planner"), main("rep-strict")
    add("RQ1", "`obt` vs `rep-strict`: loss from lies at matched utility cost (derived)",
        f"{_mean(o['loss from lies']):,.1f} vs {_mean(r['loss from lies']):,.1f} at "
        f"{o['utility (% of cost)']}% vs {r['utility (% of cost)']}% utility cost", "$ per run; % of cost",
        f"{o['seeds']} seeds each", f"{J} → main[obt|rep-strict].loss from lies, utility (% of cost)")
    add("RQ1", "`obt+planner` vs `rep-strict`: S_main share (honest) and loss from lies (derived)",
        f"S_main share {p['S_main share']} vs {r['S_main share']}; loss {_mean(p['loss from lies']):,.1f} vs "
        f"{_mean(r['loss from lies']):,.1f}", "share; $ per run", f"{p['seeds']} seeds each",
        f"{J} → main[obt+planner|rep-strict].S_main share, loss from lies")
    add("RQ1", f"E1 default OBT ({dflt['config']}) loss from lies vs `none` (scripted buyer)",
        f"{dflt['loss from lies']} vs {pareto['none']['attack_loss']:,.1f}", "$ per run", "seeds 1-3",
        f"{J} → e1_obt_front[default=yes]; results/figdata/pareto.json → none.attack_loss")

    # ---- RQ2 utility cost: $ per run and as % of the honest run's total cost without a defense
    for d in ("obt", "obt+planner", "rep-strict"):
        r = main(d)
        add("RQ2", f"{src(d)} utility cost, $ (mean [95% CI]) and % of cost, `{d}`",
            f"{r['utility cost']} ({r['utility (% of cost)']}%)", "$ per run (%)", f"{r['seeds']} seeds",
            f"{J} → main[defense={d}].utility cost, utility (% of cost)")
    add("RQ2", f"E1 default OBT ({dflt['config']}) utility cost (scripted buyer)", dflt["utility cost"],
        "$ per run", "seeds 1-3", f"{J} → e1_obt_front[default=yes].utility cost")

    # ---- RQ3 tightness: the largest per-run damage / Σ bound, adaptive attacker first
    rows = [dict(zip(T.t["bound_tightness"]["columns"], r)) for r in T.t["bound_tightness"]["rows"]]
    for d in sorted(rows, key=lambda d: not d["eval"].startswith("E6")):
        extra = "" if d["failure events"] == "-" else f"; {d['failure events']} failure events, damage " \
                                                       f"{d['damage']} vs bound {d['sum of bounds']}"
        add("RQ3", f"Max damage / Σ bound, {d['eval']} `{d['defense']}`{extra}", d["max damage/bound"], "ratio",
            {"E5": e5seeds("GPT-5.6 Luna" if "Luna" in d["eval"] else "GPT-5.6 Terra"), "E3": "seed 1", "E6": "seeds 1-3 (worst)", "E7": "seeds 1-3",
             "E2": f"{main(d['defense'])['seeds']} seeds"}.get(d["eval"][:2], "-"),
            f"{J} → bound_tightness[eval={d['eval']}].max damage/bound")

    # E8 (D43): an LLM adversarial supplier, black-box and white-box, against every defense.
    if "e8" in T.t:
        for r in T.t["e8"]["rows"]:
            x = dict(zip(T.t["e8"]["columns"], r))
            add("RQ3", f"E8 LLM adversary ({x['knowledge']}) vs `{x['defense']}`: loss from lies (mean [95% CI]); "
                f"max damage/bound; attacker profit (mean [95% CI])",
                f"{x['loss from lies']}; ratio {x['max damage/bound']}; profit {x['attacker profit']}",
                "$ per run; ratio; $ per run", f"{x['seeds']} seeds",
                f"{J} → e8[knowledge={x['knowledge']}, defense={x['defense']}]")

    # ---- RQ4 earning trust: planner, trust over time, budget growth k
    p, r = _mean(main("obt+planner")["loss from lies"]), _mean(main("rep-strict")["loss from lies"])
    add("RQ4", "`obt+planner` vs `rep-strict`: loss from lies (derived)", f"{p:,.1f} vs {r:,.1f} "
        f"({100 * (1 - p / r):.1f}% lower)", "$ per run", "5 seeds each",
        f"{J} → main[obt+planner|rep-strict].loss from lies")
    add("RQ4", "Trust over time: OBT budget B and S_main share per round, honest supplier (E2, E2c, E1)",
        "figure", "-", "as the evals", "paper/figures/trust_over_time.pdf; results/figdata/trust.json")
    h = T.row("horizon", defense="obt")
    add("RQ4", "Horizon: OBT utility cost (% of cost) at T = 50 → T = 100 (scripted buyer)",
        f"{h['utility % (T=50)']} → {h['utility % (T=100)']}", "% of cost", "seeds 1-3",
        f"{J} → horizon[defense=obt]")
    k1, k2 = T.row("budget_k", k=1, rounds=50), T.row("budget_k", k=2, rounds=50)
    add("RQ4", "E7: budget growth k = 1 → k = 2, utility cost (% of cost) and loss from lies (T = 50)",
        f"{k1['utility (% of cost)']} → {k2['utility (% of cost)']}; loss {k1['loss from lies']} → "
        f"{k2['loss from lies']}", "% of cost; $ per run", "seeds 1-3", f"{J} → budget_k[k=1|2, rounds=50]")

    # ---- RQ5 generalization across buyer models
    for run, d in (("E3", "obt"), ("E3", "none"), ("E3b", "obt+planner"), ("E3b", "rep+planner")):
        r = T.row("second_model", run=run, defense=d)
        add("RQ5", f"{run} loss from lies, `{d}` (qwen3:8b buyer; damage in brackets)",
            f"{r['loss from lies']} (damage {r['damage']})", "$ per run", "seed 1",
            f"{J} → second_model[run={run}, defense={d}]")
    for m in ("GPT-5.6 Luna", "GPT-5.6 Terra"):
        o, n = e5(m, "obt+planner"), e5(m, "none")
        add("RQ5", f"E5 v2 loss from lies, {m}: `obt+planner` vs own `none` (mean [95% CI])",
            f"{o['loss from lies']} vs {n['loss from lies']}", "$ per run", e5seeds(m),
            f"{J} → e5[buyer={m}].loss from lies")
        add("RQ5", f"E5 v2 loss reduction vs `none`, {m} (derived)",
            f"{100 * (1 - _mean(o['loss from lies']) / _mean(n['loss from lies'])):.1f}", "%", e5seeds(m),
            f"1 − e5[{m}, obt+planner] / e5[{m}, none], loss from lies")
    for m in ("GPT-5.6 Luna", "GPT-5.6 Terra"):
        r = e5(m, "obt+planner")
        add("RQ5", f"E5 v2 utility cost, $ (mean [95% CI]) and % of cost, {m} `obt+planner` (vs own `none`)",
            f"{r['utility cost']} ({r['utility (% of cost)']}%)", "$ per run (%)", e5seeds(m),
            f"{J} → e5[buyer={m}, defense=obt+planner].utility cost")

    # E9 (D44): a second domain (cloud/API capacity), scripted, structured intents.
    if "e9" in T.t:
        for r in T.t["e9"]["rows"]:
            x = dict(zip(T.t["e9"]["columns"], r))
            add("RQ5", f"E9 cloud domain, `{x['defense']}`: loss from lies; utility cost (% of cost) (mean [95% CI])",
                f"{x['loss from lies']}; {x['utility cost']} ({x['utility (% of cost)']}%)", "$ per run",
                f"{x['seeds']} seeds", f"{J} → e9[defense={x['defense']}]")
        b = {r[0]: dict(zip(T.t["e9_damage_vs_bound"]["columns"], r)) for r in T.t["e9_damage_vs_bound"]["rows"]}
        add("RQ5", f"E9 OBT damage vs Σ bound (QUOTA events {b['QUOTA']['failure events']}, SLA events "
            f"{b['SLA']['failure events']})", f"max {b['all']['max damage/bound']}; held {b['all']['held']}", "ratio",
            "3 seeds", f"{J} → e9_damage_vs_bound[events=all]")
    # E9 calibration (D45): each defense's cloud-domain config by E1's rule, next to the transferred one.
    if "e9_calibration" in T.t:
        for d in ("obt", "rep-strict"):
            t, c = T.row("e9_calibration", defense=d, setting="transferred"), \
                T.row("e9_calibration", defense=d, setting="calibrated")
            add("RQ5", f"E9 `{d}`, transferred → calibrated config (D45): loss from lies; utility cost (% of cost) "
                "(mean [95% CI])", f"{t['config']}: {t['loss from lies']}; {t['utility cost']} "
                f"({t['utility (% of cost)']}%) → {c['config']}: {c['loss from lies']}; {c['utility cost']} "
                f"({c['utility (% of cost)']}%)", "$ per run", "seeds 1-3",
                f"{J} → e9_calibration[defense={d}, setting=transferred|calibrated]")
        g = T.t["e9_calibration_grid"]
        front = lambda d: ", ".join(r[1] for r in g["rows"] if r[0] == d and r[6] == "yes")  # noqa: E731
        add("RQ5", "E9 calibration Pareto fronts (OBT; reputation, never-trading points excluded)",
            f"{front('obt')}; {front('rep-strict')}", "grid points", "seeds 1-3",
            f"{J} → e9_calibration_grid[front=yes]")
        b = dict(zip(T.t["e9_calibration_bound"]["columns"], T.t["e9_calibration_bound"]["rows"][0]))
        add("RQ5", f"E9 calibration: loss bound over every OBT grid run ({b['OBT runs']} runs, "
            f"{b['failure events']} failure events)", f"max {b['max damage/bound']}; held {b['held']}; invariant "
            f"violations {b['invariant violations']}", "ratio", "seeds 1-3", f"{J} → e9_calibration_bound")
    # D45a: the extended OBT grid, same rule.
    if "e9_calibration_ext" in T.t:
        x = {r[1]: dict(zip(T.t["e9_calibration_ext"]["columns"], r)) for r in T.t["e9_calibration_ext"]["rows"]}
        b = dict(zip(T.t["e9_calibration_ext_bound"]["columns"], T.t["e9_calibration_ext_bound"]["rows"][0]))
        c = x["calibrated, extended grid"]
        add("RQ5", f"E9 `obt` calibrated on the extended grid (D45a, b0 to 80%, k to 4): pick moved {b['pick moved']}; "
            f"pick on grid edge: {b['pick on grid edge']}", f"{c['config']}: {c['loss from lies']}; "
            f"{c['utility cost']} ({c['utility (% of cost)']}%)", "$ per run", "seeds 1-3",
            f"{J} → e9_calibration_ext[setting=calibrated, extended grid]")
        g = T.t["e9_calibration_ext_grid"]
        add("RQ5", "E9 extended OBT grid: Pareto front (D45a)", ", ".join(r[0] for r in g["rows"] if r[6] == "yes"),
            "grid points", "seeds 1-3", f"{J} → e9_calibration_ext_grid[front=yes]")
        add("RQ5", f"E9 extended OBT grid: loss bound over every run ({b['OBT runs']} runs, {b['failure events']} "
            "failure events)", f"max {b['max damage/bound']}; held {b['held']}; invariant violations "
            f"{b['invariant violations']}", "ratio", "seeds 1-3", f"{J} → e9_calibration_ext_bound")

    # ---- RQ6 extraction reliability
    for m in ("gpt-oss:20b", "qwen3:8b", "gpt-5.6-luna", "gpt-5.6-terra"):
        r = T.row("extractor", extractor=m)
        add("RQ6", f"Extractor `{m}`, test set (199): precision / recall / exact",
            f"{r['precision']} / {r['recall']} / {r['exact']}", "fraction", "frozen prompt",
            f"{J} → extractor[extractor={m}]")
        add("RQ6", f"Extractor `{m}`, hard subset (30): shipping/ready dates taken as deadlines, LLM alone → "
            f"with code guard", f"{r['hard: LLM alone']} → {r['hard: with guard']}", "items", "frozen prompt",
            f"{J} → extractor[extractor={m}].hard: LLM alone, hard: with guard")
    for st in ("delivery", "price"):
        r = T.row("enron", extractor="gpt-oss:20b", stratum=st)
        add("RQ6", f"Enron real text, {st} stratum (gpt-oss): wrong claims recorded; commitments UNTESTABLE",
            f"{r['wrong recorded']}; {r['claims UNTESTABLE']}", "claims", f"{r['rows']} rows",
            f"{J} → enron[extractor=gpt-oss:20b, stratum={st}]")

    # Independent annotator (D42a): a professor not involved in the project, blind to our labels.
    if "annotator_agreement" in T.t:
        a = lambda s: T.row("annotator_agreement", set=s)   # noqa: E731
        for s in ("spot-check, all", "spot-check, v2 rows", "Enron is_commitment"):
            x = a(s)
            add("RQ6", f"Independent annotator vs ours, {s}: raw agreement; Cohen's kappa; disagreements",
                f"{x['raw agreement']}; kappa {x['kappa']}{' (degenerate)' if x['kappa degenerate'] == 'yes' else ''}; "
                f"{x['disagreements']} of {x['rows']}", "fraction; kappa; rows", "1 annotator",
                f"{J} → annotator_agreement[set={s}]")
        x = a("spot-check, seeded errors")
        add("RQ6", "Independent annotator: seeded-error detection rate (v1 rows we marked no)",
            f"{x['detection rate']} ({x['rows']} seeded rows)", "fraction", "1 annotator",
            f"{J} → annotator_agreement[set=spot-check, seeded errors]")
        sl = T.t["annotator_slots"]["rows"]
        add("RQ6", "Independent annotator: Enron slot agreement on rows both mark is_commitment = yes",
            "; ".join(f"{r[0]} {r[2]}/{r[1]}" for r in sl), "rows", "1 annotator", f"{J} → annotator_slots")

    # Paper walkthrough (D46): one E2 run, from the run logs (results/figdata/walkthrough.json).
    wf = results / "figdata" / "walkthrough.json"
    if wf.exists():
        w = json.loads(wf.read_text())
        d = w["defenses"]
        WJ = "results/figdata/walkthrough.json"
        lie = next(e for e in w["key_events"] if e["event"].startswith("The lie"))["round"]
        q = {k: sum(o["qty"] for o in x["rounds"][lie - 1]["orders"] if o["supplier"] != "S_backup")
             for k, x in d.items()}
        add("RQ1", "Walkthrough (E2 farm-then-lie, seed 1): loss from lies, `obt` / `rep-default` / `none` (derived)",
            f"{d['obt']['loss_from_lies']:.2f} / {d['rep-default']['loss_from_lies']:.2f} / "
            f"{d['none']['loss_from_lies']:.2f}", "$ per run", "seed 1",
            f"{WJ} → defenses[*].loss_from_lies (cost − honest cost, {w['log']} lines "
            + ", ".join(f"{x['line']}−{x['honest_line']}" for x in d.values()) + ")")
        add("RQ1", f"Walkthrough: S_main units ordered on the lie (round {lie}), `obt` / `rep-default` / `none`; OBT "
            "budget B at that order (derived)", f"{q['obt']} / {q['rep-default']} / {q['none']} units; "
            f"B {d['obt']['rounds'][lie - 1]['B']:.2f}", "units; $", "seed 1",
            f"{WJ} → defenses[*].rounds[{lie - 1}].orders, defenses[obt].rounds[{lie - 1}].B")
        add("RQ3", "Walkthrough: OBT damage vs Σ L_e; blocked S_main orders (derived)",
            f"{d['obt']['damage']:.2f} vs {d['obt']['sum_bound']:.2f}; {d['obt']['main_orders_blocked']} blocked",
            "$; orders", "seed 1", f"{WJ} → defenses[obt].damage, sum_bound, main_orders_blocked")

    # ---- Section 6 verification (not an RQ). States and depth only: runtimes are wall-clock and host-dependent.
    for name, label in (("quick", "quick"), ("fallbackA2", "A′"), ("fallbackB", "B"),
                        ("quick_b01", "quick, B0 = 1"), ("fallbackA2_b01", "A′, B0 = 1")):
        x = _tlc(spec_results, name)
        runtime = "" if name == "fallbackB" else f", {x['runtime_s']:,} s"
        add("S6", f"TLA+ k = 1, {label}: unmutated spec {x['verdict']} ({x['bounds']})",
            f"{x['states']:,} states, depth {x['depth']}{runtime}", "distinct states", "exhaustive",
            f"spec/results/{name}_summary.txt → none")
    cov = (spec_results / "k_coverage.txt").read_text()
    add("S6", "TLA+ k = 1 mutant coverage: every guard mutant caught in ≥ 1 config",
        "8/8" if "RESULT: every mutant caught" in cov else "NOT all", "mutants", "5 configs",
        "spec/results/k_coverage.txt → RESULT")
    add("S6", "TLA+ k > 1", "not model-checked (no checked bound makes the k = 2 budget bind)", "-", "-",
        "spec/results/README.md → Budget growth multiplier K; DECISIONS D36b")
    return out


def render(out: dict) -> str:
    L = ["# NUMBERS: every headline number the paper cites", "",
         "Generated by `python -m eval.numbers` from `results/` (and the TLC summaries in `spec/results/`) only: "
         "no simulation, no run records, no model calls. Tag `v1.9.1-paper`. Values are as printed in the "
         "exported tables; *derived* rows name the values they were computed from.", "",
         "Definitions (DESIGN §10): **loss from lies** = mean over attack scenarios 2-12 of cost − cost of the "
         "honest run (same defense, seed). **Utility cost** = cost(defense) − cost(`none`), honest scenario, same "
         "seed, reported in $ per run and as a % of the honest run's total cost without a defense. "
         "**Reroute premium** = the dollar backup premium on quantity a defense reroutes to the backup supplier "
         "after its own blocks (per run; in the loss split it is differenced against the honest run). "
         "**Damage** = cost against the same decisions with every relied-on promise kept; the bound is Σ L_e "
         "(DESIGN §6).", "",
         "Grouped by the paper's research questions (DESIGN §10); verification is Section 6, not an RQ.", ""]
    for rq, title in RQS:
        head = title if rq == "S6" else f"{rq}. {title}"
        L += [f"## {head}", "", "| claim | value | unit | seeds | source (file → key) |", "|---|---|---|---|---|"]
        L += [f"| {c} | {v} | {u} | {s} | {src} |" for c, v, u, s, src in out[rq]]
        L.append("")
    return "\n".join(L)


def write(results: Path = ROOT / "results", out: Path = ROOT / "paper",
          spec_results: Path = ROOT / "spec" / "results") -> Path:
    f = out / "NUMBERS.md"
    f.write_text(render(entries(results, spec_results)))
    return f


if __name__ == "__main__":
    print(write())
