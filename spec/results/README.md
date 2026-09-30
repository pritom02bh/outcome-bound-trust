# Model-checking evidence for `spec/OBT.tla` (FIXES F6)

Everything here was produced by the committed spec and scripts. Nothing was edited by hand except the three N/A rows in `fallbackA2_summary.txt` (see config A′ below).

**Environment.**
- TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802); `tla2tools.jar` sha256 `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`.
- OpenJDK 21.0.12.1 (Temurin, portable), `-XX:+UseParallelGC -Xmx12g`, `-workers auto` (10).
- Apple arm64, 10 cores.

**Symmetry.** All exhaustive runs use `SYMMETRY Symm`, with `Symm == Permutations(Claims) ∪ Permutations(Orders) ∪ Permutations(Pays)`. It is sound here for three reasons:
- Every checked property is a safety property.
- Every id is a model value. The only id-typed sentinel, `NoRef`, is a model value outside the permuted sets, which an `ASSUME` enforces.
- No step tells ids apart: fresh ids are chosen with `\E`, and earliest-deadline ties are nondeterministic.

Tier 2 below checks this empirically.

## What is and is not claimed

- **Claimed:** exhaustive verification of I1–I4, I6 and I7 (I1–I3 as action properties, I4, I6, I7 and TypeOK as invariants) at three bounded configs:
  - **quick:** 1 supplier, 1 item, 3 rounds.
  - **A′:** 2 suppliers, 1 item, 2 rounds.
  - **B:** 1 supplier, 2 items, 3 rounds.

  In addition, every guard mutant that can act at a config's bounds is caught there.
- **Budget growth multiplier K (D36).** All of the above is at K = 1. K = 2 also passes at quick and A′, with every applicable mutant caught, but those bounds can't tell K = 2 from K = 1 (the probe below). So **K > 1 is not claimed as verified** at any bound.
- **Not claimed:** exhaustive verification at the full bounds (2 suppliers, 2 items, 6 rounds), or at config A (2 suppliers, 1 item, 3 rounds). Neither exhaustive search finished. Both are reported below as partial, non-exhaustive evidence.
- **Two-supplier behavior over 3+ rounds is not covered by a completed exhaustive search.** It is covered by:
  - the partial exhaustive run of config A (547M states, 0 violations);
  - the mutants caught at A′, including the cross-supplier mutants XSUP-RECEIPT and XSUP-BUDGET;
  - the 1-hour full-bounds simulation;
  - spec–code trace replay.

## Tier 1: exhaustive checks

Common constants: `Claims = {k1, k2, k3}`, `Orders = {o1, o2}`, `Pays = {p1}`, `Notes = {n1}`, `W = 1`, `K = 1` (see the K section below), `NoRef = NoRef`, symmetry as above. No state constraints.

| config | Sups | Items | MaxRound | B0 | MinLead | unmutated result | distinct states | depth | runtime |
|---|---|---|---|---|---|---|---|---|---|
| quick | {s1} | {i1} | 3 | 2 | 1 | **PASS**, no error | 55,007,884 | 30 | 168 s |
| A′ | {s1, s2} | {i1} | 2 | 2 | 1 | **PASS**, no error | 116,548,616 | 22 | 373 s |
| B | {s1} | {i1, i2} | 3 | 2 | 1 | **PASS**, no error | 1,314,397,838 | 30 | 7,407 s wall, incl. 2,316 s host sleep |

### Mutants

Each mutant removes exactly one enforcing guard. TLC must report a violation of the named property.

| mutant | guard removed | must violate |
|---|---|---|
| I1 | budget row `P + inc ≤ B` | I1 |
| I2 | D3 cool-down floor (passes during the cool-down count) | I2 |
| I4 | same-step flagging (flags only in a later round) | I4 |
| I6 | OVER_CLAIM row and capped consumption | I6 |
| I7 | allocation doesn't subtract credited units | I7 |
| ITEM | same-item binding: order vs every cited claim (D18) | I1 (I1 re-checks the full table) |
| XSUP-RECEIPT | allocation ignores the supplier | I7 |
| XSUP-BUDGET | a PASSED claim earns budget for every supplier | I2 |

Results: violated property, distinct states when TLC stopped, counterexample length and runtime. With `-workers auto` the first counterexample found depends on worker scheduling, so a caught mutant's state count and length vary between reruns (the K = 1 reruns below differ by up to 20%). The verdicts don't vary, and neither do the counts of exhaustive (PASS) runs.

