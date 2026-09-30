"""Spec-code trace replay (FIXES F6 conformance check 2).

Replays every gate decision in TLC simulation traces through the Python gate
(`obt.gate.Gate.allow`) and the runtime monitor's independent table
(`obt.monitor.table_verdict`), and asserts both agree with the spec's verdict
(EXECUTED vs BLOCKED) on the same pre-state.

    python -m spec.replay <trace_dir> <cfg>
    python -m spec.replay campaign <uniform|guided> <mutant> <min_traces> <min_decisions> <seed> <out.json>

`campaign` runs TLC `-simulate file=` at full bounds in batches of 1,000 traces
(seeds seed, seed+1, ...) until both minimums are met, replays each batch, keeps
only traces that contain a gate decision (under spec/states/replay/), and
writes the totals as JSON. "guided" uses MCsim's GuidedSpec (proposals cite only
PENDING same-supplier, same-item claims), which reaches the allow rows far more
often. A mutant campaign checks no properties in TLC, so the mutated gate keeps
running and the replay must report the mismatches (negative control).

Mapping from spec to code (the spec abstracts prices to one level):
    supplier s1, s2        -> counterparty "s1", "s2"
    item i1, i2            -> "widget", "gadget"   (gadget via model_copy: the catalog is closed, D18 tests)
    claim tmpl "D" / "P"   -> DELIVERY {qty, by_round=by} / PRICE {unit_price=1.00, valid_until=by}
    claim tmpl "U"         -> UNTESTABLE
    claim st "NONE"        -> absent from the ledger (citing it is UNKNOWN_CLAIM)
    exposure, consumed, resolved -> realized_exposure, consumed, resolved_round
    order                  -> ORDER, unit_price 1.00, value = qty, executed_round = round if exec
    (all money is exact Decimal on both sides, D19: integers in the spec, cents in the code)
    payment                -> PAYMENT, value = amount, ref_order = the order id (NoRef -> None)
    B0, W, MinLead, K      -> BudgetConfig(b0=B0, window=W, k=K), Gate(min_lead={s: MinLead})

`build_world` bypasses the ledger's append-only API on purpose: it reconstructs
an arbitrary reachable state rather than replaying how it was reached. Harness
code only; nothing in `obt/` calls it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from obt.budget import BudgetConfig, TrustBudget
from obt.gate import Gate, GateSnapshot
from obt.ledger import ActionLog, Ledger
from obt.monitor import table_verdict
from obt.types import Action, Claim, FrozenDict

ITEM = {"i1": "widget", "i2": "gadget"}


# ------------------------------------------------------------------ world construction (shared with tests)

def with_item(claim: Claim, item: str) -> Claim:
    if item == "widget" or claim.template is None:
        return claim
    return claim.model_copy(update={"slots": FrozenDict({**claim.slots, "item": item})})


def build_world(claims: list[Claim], actions: list[Action], b0: Decimal, window: int,
                min_lead: dict[str, int], k: int = 1) -> Gate:
    led, log = Ledger(), ActionLog()
    for c in claims:
        led._claims[c.claim_id] = c
    for a in actions:
        log._actions[a.action_id] = a
        for cid in dict.fromkeys(a.cited_claims):
            log._by_claim.setdefault(cid, []).append(a.action_id)
    budget = TrustBudget(led, log, BudgetConfig(b0=b0, window=window, k=k))
    return Gate(led, log, budget, min_lead=min_lead)


def snapshot(gate: Gate, a: Action, now: int) -> GateSnapshot:
    """Exactly what Gate.decide records before deciding, without committing anything."""
    ref = gate.actions.get(a.ref_order) if a.ref_order else None
    return GateSnapshot(action=a, now=now,
                        claims={k: c for k in a.cited_claims if (c := gate.ledger.get(k)) is not None},
                        P=gate.budget.pending(a.counterparty), B=gate.budget.B(a.counterparty, now),
                        paid=gate.paid_so_far(ref.action_id) if ref else 0.0, ref=ref,
                        min_lead=gate.min_lead.get(a.counterparty, 0))


# ------------------------------------------------------------------ TLC value parser

_TOK = re.compile(r'\s*(<<|>>|\|->|:>|@@|/\\|==|[\[\]{}(),=]|"(?:[^"\\]|\\.)*"|-?\d+|[A-Za-z_][A-Za-z0-9_]*)')


def _tokens(text: str) -> list[str]:
    out, i = [], 0
    while i < len(text):
        m = _TOK.match(text, i)
        if not m:
            if text[i:].strip() == "":
                break
            raise ValueError(f"cannot tokenize at {text[i:i + 40]!r}")
        out.append(m.group(1))
        i = m.end()
    return out


class _P:
    def __init__(self, toks: list[str]) -> None:
        self.t, self.i = toks, 0

    def peek(self) -> str | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self, want: str | None = None) -> str:
        tok = self.t[self.i]
        if want is not None and tok != want:
            raise ValueError(f"expected {want!r}, got {tok!r}")
        self.i += 1
        return tok

    def seq(self, close: str) -> list:
        items = []
        while self.peek() != close:
            items.append(self.value())
            if self.peek() == ",":
                self.eat(",")
        self.eat(close)
        return items

    def value(self):
        tok = self.eat()
        if tok == "(":                                   # function: k :> v @@ k :> v
            f = {}
            while True:
                k = self.value()
                self.eat(":>")
                f[k] = self.value()
                if self.peek() == "@@":
                    self.eat("@@")
                    continue
                self.eat(")")
                return f
        if tok == "[":                                   # record
            r = {}
            while self.peek() != "]":
                name = self.eat()
                self.eat("|->")
                r[name] = self.value()
                if self.peek() == ",":
                    self.eat(",")
            self.eat("]")
            return r
        if tok == "{":
            return frozenset(self.seq("}"))
        if tok == "<<":
            return tuple(self.seq(">>"))
        if tok.startswith('"'):
            return tok[1:-1]
        if tok in ("TRUE", "FALSE"):
            return tok == "TRUE"
        if re.fullmatch(r"-?\d+", tok):
            return int(tok)
        return tok                                       # model value


def parse_trace(text: str) -> list[dict]:
    """A TLC `-simulate file=` trace module -> list of states (var -> value)."""
    states = []
    for block in re.split(r"^STATE_\d+ ==\s*$", text, flags=re.M)[1:]:
        block = block.split("\n=====")[0]
        p = _P(_tokens(block))
        st = {}
        while p.peek() is not None:
            p.eat("/\\")
            var = p.eat()
            p.eat("=")
            st[var] = p.value()
        states.append(st)
    return states


def parse_cfg(text: str) -> dict:
    consts = {}
    for m in re.finditer(r"^\s+(\w+)\s*=\s*(.+?)\s*$", text, flags=re.M):
        v = m.group(2)
        consts[m.group(1)] = int(v) if re.fullmatch(r"-?\d+", v) else v
    return consts


# ------------------------------------------------------------------ spec state -> Python objects

def claims_from(state: dict) -> list[Claim]:
    out = []
    for k, c in state["cl"].items():
        if c["st"] == "NONE":
            continue
        if c["tmpl"] == "U":
            out.append(Claim.untestable(claim_id=k, counterparty=c["sup"], source_msg_hash="tlc",
                                        created_round=c["created"]))
            continue
        if c["tmpl"] == "D":
            base = Claim.make(claim_id=k, counterparty=c["sup"], source_msg_hash="tlc", created_round=c["created"],
                              template="DELIVERY", slots={"item": "widget", "qty": c["qty"], "by_round": c["by"]})
        else:
            base = Claim.make(claim_id=k, counterparty=c["sup"], source_msg_hash="tlc", created_round=c["created"],
                              template="PRICE", slots={"item": "widget", "unit_price": Decimal(1), "valid_until": c["by"]})
        base = with_item(base, ITEM[c["item"]])
        out.append(base.model_copy(update={
            "status": c["st"], "consumed": c["consumed"], "realized_exposure": Decimal(c["exposure"]),
            "resolved_round": None if c["st"] == "PENDING" else c["resolved"]}))
    return out


def order_action(o: str, r: dict) -> Action:
    a = Action(action_id=o, kind="ORDER", counterparty=r["sup"], qty=r["qty"], unit_price=Decimal(1),
               value=Decimal(r["qty"]), cited_claims=tuple(sorted(r["cites"])), round=r["round"])
    upd = {"item": ITEM[r["item"]], "status": r["st"]}
    if r["exec"]:
        upd["executed_round"] = r["round"]
    return a.model_copy(update=upd)


def pay_action(p: str, r: dict, now: int) -> Action:
    a = Action(action_id=p, kind="PAYMENT", counterparty=r["sup"], value=Decimal(r["amount"]),
               cited_claims=tuple(sorted(r["cites"])), round=now,
               ref_order=None if r["ref"] == "NoRef" else r["ref"])
    upd = {"status": r["st"]}
    if r["exec"]:
        upd["executed_round"] = now
    return a.model_copy(update=upd)


def actions_from(state: dict) -> list[Action]:
    acts = [order_action(o, r) for o, r in state["od"].items() if r["st"] != "NONE"]
    acts += [pay_action(p, r, state["now"]) for p, r in state["py"].items() if r["st"] != "NONE"]
    return acts


# ------------------------------------------------------------------ replay

def decisions(states: list[dict]):
    """Yield (pre-state, kind, id, spec_allowed) for every gate step in a trace."""
    for s, t in zip(states, states[1:]):
        if s["phase"] != "gate":
            continue
        for o, r in s["od"].items():
            if r["st"] == "PROPOSED" and t["od"][o]["st"] in ("EXECUTED", "BLOCKED"):
                yield s, "ORDER", o, t["od"][o]["st"] == "EXECUTED"
        for p, r in s["py"].items():
            if r["st"] == "PROPOSED" and t["py"][p]["st"] in ("EXECUTED", "BLOCKED"):
                yield s, "PAYMENT", p, t["py"][p]["st"] == "EXECUTED"


def replay_state(s: dict, kind: str, ident: str, consts: dict) -> tuple[bool, str, str]:
    """Python gate and monitor verdicts on one spec pre-state: (gate_allowed, gate_reason, monitor_reason)."""
    acts = actions_from(s)
    target = next(a for a in acts if a.action_id == ident and a.kind == kind)
    others = [a for a in acts if a is not target]
    sups = set(s["made"])
    gate = build_world(claims_from(s), others, b0=Decimal(consts["B0"]), window=int(consts["W"]),
                       min_lead={sup: int(consts["MinLead"]) for sup in sups}, k=int(consts.get("K", 1)))
    ok, why = gate.allow(target, s["now"])
    _, mwhy = table_verdict(snapshot(gate, target, s["now"]))
    return ok, why, mwhy


def new_stats() -> dict:
    return {"traces": 0, "traces_with_decisions": 0, "traces_to_final_round": 0, "states": 0, "decisions": 0,
            "mismatches": [],
            "reasons": Counter(), "spec_verdicts": Counter()}


def replay_dir(trace_dir: Path, cfg: Path, stats: dict | None = None, prune: bool = False) -> dict:
    consts = parse_cfg(cfg.read_text())
    files = sorted(p for p in trace_dir.iterdir() if p.name.startswith("trace"))
    stats = stats if stats is not None else new_stats()
    for f in files:
        states = parse_trace(f.read_text())
        stats["traces"] += 1
        stats["states"] += len(states)
        # Ran to the spec's terminal step (final round's execute), not cut short by a deadlock.
        stats["traces_to_final_round"] += (states[-1]["now"] == consts.get("MaxRound")
                                           and states[-1]["phase"] == "execute")
        found = list(decisions(states))
        stats["traces_with_decisions"] += bool(found)
        if prune and not found:
            f.unlink()
        for s, kind, ident, spec_ok in found:
            ok, why, mwhy = replay_state(s, kind, ident, consts)
            stats["decisions"] += 1
            stats["reasons"][f"{kind}:{why}"] += 1
            stats["spec_verdicts"]["EXECUTED" if spec_ok else "BLOCKED"] += 1
            if ok != spec_ok or why != mwhy:
                stats["mismatches"].append({"trace": f.name, "round": s["now"], "kind": kind, "id": ident,
                                            "spec": spec_ok, "gate": (ok, why), "monitor": mwhy})
    return stats


SPEC = Path(__file__).resolve().parent
FULL_CFG = SPEC / "results" / "full_partial" / "full_none.cfg"


def campaign_cfg(mode: str, mutant: str) -> str:
    """Full bounds, no symmetry (irrelevant to simulation). A mutant checks no properties (negative control)."""
    lines = []
    for line in FULL_CFG.read_text().splitlines():
        if line.startswith("SYMMETRY"):
            continue
        if line.startswith("SPECIFICATION") and mode == "guided":
            line = "SPECIFICATION GuidedSpec"
        if mutant != "none" and line.split(" ")[0] in ("INVARIANT", "PROPERTY") and "TypeOK" not in line:
            continue
        lines.append(line.replace('MUTANT = "none"', f'MUTANT = "{mutant}"'))
    return "\n".join(lines) + "\n"


def campaign(mode: str, mutant: str, min_traces: int, min_decisions: int, seed: int, out: Path,
             batch: int = 1000, max_batches: int = 60) -> dict:
    java = next(iter(sorted((SPEC.parent / "tools").glob("jdk-*/Contents/Home/bin/java"))), "java")
    work = SPEC / "states" / "replay" / f"{mode}_{mutant}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    cfg = work / "sim.cfg"
    cfg.write_text(campaign_cfg(mode, mutant))
    stats, seeds = new_stats(), []
    for b in range(max_batches):
        if stats["traces"] >= min_traces and stats["decisions"] >= min_decisions:
            break
        d = work / f"batch{b:03d}"
        d.mkdir()
        seeds.append(seed + b)
        r = subprocess.run([str(java), "-Xmx4g", "-cp", str(SPEC / "tla2tools.jar"), "tlc2.TLC", "-simulate",
                            f"file={d}/trace,num={batch}", "-depth", "500", "-seed", str(seed + b),
                            "-workers", "1", "-deadlock", "-metadir", str(work / "meta"), "-config", str(cfg),
                            "MCsim.tla"], cwd=SPEC, capture_output=True, text=True)
        if mutant == "none" and ("is violated" in r.stdout or r.returncode != 0):
            raise SystemExit(f"TLC reported a problem in batch {b}:\n{r.stdout[-3000:]}")
        replay_dir(d, cfg, stats, prune=True)
    summary = {"mode": mode, "mutant": mutant, "seeds": seeds, "batch": batch,
               "avg_trace_length": round(stats["states"] / max(1, stats["traces"]), 2),
               "tlc_cfg": cfg.read_text(), **{k: v for k, v in stats.items() if k != "mismatches"},
               "reasons": dict(sorted(stats["reasons"].items())), "spec_verdicts": dict(stats["spec_verdicts"]),
               "mismatch_count": len(stats["mismatches"]), "mismatch_examples": stats["mismatches"][:10]}
    out.write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main(argv: list[str]) -> int:
    if argv[1] == "campaign":
        mode, mutant = argv[2], argv[3]
        st = campaign(mode, mutant, int(argv[4]), int(argv[5]), int(argv[6]), Path(argv[7]))
        print(json.dumps({k: st[k] for k in ("mode", "mutant", "traces", "traces_with_decisions", "decisions",
                                             "spec_verdicts", "reasons", "mismatch_count")}, indent=1))
        return int(st["mismatch_count"] > 0) if mutant == "none" else int(st["mismatch_count"] == 0)
    trace_dir, cfg = Path(argv[1]), Path(argv[2])
    st = replay_dir(trace_dir, cfg)
    print(f"traces replayed:     {st['traces']}")
    print(f"states parsed:       {st['states']}")
    print(f"gate decisions:      {st['decisions']}  (spec: {dict(st['spec_verdicts'])})")
    print("python reason codes: " + ", ".join(f"{k} {v}" for k, v in sorted(st["reasons"].items())))
    print(f"mismatches:          {len(st['mismatches'])}")
    for m in st["mismatches"][:20]:
        print("  ", m)
    return 1 if st["mismatches"] or st["decisions"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
