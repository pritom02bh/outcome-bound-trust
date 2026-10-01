# E9 plan: a light second domain (cloud/API capacity) — PLAN ONLY, awaiting approval

Status: **not built**. Nothing below has been implemented or run. Build starts only after the user approves this plan, including the one decision in §8.

## 1. Purpose and scope

E9 tests whether Outcome-Bound Trust transfers to a second domain with a genuinely different kind of promise.
- **Domain:** an agent that buys cloud/API capacity.
- **Kept:** the same trust core (verifier, budget, gate, remediation, monitors).
- **Added:** a new claim template, **SLA(min_availability, window)**, checked against an environment-owned uptime log, and **QUOTA(capacity, by_round)**, the analog of DELIVERY.

E9 is deliberately light:
- scripted buyer and scripted suppliers only;
- suppliers emit **structured intents**, turned into claims directly, with **no natural-language extraction**. The extractor is not part of E9, and the paper must say so;
- 7 scenarios (honest, always-lie, farm-then-lie, slow drift, claim splitting, noisy honest, Sybil);
- 4 defenses (none, rep-strict, rep-n18, obt);
- seeds 1–3, so 84 runs.

## 2. Environment and cost model

The capacity game (`obt/env/cloud.py`, new) has the same round order as DESIGN §5 and the same seeding and money rules.

- **Workload.** In each round t the buyer must serve `D_t` request units (seeded Gaussian, mean 20, sd 4, as in the Beer Game).
- **Capacity.** Capacity units are **reserved for a term** of `L = 5` rounds.
  - An order for `q` units from provider P, provisioned at round `r`, gives `q` units of capacity in each of rounds `r … r+L−1`, **while P is up** in that round.
  - Capacity is perishable: unused capacity in a round is lost, and it costs nothing extra because it is already paid.
- **Prices** (per unit-round):

  | source | price | lead |
  |---|---|---|
  | main provider (reserved) | `u = $1.00` | ≥ 2 rounds |
  | backup provider (reserved) | `u_b = $1.20` | 3 rounds |
  | on-demand burst (unlimited, never down) | `p_od = $2.00` | 0 rounds |

- **Serving.** Served from reserved capacity = min(D_t, available capacity_t). The remainder is served on demand and costs `p_od` per unit. Nothing carries over, so there's no backlog and no holding cost.
- **Payment.** Prepaid in effect, as in DESIGN §8: the invoice for `q·L·u` is posted the round after the order and paid through a gated PAYMENT before provisioning (lead ≥ 2). Under OBT the payment is capped at the claimed price, as today.
- **Total cost** = reserved purchases + on-demand purchases.
- **Environment-owned oracles**, which suppliers can't write:
  - a **provisioning log**: (round, provider, units, order id), the analog of receipts;
  - an **uptime log**: (round, provider) → up/down, set by the scenario's ground truth and recorded by the environment, never by the supplier.

## 3. Templates

| template | slots | resolves at | PASSED iff |
|---|---|---|---|
| QUOTA | `item = "capacity"`, `capacity` (units), `by_round` | `by_round + δ` | units provisioned by P by `by_round`, not credited to another claim (allocation by earliest deadline, as for DELIVERY), are ≥ `capacity` |
| PRICE | as today, with `item = "capacity"` | `valid_until` | as today |
| SLA | `item = "capacity"`, `min_availability ∈ (0, 1]`, `start`, `end` (the window) | `end + δ` | up rounds of P in `[start, end]` / window length ≥ `min_availability` |