| mutant | quick | A′ | B |
|---|---|---|---|
| I1 | caught I1 · 1,397,603 · 23 · 5 s | caught I1 · 24,189,963 · 21 · 87 s | caught I1 · 26,863,525 · 24 · 85 s |
| I2 | caught I2 · 2,095,684 · 25 · 8 s | N/A (1) | caught I2 · 24,278,086 · 24 · 77 s |
| I4 | caught I4 · 21,483 · 19 · 1 s | caught I4 · 698,266 · 18 · 5 s | caught I4 · 118,525 · 19 · 2 s |
| I6 | caught I6 · 1,470 · 13 · 1 s | caught I6 · 12,760 · 13 · 2 s | caught I6 · 6,339 · 13 · 1 s |
| I7 | caught I7 · 6,247,777 · 28 · 20 s | N/A (2) | caught I7 · 155,337,457 · 29 · 561 s |
| ITEM | PASS (no-op, 1 item) | N/A (3) | caught I1 · 5,691 · 13 · 1 s |
| XSUP-RECEIPT | PASS (no-op, 1 supplier) | caught I7 · 420,452 · 17 · 3 s | PASS (no-op) · 1,314,397,838 · 30 · 5,500 s wall, incl. 485 s sleep |
| XSUP-BUDGET | PASS (no-op, 1 supplier) | caught I2 · 445,466 · 16 · 3 s | PASS (no-op) · 1,314,397,838 · 30 · 4,976 s |

**Runtimes are wall-clock.** The host slept during three runs, detected as gaps longer than 150 s between TLC's once-a-minute progress lines: B unmutated (2,316 s), B XSUP-RECEIPT (485 s), and quick ITEM in the slow-test rerun (2,374 s + 3,098 s; its summary row says 6,758 s). Sleep pauses TLC; state counts, depths and verdicts are unaffected. The 1-hour simulation has no gaps.

"No-op" means the mutant can't act at those bounds. It must then behave exactly like the real spec, and it does: the same distinct-state count as the unmutated run.

**Not applicable at A′ (unreachable at these bounds).** These three mutants were not run at A′. The cap watchdog stopped each within seconds (`fallbackA2_caps.log`); the stub outputs are in `aborted/a2_na/`.
1. **I2** needs a failure and then the cool-down to expire, so at least 3 rounds. It is caught in quick and B. Its cross-supplier form is XSUP-BUDGET, caught at A′.
2. **I7** needs 3 PENDING claims at one supplier (two DELIVERY + one PRICE), and a supplier makes at most 2 claims per round, so it needs 3 rounds. It is caught in quick and B. Its cross-supplier form is XSUP-RECEIPT, caught at A′.
3. **ITEM** can't act with one item. It is caught in B.

Caps at A′: 3 hours for the unmutated run and 30 minutes per mutant. No run reached its cap. A′'s unmutated run finished in 373 s.

### Partial exhaustive runs: non-exhaustive evidence only

| run | bounds | stopped after | depth | distinct states | queue at stop | violations |
|---|---|---|---|---|---|---|
| config A (`fallbackA_partial/`) | 2 sups, 1 item, **3 rounds**, B0 2, MinLead 1 | 39 min | 30 | 547,083,101 | 188,641,957 (growing) | 0 |
| full bounds (`full_partial/`) | 2 sups, 2 items, 6 rounds, B0 1, MinLead 2 | 39 min | 23 | 415,521,614 | 354,081,841 (growing) | 0 |

Both were stopped by decision, because their queues kept growing. They predate later spec changes: see each `NOTES.txt` for D18 (strict item binding) and D20 (strengthened I7).

**Why A′ uses 2 rounds (DECISIONS D20).** Keeping 3 rounds and capping live claims at 2 per supplier makes I7 unreachable, and it shrank the state space by only about 30%. A cap of 3 does nothing with a 3-id pool. The Claims and Orders pools are already at the minimum that I7 and I1 need. Dropping past-round receipt history saved 1%. So A′ keeps two suppliers and drops to 2 rounds, with no state constraint.

## Tier 2: symmetry cross-check (`symmetry_crosscheck.txt`)

The same specs were run to completion with and without symmetry:
- tier 1: tiny bounds (1 supplier, 1 item, 2 rounds), all 9 specs;
- tier 2: I2 and I7 at quick bounds, where they can act.

**All 11 verdict pairs match.** At tiny bounds, symmetry cuts the unmutated state space 5.9× (3,836,186 vs 22,587,486 distinct states).

## Tier 3: random simulation at the full bounds (`simulation_full.txt`)

- **Run:** TLC `-simulate` of the unmutated spec at 2 suppliers, 2 items, 6 rounds (B0 1, MinLead 2), seed 20260925, no symmetry.
- **Checks:** every invariant and action property, on every state of every trace.
- **Result:** 102,272 traces, and every one ran to the final round. TLC's "states checked" counter reads 949,168,936. Maximum trace depth was 53, runtime 3,349 s, **0 violations**.
- **How the length was set:** TLC 2.19 has no time limit in simulation mode. So a 5,000-trace pilot (176 s) set `num` to fill about an hour.

This is random evidence at the realistic size, not exhaustive verification.

