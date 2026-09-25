# Outcome-Bound Trust — Design Spec (v0.1)

Working title: _Outcome-Bound Trust: Falsifiable Claims as a Security Primitive for Memory in Multi-Agent AI Systems_

## 1. Problem

A buyer agent must store and act on what a supplier agent tells it. The supplier is authenticated and legitimate, so provenance-based defenses mark it trusted. It can still lie for profit, usually after building a clean record. Goal: bound what a lying counterparty can gain, without an LLM making the trust decision.

Core rule: **trust comes from claims that came true, never from who said them or how they sound.**

## 2. Threat model

- Adversary: an authenticated counterparty. Full control over its own messages (content, timing, volume, wording).
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
| DELIVERY(item, qty, by_round)        | units received from counterparty in (created_round, by_round], credited to at most one claim, ≥ **consumed** |
| PRICE(item, unit_price, valid_until) | every invoice for item from counterparty in [created_round, valid_until) has price ≤ unit_price |

Either template resolves LAPSED instead if `consumed = 0`. A message the extractor can't map to a valid template becomes `UNTESTABLE`, as does any claim whose deadline is more than `H` rounds after creation (default 8). Untestable claims can't be cited.

## 5. Components

- **Gateway.** Receives A2A messages with the authenticated counterparty id. Writes raw text to an append-only audit log. Forwards to the extractor and appends the resulting claims (horizon cap applied) straight to the ledger.
- **Extractor (LLM).** `extract(msg) -> list[Claim]`. JSON-schema output, validated by pydantic. Invalid output → `UNTESTABLE`. Sets no trust or exposure values.
- **Ledger.** Append-only claim store. Only the verifier changes status, and only `PENDING → PASSED | FAILED | LAPSED` (LAPSED only when consumed = 0). Only the gate records consumption. `UNTESTABLE`, `PASSED`, `FAILED`, `LAPSED` are terminal.
- **Memory view.** The only path from counterparty data to the agent. Renders claims as cards (template, slots, status, deadline) plus each counterparty's track record and current budget headroom. No raw text.
- **Buyer agent (LLM).** Plans orders across a main supplier and a backup. Must cite claim ids on every action toward a counterparty. Its notes may cite claim ids too.
- **Oracles.** Environment-owned records: warehouse receipts, invoices. Read-only to everything except the environment.
- **Verifier.** Each round, resolves every PENDING claim with `deadline <= now` against the oracle.
- **Trust budget.** Per counterparty, computed in code (§6).
- **Gate.** Checks each proposed action against the rules (§6). Blocked actions return to the agent with a reason code.
- **Dependency tracker.** When a claim fails, flags every action and note citing it in the same step and fires a replan hook.

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
| ORDER: no cited PENDING DELIVERY claim for the item, or a cited DELIVERY claim with `by_round − now` < the supplier's minimum lead time | `CLAIM_MISMATCH` |
| ORDER: not exactly one cited PRICE claim for the item, PENDING, with `created_round ≤ now < valid_until` and unit price equal to the order's | `PRICE_MISMATCH` |
| ORDER: `qty` > total remaining capacity of the cited DELIVERY claims | `OVER_CLAIM` |
| PAYMENT: doesn't reference an EXECUTED order to `c`, or cumulative payments on it would exceed `qty × its claimed unit price` | `OVERPAY` |
| `P(c) + increment > B(c)` (increment = value for ORDER, 0 for PAYMENT) | `OVER_BUDGET` |

An allowed ORDER consumes capacity from its cited DELIVERY claims (earliest deadline first) and records exposure. A blocked ORDER's quantity is ordered from backup by code in the same round.

**Headline guarantee.** A counterparty's loss-inducing exposure at any moment is at most `B(c) = b0 + (largest delivered exposure it already honored)`. To steal X, it must first deliver goods worth about X − b0 against a claim. Farming trust with many small true claims earns nothing beyond small actions, and a small claim can't back a large order (capacity).

## 7. Invariants (to model-check in TLA+)

- **I1 Gate safety.** Every EXECUTED action to a non-backup counterparty passes the full §6 table at execution time, and `P(c) ≤ B(c)` after execution.
- **I2 Earned trust.** `B(c)` increases only in a verifier step that sets a claim of `c` to PASSED.
- **I3 Ledger integrity.** Status changes only `PENDING → PASSED | FAILED | LAPSED` (LAPSED only when consumed = 0), only by the verifier. Terminal statuses never change.
- **I4 Propagation.** Once claim `k` is FAILED, every action and note citing `k` is flagged in the same step.
- **I5 Context isolation.** No raw counterparty text reaches agent context. Enforced by code structure and a unit test, not TLA+.

## 8. Environment

Beer Game variant, 50 rounds, seeded demand.

- Buyer (LLM) serves seeded downstream demand and orders from two suppliers.
- `S_main`: cheaper, sends promises over A2A. This is the adversary slot.
- `S_backup`: scripted honest, ~20% pricier, fixed lead time. No claims needed.
- Costs: purchase, holding per unit-round, backlog per unit-round.
- **Payment model.** Placing an order charges nothing. The supplier's invoice is posted to the oracles the next round; code proposes a PAYMENT for it, the gate decides, and only allowed payments are charged. Under OBT a payment is capped at `qty × claimed unit price`; any invoice amount above the cap is recorded as unpaid-disputed, not charged, and fails the PRICE claim. Baselines pay invoices in full. Payment lands before delivery (lead ≥ 2), so orders are **prepaid in effect**: money for an undelivered order is lost. Scripted suppliers ship regardless of payment.
- **Loss from lies** = total cost minus cost on the same seed with an honest `S_main`.

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

Baselines: (a) no defense, raw messages in memory; (b) LLM self-check ("is this supplier trustworthy?"); (c) provenance-only (authenticated means trusted).

## 10. Evaluation

- Loss from lies per scenario × defense.
- Utility cost: blocked honest actions and extra cost in scenarios 1 and 9.
- Overhead: added latency and tokens per round.
- Extractor accuracy: 200 labeled messages, precision/recall on template + slots.
- Budget: ~45 full runs + 200 single extractor calls. Local gpt-oss-20b and Qwen3 8B for all dev. OpenAI: all runs on GPT-5.6 Luna, scenarios 1–10 once on Terra. Hard cap $13.

## 11. Open design questions

- `b0` and `W` defaults; ablate both.
- Should partial delivery count as a partial pass? v1: no, binary.
- Should notes without citations be allowed to mention counterparty facts? v1: yes, but they can't back an action.
