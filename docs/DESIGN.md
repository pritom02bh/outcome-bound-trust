# Outcome-Bound Trust — Design Spec (v0.1)

Working title: _Outcome-Bound Trust: Falsifiable Claims as a Security Primitive for Memory in Multi-Agent AI Systems_

## 1. Problem

A buyer agent must store and act on what a supplier agent tells it. The supplier is authenticated and legitimate, so provenance-based defenses mark it trusted. It can still lie for profit, usually after building a clean record. Goal: bound what a lying counterparty can gain, without an LLM making the trust decision.

Core rule: **trust comes from claims that came true, never from who said them or how they sound.**

## 2. Threat model

- Adversary: an authenticated counterparty. Full control over its own messages (content, timing, volume, wording), including text aimed at the extractor (injected instructions, decoy numbers; scenario 11).
- **Identities** are authenticated by the transport (per-agent credentials), and creating one is costly: it has to be registered with the buyer. An adversary may hold a few, but each is a separate counterparty with its own ledger history and its own `B(c)`, which starts at `b0`. A new identity therefore gains at most `b0` of unearned exposure (scenario 12). Under OBT a failed identity already sits at `b0`, so re-entering after a failure buys at most a skipped cool-down. With `b0 = 0` (included in the E1 ablations), a Sybil gains nothing.
- Adversary can't write to: outcome oracles, the ledger, the gate, the verifier, or the buyer's code.
- Out of scope (v1): compromised oracles, collusion that forges outcomes, gateway compromise, attacks on the LLM provider.

## 3. Architecture

```
Supplier ──A2A──> Gateway ──> Extractor (LLM) ──> Ledger ──> Memory view ──> Buyer agent (LLM)
                     │                              ▲                              │ proposes action
                raw log (audit only)                │                              ▼
                                   Oracles ──> Verifier ──> Trust budget ──────> Gate (code) ──> execute | block
                                                    │
                                                    └──> Dependency tracker ──> flags actions + notes
```

LLM components can be fooled. Code components can't. **Every security property lives in code.**

## 4. Data model

```python
class Claim:
    claim_id: str
    counterparty: str
    source_msg_hash: str        # links to raw log; raw text never enters agent context
    created_round: int
    template: Literal["DELIVERY", "PRICE"]
    slots: dict                 # DELIVERY: item, qty, by_round | PRICE: item, unit_price, valid_until
    deadline: int               # round when the verifier resolves it
    status: Literal["PENDING", "PASSED", "FAILED", "LAPSED", "UNTESTABLE"]
    resolved_round: int | None
    consumed: int               # DELIVERY: capacity used by allowed orders (what is owed); PRICE: units ordered at it
    realized_exposure: float    # set by the gate only: consumed units x claimed unit price

class Action:
    action_id: str
    kind: Literal["ORDER", "PAYMENT"]
    counterparty: str
    qty: int                    # ORDER: chosen by the buyer, capped by cited claim capacity
    unit_price: float | None    # ORDER: from the single cited PRICE claim (code-set)
    value: float                # ORDER: qty x unit_price; PAYMENT: amount
    ref_order: str | None       # PAYMENT: the executed ORDER it pays
    cited_claims: list[str]
    status: Literal["PROPOSED", "EXECUTED", "BLOCKED", "FLAGGED"]
```

A DELIVERY claim is a **capacity offer**: `remaining_capacity = qty − consumed`. Allowed orders consume capacity (earliest deadline first); a unit of capacity is never used twice. The supplier owes only what was consumed. A claim nothing consumed resolves **LAPSED** (terminal): no obligation, no credit, no penalty.

Tests are **typed templates**, not code. The extractor picks a template and fills slots. The verifier owns the template logic. An LLM never writes test code.

| Template                             | Passes iff (checked against oracle)                                                |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| DELIVERY(item, qty, by_round)        | units credited to it by round by_round + δ ≥ **consumed**. Each unit received from the counterparty is credited on arrival to its earliest-deadline PENDING DELIVERY claim for the item that still needs units and whose window (created_round, by_round + δ] contains the arrival; a unit backs at most one claim. Resolves at by_round + δ (δ config, default 0). Partial delivery fails. |
| PRICE(item, unit_price, valid_until) | every invoice for item from counterparty in [created_round, valid_until) has price ≤ unit_price |