## Conformance: gate, monitor and spec use the same rule

**Differential test, gate vs runtime monitor** (`tests/test_conformance.py`).
- **Inputs:** hypothesis generates random ledgers, action logs and proposed actions. They include wrong items, unknown ids, every claim status, over-capacity and over-budget orders, overpayments, and ±1-cent offsets at every money boundary.
- **Check:** on every input, `Gate.allow` and `monitor.table_verdict` return the same reason code.
- **Size:** 10,000 examples in the slow suite, 400 in the default suite. A coverage guard requires all 10 reason codes to come up.
- **What it found:** a tolerance drift. The monitor used 1e-6 where the gate used 1e-9. That led to exact Decimal money (DECISIONS D19).

**Spec–code trace replay** (`replay/`, `spec/replay.py`, `spec/run_replay.sh`).
- **Method:** each TLC trace is parsed. Every gate decision's pre-state is rebuilt as Python objects: ledger, action log and budget. Then the Python gate and the monitor must agree with the spec's EXECUTED/BLOCKED verdict. Both sides use exact integer money.
- **Sampling:** the traces come from separate `-simulate file=` runs at the full bounds with fixed seeds. The 1-hour run can only dump every trace, which would be millions of files.
- **Guided traces:** `MCsim.tla`'s `GuidedSpec` only restricts the spec's behaviors, never adds any. Suppliers send DELIVERY + PRICE offer pairs, and the buyer cites PENDING claims of the order's own supplier and item. Without it, uniform traces almost never reach the allow, capacity, budget and payment rows.
- **Controls:** mutant campaigns run with TLC's property checks off, so the mutated gate keeps running and the replay has to report the disagreement.

| campaign | traces | reach final round | avg trace length | gate decisions | spec EXECUTED | mismatches |
|---|---|---|---|---|---|---|
| uniform, unmutated | 1,000 | 1,000 | 52.95 | 2,002 | 3 | **0** |
| guided, unmutated | 1,000 | 1,000 | 52.02 | 1,021 | 223 | **0** |
| control: guided, I1 mutant | 3,000 | 3,000 | 52.14 | 3,415 | 941 | 241 (detected) |
| control: uniform, ITEM mutant | 5,000 | 5,000 | 52.95 | 10,008 | 10 | 7 (detected) |

Python reason codes reached in the unmutated campaigns:
- **Uniform:** NO_CITATION, UNKNOWN_CLAIM, WRONG_COUNTERPARTY, BAD_CLAIM, CLAIM_MISMATCH, PRICE_MISMATCH, OVER_CLAIM, OVER_BUDGET, OK, OVERPAY.
- **Guided:** CLAIM_MISMATCH, PRICE_MISMATCH, OVER_CLAIM, OVER_BUDGET, OK, OVERPAY, and payment BAD_CLAIM.

No trace ended early from deadlock: every trace reached the final round's execute step.

## Budget growth multiplier K (DECISIONS D36, D36a)

`OBT.tla` now takes `K` as a constant: `Bud(s) = B0 + K * MaxOf(earned)`, with `ASSUME K \in Nat \ {0}`. `run_mutants.sh` reads `K` from the environment (default 1); K ≠ 1 tags its outputs `<bounds>_k<K>_*`. `run_k2.sh` runs everything in this section.

**K = 1 reproduces the committed results** (`k1_repro/`). Every verdict is identical, and the exhaustive runs match exactly:

| config | unmutated, committed | unmutated, K = 1 rerun | verdicts |
|---|---|---|---|
| quick | 55,007,884 states · depth 30 | 55,007,884 · 30 | 9/9 identical (ITEM, XSUP-* no-op PASS at 55,007,884 · 30) |
| A′ | 116,548,616 · 22 | 116,548,616 · 22 | 9/9 identical (3 N/A) |

The caught mutants' counterexample counts differ from the committed ones, as expected under `-workers auto` (see Mutants above). For example, quick I1 went from 1,397,603 · 23 to 1,338,745 · 24, and A′ I1 from 24,189,963 · 21 to 19,395,933 · 21.

**K = 2** (`quick_k2_*`, `fallbackA2_k2_*`). All pass, and every applicable mutant is caught.

| mutant | quick, K = 2 | A′, K = 2 |
|---|---|---|
| none | **PASS** · 55,007,884 · 30 · 252 s | **PASS** · 116,548,616 · 22 · 542 s |
| I1 | caught I1 · 1,449,810 · 24 · 8 s | caught I1 · 22,323,315 · 21 · 119 s |
| I2 | caught I2 · 2,072,406 · 24 · 10 s | N/A (1) |
| I4 | caught I4 · 20,273 · 19 · 2 s | caught I4 · 711,192 · 18 · 7 s |
| I6 | caught I6 · 2,515 · 13 · 0 s | caught I6 · 14,451 · 12 · 1 s |
| I7 | caught I7 · 6,633,047 · 28 · 34 s | N/A (2) |
| ITEM | PASS (no-op) · 55,007,884 · 30 · 248 s | N/A (3) |
| XSUP-RECEIPT | PASS (no-op) · 55,007,884 · 30 · 240 s | caught I7 · 442,523 · 16 · 5 s |
| XSUP-BUDGET | PASS (no-op) · 55,007,884 · 30 · 253 s | caught I2 · 373,240 · 16 · 4 s |