- **QUOTA is implemented as the existing DELIVERY template over a new item, "capacity".** Its verifier test, capacity accounting, EDF allocation, budget earning and remediation are then the existing code paths, unchanged.
- **SLA is new.** It has no capacity of its own: an order citing it records the reserved capacity that relies on it (§8). An SLA PASS does **not** earn budget, because only honored QUOTA/DELIVERY claims earn (D11's rule is unchanged). An SLA FAIL clears the budget for W rounds like any failure, and its citing actions are flagged (I4).
- **The horizon cap** H = 8 applies to `by_round` and to an SLA's `end`, so every claim resolves within reach.
- **Gate (unchanged rows):** an order must cite ≥ 1 live QUOTA claim for its quantity (capacity), exactly 1 PRICE, and optionally SLA claims of the same provider and item. OVER_CLAIM and OVER_BUDGET apply as today. P(c) counts an order while **any** cited claim is pending, so citing an SLA keeps its exposure pending until the window ends. That is deliberate and conservative.

## 4. Damage counterfactual and per-event bound (DESIGN §6 style)

**Counterfactual.** As in DESIGN §6, for an OBT run R let R* replay R with the same workload and the **same decisions**: every executed order and payment, in the same round, with the same amounts. In R* the provider keeps every promise the gate relied on:
- the units each order took from QUOTA claim e are provisioned at e's `by_round`, and R's remediation orders don't exist;
- for each SLA claim e relied on, the provider is up for at least `⌈a_e·n_e⌉` rounds of e's window. The restored rounds are the down rounds in R with the largest load, the worst case for the bound.

`damage(R) = cost(R) − cost(R*)`. `loss_from_lies = damage + reroute premium diff + resid`, exactly as in DESIGN §6.

**QUOTA failure e** (shortfall `U_e` = consumed − allocated, claimed unit price `u_e`, resolved at `t_e = by_round + δ`, backup lead `ℓ_b`):
- **Prepaid value lost:** `V_e = U_e·L·u_e`, paid in R and R* alike. In R it buys nothing, and the buyer pays again for replacement capacity.
- **On-demand while waiting:** from `by_round` until remediation capacity arrives at `t_e + ℓ_b`, at most `U_e` units per round are served on demand: ≤ `U_e·p_od·(δ + ℓ_b + 1)`.
- **Replacement premium:** remediation reserves `U_e` backup units for the remaining term, at most L rounds: ≤ `U_e·L·(u_b − u_e)`.
- **Late provisioning:** reduces cost, since capacity is perishable with no holding cost. So there is **no late-surplus term**, unlike the Beer Game (§6).

  `L_e^Q = V_e + U_e·p_od·(δ + ℓ_b + 1) + U_e·L·Δu_b`, with `Δu_b = u_b − u_e`.

**SLA failure e** (window length `n_e`, promised `a_e`, actual up rounds `m_e < ⌈a_e·n_e⌉`, reserved capacity relying on e `C_e`):
- **Excess downtime:** `k_e = ⌈a_e·n_e⌉ − m_e ≤ n_e` rounds.
- **Cost per restored round:** in each of them at most `C_e` units move from on-demand back to the reserved capacity already paid for. That saves at most `C_e·p_od`.
- **No remediation inside the window,** because the failure is only known at `end + δ`. Purchases are the same in R and R*.

  `L_e^S = k_e·C_e·p_od`

**Check (STOP rule):** `damage ≤ Σ_e (L_e^Q + L_e^S)` in every OBT run, with tolerance 1e-6, exactly as F7.

**A-priori corollary in terms of B(c).** By I1 every relied-on value is ≤ B(c):
- `U_e·L·u_min ≤ B(c)`;
- `C_e·L·u_min ≤ B(c)`;
- `k_e ≤ n_e ≤ H`.

So `L_e^Q ≤ B(c)·(1 + (p_od·(δ + ℓ_b + 1) + L·Δu_b)/(L·u_min))` and `L_e^S ≤ B(c)·H·p_od/(L·u_min)`. Damage from one broken promise is linear in the earned trust budget, as in the Beer Game. The SLA constant grows with the horizon cap H, not with the game length.

## 5. Scenarios (scripted suppliers, structured intents)

| # | scenario | QUOTA behavior | SLA behavior |
|---|---|---|---|
| 1 | honest | provisions on time | promises 0.95, delivers ≥ 0.95 |
| 2 | always-lie | provisions nothing | promises 0.99, is down every round |
| 3 | farm-then-lie | honest until round 25, then one large discounted QUOTA it doesn't provision | honest, then 0.99 promised with 0.5 delivered in the lie window |
| 4 | slow drift | provisions 2% less each round after round 10 | availability drifts down 1% per round after round 10 |
| 5 | claim splitting | splits lots into many small QUOTA claims; after round 20, triples the total and provisions nothing | honest |
| 6 | noisy honest | provisions on time, with 15% one-round slips | promises 0.9; random outages average 0.95 |
| 7 | Sybil | always-lie, re-entering under up to 3 identities | always-lie |

Scenario 6 measures false positives: any SLA failure there is a utility cost of the defense.

## 6. Invariants, monitors and what the TLA+ spec covers

- **Apply unchanged:**
  - I1 (gate safety, `P ≤ B`);
  - I2 (B rises only on a verifier PASS, and only QUOTA/DELIVERY earns);
  - I3 (ledger integrity: PENDING → PASSED | FAILED | LAPSED by the verifier only);
  - I4 (same-step propagation of any FAILED claim, SLA included: `deps.py` is template-agnostic);
  - I6 (capacity: consumed ≤ claimed, for QUOTA);
  - I7 (each provisioned unit credited to at most one QUOTA claim of the right provider and item);
  - I5 is not applicable, since there's no text.
- **SLA:** has no capacity (I6 n/a) and no receipt credit (I7 n/a). Overlapping SLA windows of one provider may read the same uptime rounds; that is allowed.
- **Runtime monitors:** the existing monitors run after every phase. The I1 monitor re-checks the gate table and must mirror the §8 change (SLA citations recorded as reliance). Any violation stops the run.
- **TLA+:** **no spec change is planned.**
  - The spec's abstract `D`/`P` templates cover QUOTA (DELIVERY over a different item), so the existing exhaustive results (k = 1, five bounds) apply to QUOTA's gate, budget and propagation logic.
  - **The spec does not model SLA:** neither its window/uptime test nor its reliance bookkeeping (§8). Those rest on unit tests, property tests and the runtime monitors, and the paper must say so.

## 7. Outputs and metrics

The same as E1/E2:
- loss from lies split into damage + reroute premium + resid;
- damage vs Σ bound (QUOTA and SLA events reported separately) with the max ratio;
- the a-priori ratio;
- utility cost ($ and % of the honest run's cost);
- main-provider share.

Tables `e9`, `e9_damage_vs_bound`; `NUMBERS.md` under RQ5 (generalization); a workbook sheet; INDEX row.

## 8. Decision needed before building: SLA reliance in the gate (a small core change)

"Keep the trust core unchanged" holds for QUOTA but **not exactly for SLA**:
- **Gate:** `gate.py` records consumption only for DELIVERY and PRICE claims. An SLA claim cited by an order would end with consumed = 0 and resolve **LAPSED** (D11: LAPSED iff nothing was consumed), never PASSED or FAILED.
- **Types:** `obt/types.py` has a closed `Template` (DELIVERY, PRICE) and a closed `Item` ("widget").

**Proposed minimal change** (new code only, no change to any existing rule):
- `types.py`: add the `SLA` template and the `"capacity"` item, with typed slots.
- `verifier.py`: add `check_sla` to the template registry; existing templates are untouched.
- `gate.py` `_consume`: an executed order citing an SLA records its reserved capacity on that claim as reliance (consumed += qty). That is bookkeeping only, and no gate row changes.
- The I1 monitor mirrors that bookkeeping.

Every existing test must pass unchanged, and the TLA+ results for the Beer Game are unaffected.

**Alternative** (no core change): treat SLA claims as informational (never cited), with damage from outages reported but not bound. That would make E9 test only QUOTA, which is DELIVERY renamed, so it would show little. **Recommendation: the minimal change.**

## 9. Estimated effort and runtime

- **Build:** the capacity environment and oracles; QUOTA/SLA templates and the §8 change; 7 scripted suppliers; the scripted capacity buyer; the damage replay and per-event bounds; tests first (template pass/fail/boundary, the bound on every scenario, replay fidelity, I1 property test with SLA citations); report and NUMBERS. About one working session.
- **Runtime:** scripted, in-process, about 5–10 s per run, so 84 runs take about 10–15 minutes. No model calls.