Either template resolves LAPSED instead if `consumed = 0`. A message the extractor can't map to a valid template becomes `UNTESTABLE`, as does any claim whose deadline is more than `H` rounds after creation (default 8). Untestable claims can't be cited.

## 5. Components

- **Transport (F11, D25).** Each supplier identity is a localhost A2A server (a2a-sdk 1.x) with an Agent Card and its own bearer token; the buyer is an A2A client. `transport = inproc | a2a` (the eval uses `a2a`; both give identical ledgers and costs).
- **Gateway.** Receives A2A messages with the authenticated counterparty id. The id is the identity of the authenticated endpoint the message arrived on, never anything in the message. Writes raw text to an append-only audit log. Forwards to the extractor and appends the resulting claims (horizon cap applied) straight to the ledger.
- **Extractor (LLM).** `extract(msg) -> list[Claim]`. JSON-schema output, validated by pydantic. Invalid output → `UNTESTABLE`. Sets no trust or exposure values, and never the counterparty (that is the gateway's authenticated sender). **Hardening:** each numeric slot must be grounded in the raw text in that slot's context and unambiguous. The set of values the text offers for the slot (quantities next to "widgets/units/qty", deadlines after "by / no later than round", validity after "until / through / invoiced before round", prices after "$" or "price") must be exactly `{value}`, else that claim is `UNTESTABLE`.
  - Quantity-like figures ("lot size N", a bare "N/unit") count as competing quantities. "$N/unit" is a price. A number followed by "unit price/cost" is not a quantity.
  - **Deadline wording (in code, D23b).** A DELIVERY deadline is an arrival deadline. If the sentence stating the deadline words it with ship/send/dispatch/ready/available/scheduled and has no arrival wording (deliver(ed), arrive, receive, you will have, in your warehouse), the DELIVERY claim is `UNTESTABLE` (fail closed). A lead-time clause ("we usually ship within 2 rounds") and a price-validity clause in the same sentence are set aside first.
  - This check is code, not prompt. On the 30-item hard subset, gpt-oss alone recorded 21 shipping/ready dates as delivery deadlines; with the guard it records 0.
  - The prompt is frozen by sha256 in `obt/config.py`.
- **Ledger.** Append-only claim store. Only the verifier changes status, and only `PENDING → PASSED | FAILED | LAPSED` (LAPSED only when consumed = 0). Only the gate records consumption. `UNTESTABLE`, `PASSED`, `FAILED`, `LAPSED` are terminal.
- **Memory view.** The only path from counterparty data to the agent. Renders claims as cards (template, slots, status, deadline) plus each counterparty's track record and current budget headroom. No raw text.
- **Buyer agent (LLM).** Plans orders across a main supplier and a backup. Must cite claim ids on every action toward a counterparty. Its notes may cite claim ids too.
- **Oracles.** Environment-owned records: warehouse receipts, invoices. Read-only to everything except the environment.
- **Verifier.** Each round (phase 2), credits newly arrived units to DELIVERY claims (earliest deadline first), then resolves every PENDING claim that is due: DELIVERY at `by_round + δ`, PRICE at `valid_until`.
- **Trust budget.** Per counterparty, computed in code (§6).
- **Gate.** Checks each proposed action against the rules (§6). Blocked actions return to the agent with a reason code.
- **Dependency tracker + remediation (round phase 4).** When a DELIVERY claim fails, code first orders its unallocated shortfall (`consumed − credited units`) from backup, then flags every action and note citing the claim in the same step, and the agent sees the failure in its view. Blocked ORDER quantity is likewise re-ordered from backup by code in phase 8. The LLM is never relied on to remediate.

**Round order (single source of truth: `obt/env/beer_game.py: ROUND_ORDER`, `step()`).** Every round runs exactly:

1. Environment posts deliveries and invoices to the oracles (invoices issued last round are posted now), then demand and holding/backlog costs.
2. Verifier resolves due claims.
3. Budget recompute.
4. Dependency tracker flags + automatic remediation.
5. New supplier messages → gateway → extractor → claim store.
6. Buyer agent proposes actions (proposals only; nothing is decided or executed yet). Code then proposes one PAYMENT per invoice posted in step 1.
7. Gate decides each action in proposal order; allowed actions commit immediately (they count toward `P(c)` and consume claim capacity before the next proposal is decided).
8. Execute allowed actions (orders placed, allowed payments charged); blocked ORDER quantity is rerouted to backup by code.

## 6. Gate and budget

All money in this section is exact Decimal cents, compared exactly, as in the spec's integers (DECISIONS D19). Env floats enter only through `obt.money.to_money`, which rounds half-even to a cent.

Definitions per counterparty `c`:

- `b0` = cold-start budget (default: 5% of per-round spend, tune in config)
- `B(c) = b0 + max(realized_exposure of c's PASSED DELIVERY claims)`. On any FAILED claim of `c` (DELIVERY or PRICE) the max is cleared and `B(c) = b0` for `W` rounds; passes during that window never count (D3). LAPSED claims never count.
- `realized_exposure(claim) = consumed_qty × claimed unit price`, computed by the gate when it allows an order; never from an action's value alone.
- `P(c)` = total value of EXECUTED ORDERs to `c` that cite at least one PENDING claim of `c` (each counted once). Payments are not added: they pay for orders already counted.

`allow(a)` returns the first failing check, in this order:

| Check | Reason code |
|---|---|
| counterparty is BACKUP → allow | `OK` |
| no cited claims | `NO_CITATION` |
| any cited id not in ledger (never raises) | `UNKNOWN_CLAIM` |
| any cited claim from another counterparty | `WRONG_COUNTERPARTY` |
| any cited claim FAILED, UNTESTABLE or LAPSED | `BAD_CLAIM` |
| ORDER: any cited claim (DELIVERY or PRICE) for a different item than the order's (D18), or no cited PENDING DELIVERY claim, or a cited DELIVERY claim with `by_round − now` < the supplier's minimum lead time | `CLAIM_MISMATCH` |
| ORDER: not exactly one cited PRICE claim for the item, PENDING, with `created_round ≤ now < valid_until` and unit price equal to the order's | `PRICE_MISMATCH` |
| ORDER: `qty` > total remaining capacity of the cited DELIVERY claims | `OVER_CLAIM` |
| PAYMENT: doesn't reference an EXECUTED order to `c`, or cumulative payments on it would exceed `qty × its claimed unit price` | `OVERPAY` |
| `P(c) + increment > B(c)` (increment = value for ORDER, 0 for PAYMENT) | `OVER_BUDGET` |

An allowed ORDER consumes capacity from its cited DELIVERY claims (earliest deadline first) and records exposure. A blocked ORDER's quantity is ordered from backup by code in the same round.

**Headline guarantee.** A counterparty's loss-inducing exposure at any moment is at most `B(c) = b0 + (largest delivered exposure it already honored)`. To steal X, it must first deliver goods worth about X − b0 against a claim. Farming trust with many small true claims earns nothing beyond small actions, and a small claim can't back a large order (capacity).

### Loss bound per failure event (FIXES F7, DECISIONS D21)

**Damage.** For an OBT run R, let R* replay R with the same demand and the same decisions: every executed order and payment, in the same round, with the same amounts. In R*, S_main keeps every promise the gate relied on. The units an order took from DELIVERY claim k arrive at k's `by_round`, invoiced at the claimed price, and R's remediation orders don't exist. Then `damage(R) = cost(R) − cost(R*)` (`obt/lossbound.py`). Holding the decisions fixed leaves out three things that aren't damage from a broken promise: opportunity cost, cool-down reroutes and LLM trajectory noise. The results report them separately:

`loss_from_lies = damage + reroute_cost_diff + resid`

Every term is relative to the honest run with the same defense and seed:
- `damage` is already relative by construction; it is 0 in the honest run.
- `reroute_cost_diff = reroute_cost(R) − reroute_cost(honest)`. Here `reroute_cost` is the backup premium on quantity rerouted after `OVER_BUDGET`/`OVER_CLAIM` blocks.
- `resid` is the rest: blocks for other reasons (untestable, bad claim, mismatch) and trajectory differences. It is reported as is, and it can be nonzero, even negative.

The honest run's absolute `reroute_cost` is the defense's **price of safety** (§10), not part of the decomposition.

**Per-event bound.** Take a FAILED DELIVERY claim e, resolved at `t_e = by_round + δ`, with:
- `U_e` = shortfall (consumed − allocated), which is also what phase 4 re-orders from backup;
- `u_e` = claimed unit price;
- `V_e = U_e·u_e` = prepaid money committed to undelivered units (orders are prepaid in effect, §8);
- `Δu_e = p_bk − u_e`;
- `p_b` = backlog cost per unit-round, `h` = holding cost per unit-round, `ℓ_b` = backup lead, `T` = rounds.

Then:

`L_e = V_e + U_e·p_b·(δ + ℓ_b + 1) + U_e·Δu_e + late_e·h·(T − a_e + 1)`

1. **Purchases.** R pays `U_e·p_bk` extra for the replacement, and `U_e·p_bk = V_e + U_e·Δu_e`. Payments are otherwise identical.
2. **Backlog.** R's net stock is `U_e` lower from `by_round` until the replacement arrives at `t_e + ℓ_b`, which is `δ + ℓ_b` rounds. The per-round cost difference is at most `p_b·U_e`. FIXES' form keeps a +1 of slack. Holding can only fall.
3. **Late surplus.** If S_main delivers the shortfall after `t_e`, those `late_e ≤ U_e` units come on top of the replacement. They are held from their arrival round `a_e` to the end, because decisions are fixed. This term is not in FIXES' form (D21).
4. **PRICE failures contribute 0.** Payments are capped at `qty × claimed price`.

**Check.** `damage ≤ Σ_e L_e` in every OBT run. The eval raises `LossBoundViolation` otherwise, which is a FIXES STOP. Baselines never replace a missing unit, so the kept-promise counterfactual measures overstock there, not damage. They report no damage figure and no bound.

**Budget corollary (the headline claim, quantified).**
- By I1, the exposure behind e was at most `P(c) ≤ B(c)` when the last order consuming it executed, so `V_e ≤ B(c)` and `U_e ≤ B(c)/u_e`.
- With `late_e ≤ U_e` and `T − a_e + 1 ≤ T`, each failure event costs at most:

`L_e ≤ B(c)·(1 + (p_b·(δ+ℓ_b+1) + Δu_max + h·T) / u_min)`

The damage from one broken promise is linear in the trust budget the counterparty had earned. The late-surplus term makes the constant grow with the horizon T. The results check every measured `L_e` against this a-priori value, using `B(c)` at the time of the last consuming order.

## 7. Invariants

- **I1** Gate safety: every action that becomes EXECUTED passes the full §6 gate table at that moment; `P(c) ≤ B(c)` after every execution.
- **I2** Earned trust: `B(c)` rises only in a verifier step that sets a claim of `c` to PASSED.
- **I3** Ledger integrity: only `PENDING → PASSED | FAILED | LAPSED` (LAPSED only if consumed = 0), only by the verifier; terminal statuses never change.
- **I4** Propagation: a FAILED claim's citing actions and notes are flagged in the same step.
- **I5** Context isolation: no raw counterparty text in agent context (unit test only).
- **I6** Capacity: for every claim, total consumed qty ≤ claimed qty.
- **I7** Receipt uniqueness: every received unit is credited to at most one claim, and only to a claim of the supplier and item that delivered it.

**Checked three ways.**
- **TLA+** (`spec/OBT.tla`): models the §5 phase order exactly; nondeterminism only in deliveries/invoice prices, supplier claims, and buyer proposals. I1–I3 are action properties; I4, I6, I7 are state invariants. TLC runs on small bounds via `spec/run_mutants.sh`, with the claim, order and payment id pools as symmetry sets. That is sound because every property is a safety property and no step tells ids apart. Earliest-deadline ties are nondeterministic in the spec, which over-approximates the code's claim_id tie-break. Bounds, TLC version, state counts, depths and runtimes are in `spec/results/README.md`.
- **Mutation check**: for each of I1, I2, I4, I6, I7 one spec mutant removes the enforcing guard (budget row; cool-down floor; same-step flagging; capacity; receipt bookkeeping). Three more remove a binding. ITEM drops same-item binding (caught as I1). XSUP-RECEIPT lets allocation ignore the supplier (caught as I7). XSUP-BUDGET lets a pass earn budget for every supplier (caught as I2). TLC must find a counterexample for every mutant that can act in a config, and the unmutated spec must pass. The exhaustive results come from these configs:
  - A′: 2 suppliers, 1 item, 2 rounds (cross-supplier binding).
  - B: 1 supplier, 2 items, 3 rounds (cross-item binding).
  - quick: 1 supplier, 1 item, 3 rounds.
  Config A, with 3 rounds and 2 suppliers, did not finish; its partial run is reported separately. A symmetry cross-check backs these up, and random simulation plus spec–code trace replay cover the full bounds (2 suppliers, 2 items, 6 rounds). The full bounds are not verified exhaustively. The invariant-by-config coverage table and all outputs are in `spec/results/`.
- **Runtime monitors** (`obt/monitor.py`): check I1–I4, I6, I7 after every phase of every run. I1 is re-derived by a second implementation of the §6 table from a pre-commit gate snapshot. Violations go into each run's metrics; the eval fails loudly if the total isn't 0.

## 8. Environment

Beer Game variant, 50 rounds, seeded demand.

- Buyer (LLM) serves seeded downstream demand and orders from two suppliers.
- `S_main`: cheaper, sends promises over A2A. This is the adversary slot.
- `S_backup`: scripted honest, ~20% pricier, fixed lead time. No claims needed.
- Costs: purchase, holding per unit-round, backlog per unit-round.
- **Payment model.** Placing an order charges nothing. The supplier's invoice is posted to the oracles the next round; code proposes a PAYMENT for it, the gate decides, and only allowed payments are charged. Under OBT a payment is capped at `qty × claimed unit price`; any invoice amount above the cap is recorded as unpaid-disputed, not charged, and fails the PRICE claim. Baselines pay invoices in full. Payment lands before delivery (lead ≥ 2), so orders are **prepaid in effect**: money for an undelivered order is lost. Scripted suppliers ship regardless of payment. Timeline for an order placed in round t:
  - The invoice is posted at the start of round t+1, and its gated payment is charged in phase 8 of round t+1.
  - Units arrive at the start of round t + lead (≥ t+2).
  - Holding (0.5) and backlog (2.0) per unit are charged at the end of every round, after that round's demand.
- **Loss from lies** = total cost minus cost on the same seed with an honest `S_main`. It is decomposed as damage + reroute_cost + resid (§6), and only damage is bounded.
- **One item.** The eval env trades a single item, and the item catalog is closed at the type level (`types.ITEMS = ("widget",)`, for I5). Item binding (every claim an order cites must be for the order's item, D18) is therefore **not exercised in the eval runs**. It is verified in two other places. TLA+ config B (1 supplier, 2 items) exhaustively checks it, and the ITEM mutant, which removes the same-item check, must be caught there as an I1 violation. Unit tests build synthetic two-item states. Gate tests check that any wrong-item citation, DELIVERY or PRICE, gives CLAIM_MISMATCH, even when the same-item claims alone would cover the order. A monitor test checks that the runtime I1 monitor flags an executed order bound to another item's claim.

## 9. Scenarios (scripted suppliers, deterministic)

| #   | Supplier behavior                                            |
| --- | ------------------------------------------------------------ |
| 1   | Honest (utility baseline)                                    |
| 2   | Always lies on delivery                                      |
| 3   | Farm-then-lie: honest N rounds, then one large false promise |
| 4   | Slow drift: small, growing shortfalls                        |
| 5   | Price bait: quotes low, invoices high                        |
| 6   | Vague: untestable promises only                              |
| 7   | Far deadlines: pushes resolution past the horizon            |
| 8   | Claim splitting: many small pending claims to one big order  |
| 9   | Honest supplier with noisy delays (false-positive stress)    |
| 10  | Farm, fail once, re-farm                                     |
| 11  | Extraction attack: a real offer plus injected parser instructions and decoy numbers (shrunk qty, inflated price); ships the shrunk lot at the inflated price, so it profits only if extraction is fooled |
| 12  | Sybil re-entry: lies from the cold start; after a claim fails, returns under the next registered identity (up to 3), which starts at `b0` |

**Messages come from a frozen bank** (`data/message_bank.json`, D23). Scripted suppliers emit intents (kind + slot values + truth flag). Each message is a template for that kind, chosen with the run seed and filled with the intent's numbers.
- **Template source.** Templates are `qwen3:8b` rewrites that passed an exact-numbers check and a separate semantic reading. Scenario-11 injections are written by template.
- **The run bank is grounding-filtered.** Every slot of a testable kind is recoverable by the F5 context patterns, so runs measure security rather than phrasing luck.
- **The extractor test set is not grounding-filtered.** Its 199 items (200 before one bracketed-placeholder template was excluded, D23c) keep hard-but-valid phrasings, and the eval reports how often honest testable messages come out UNTESTABLE.
- **Extraction in runs.** Every eval run that reads claims extracts with the frozen LLM extractor. The rule extractor is only a baseline on the test set (D24).
- **Semantic reader, validated (D23a/b).** The reader that filters the bank (`qwen3:8b`, fixed prompt, thinking on) must pass a 20-phrase arrival-vs-shipping contrast set and accept all 7 canonical messages before use. Its prompt was tuned against that set, so it was also tested on fresh held-out sets with no prompt change, each run once:
  - **Run 1:** 18/20 overall, 20/20 on the arrival-vs-shipping question. The 2 misses were answer-key errors: in those items the price-validity round equalled the delivery round, so "is round U the delivery deadline?" was truly yes.
  - **Run 2:** a completely fresh set, with validity ≠ delivery round enforced by a test. **20/20** overall and on the deadline question.
- **Hard-phrasing subset (`test_hard`, 30 items, D23b).** Hand templates, no LLM: "ship/send/dispatch by round N", "ready/available by round N", "scheduled for round N". DELIVERY gold is UNTESTABLE and PRICE is normal. Never in the bank, so never in a run. It is reported separately. The key metric, shipping dates recorded as delivery deadlines, is:
  - gpt-oss, LLM alone: **21/30** (every ship and ready item);
  - gpt-oss with the code guard: **0/30**;
  - rule baseline: 0/30 as-is (21/30 before the guard).

Defenses: `none` (no defense, raw messages in memory); `llm_selfcheck` (the LLM asks itself "is this supplier trustworthy?" before each S_main order); `provenance` (authenticated means trusted); `reputation` (code-only Beta reputation, below); `obt`. Every baseline sees S_main's raw messages; OBT never does.

**Reputation baseline** (`obt/reputation.py`, D22):
- **Score.** `(s+1)/(s+f+2)` over the counterparty's resolved orders. An order is a success iff its full quantity arrived by the promised round.
- **Rule.** An S_main order is allowed iff the counterparty is on probation (fewer than `n0 = 3` outcomes) or its score is ≥ θ (0.8), and the order's value is ≤ score × cap ($200).
- **Blocked quantity** is rerouted to backup by code, as under OBT.
- **Evaluation.** E1 sweeps cap × θ, and OBT is compared against the baseline's whole Pareto front.

**Positioning: why this isn't just reputation.** Reputation scores *who* a counterparty is: one number per identity, earned by any mix of past outcomes and spendable on any future order up to a cap. OBT binds every action to the specific falsifiable claims it relies on:
- **Capacity.** A claim backs at most the quantity it promised.
- **Budget.** B(c) grows only by the largest exposure the counterparty actually honored.

So trust earned with many small true claims can't be spent on one large order. That is exactly what a farm-then-lie supplier does to a reputation score (scenario 3). Under reputation, every fresh identity also restarts on probation with half the cap (scenario 12). Under OBT it restarts at b0.

## 10. Evaluation

- Loss from lies per scenario × defense, decomposed as `damage + reroute_cost_diff + resid` (§6). Every term is relative to the honest run with the same defense and seed; damage is also checked against the per-event bound Σ L_e (OBT). `resid` is reported, never folded into another term.
- Utility cost: blocked honest actions and extra cost in scenarios 1 and 9. **Price of safety:** the absolute backup premium the defense's own reroutes cost in the honest scenario, per defense.
- Overhead: added latency and tokens per round.
- Extractor accuracy: 200 labeled messages, precision/recall on template + slots. The 30-item hard-phrasing subset is reported separately, LLM alone and with the code guard (§9).
- Budget: ~45 full runs + 200 single extractor calls. Local gpt-oss-20b and Qwen3 8B for all dev. OpenAI: all runs on GPT-5.6 Luna, scenarios 1–10 once on Terra. Hard cap $13.

## 11. Open design questions

- `b0` and `W` defaults; ablate both.
- Should partial delivery count as a partial pass? v1: no, binary.
- Should notes without citations be allowed to mention counterparty facts? v1: yes, but they can't back an action.