Runtimes are wall-clock, on a host that was also running the E3b LLM runs (ollama). That is why the K = 1 reruns were also slower than the committed runs, for example 217 s vs 168 s at quick. No host sleep occurred.

**At these bounds K = 2 checks nothing that K = 1 doesn't.** The K = 2 state spaces are identical to K = 1's, and a probe shows why (`k_probe/`). The probe is `OBT.tla` plus two scratch invariants, run at K = 1:

| probe invariant | meaning | quick | A′ |
|---|---|---|---|
| `NoEarned` | no supplier ever has earned trust | **violated** (11,349 states) | **violated** (434,601 states) |
| `KNeverDecides` | no order or payment is ever judged OVER_BUDGET while its supplier's earned term is > 0 | **holds**, exhaustive (55,007,884) | **holds**, exhaustive (116,548,616) |

So earned trust does arise, but once it has, the budget never binds. Only order ids {o1, o2} exist, and an order is 1–2 units, so too little pending exposure is left to exceed B0 + earned. K scales only the earned term, so it can't change any gate decision at these bounds, for any K ≥ 1.

**What is verified:**
- K = 1: exhaustive at quick, A′ and B.
- K = 2: exhaustive at quick and A′, but vacuously, since the configurations are behaviorally the same as K = 1.
- **No bound has yet exercised K > 1 where it matters.** That needs bounds at which `KNeverDecides` is violated. B0 = 1 at the quick and A′ bounds gives such a witness (`k_probe/candidates/`); a third order id found none within 10 minutes. See DECISIONS D36a, which is open. B was not rerun at K = 2 (too slow, per the request) and was not probed.

## Coverage: invariant by evidence

"PASS" means the unmutated spec satisfies the property exhaustively at that config. "caught X" means that config's mutant for it is caught (as property X).

| invariant | quick (1s, 1i, 3r) | A′ (2s, 1i, 2r) | B (1s, 2i, 3r) | full bounds (2s, 2i, 6r) | other |
|---|---|---|---|---|---|
| I1 gate safety | PASS; caught I1 | PASS; caught I1 | PASS; caught I1, ITEM (item binding) | simulation 0 violations; replay 0 mismatches (I1 control detected) | runtime monitor; differential test 10k |
| I2 earned trust | PASS; caught I2 | PASS; I2 N/A (needs 3 rounds); **XSUP-BUDGET caught** | PASS; caught I2 | simulation 0 violations | runtime monitor + tamper test |
| I3 ledger integrity | PASS | PASS | PASS | simulation 0 violations | no spec mutant: the verifier-only capability is structural (`Ledger.bind_verifier`); runtime monitor + tamper test |
| I4 propagation | PASS; caught I4 | PASS; caught I4 | PASS; caught I4 | simulation 0 violations | runtime monitor + tamper test |
| I5 context isolation | — | — | — | — | unit tests only (`tests/test_extractor_view.py`) |
| I6 capacity | PASS; caught I6 | PASS; caught I6 | PASS; caught I6 | simulation 0 violations | runtime monitor + tamper test |
| I7 receipt uniqueness (incl. supplier/item match, D20) | PASS; caught I7 | PASS; I7 N/A (needs 3 rounds); **XSUP-RECEIPT caught** | PASS; caught I7 | simulation 0 violations | runtime monitor + two tamper tests |
| two suppliers, 3+ rounds | — | — | — | simulation, replay | config A partial: 547M states, 0 violations. **No completed exhaustive search.** |

## Reproduce

```
spec/run_mutants.sh quick|fallbackA2|fallbackB|tiny     # SYM=0 disables symmetry; ONLY="I2 I7" runs a subset; K=2 sets the multiplier
spec/run_k2.sh                                           # K = 1 reproduction check + K = 2 at quick and A′ (D36)
python -m spec.make_crosscheck                           # after tiny, SYM=0 tiny, and ONLY="I2 I7" quick with/without SYM
spec/run_replay.sh                                       # replay campaigns -> replay/
spec/run_simulation.sh 102272 20260925                   # full-bounds simulation -> simulation_full.*
pytest -m slow                                           # quick bounds + ITEM at B + XSUP at A′, and the 10k differential test
```

`aborted/` keeps superseded outputs from earlier spec and harness versions, each in its own folder. None of them is reported above.
