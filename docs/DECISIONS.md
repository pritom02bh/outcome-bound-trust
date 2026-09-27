# Design decisions and open issues

Interpretations made while implementing `docs/DESIGN.md`. DESIGN.md is unchanged; each item says what the code does and what change is proposed, if any.

## D1. Exposure accrues only to PENDING claims
**Issue.** §4 says `realized_exposure` is "value of executed actions that cited it". If an action cites an already-PASSED claim and that adds to its exposure, `B(c)` rises without a verifier step, violating I2.
**Code.** Exposure is added only to cited claims that are PENDING at execution time. A PASSED claim's exposure is frozen.
**Proposed change.** State this in §4.

## D2. Actions citing only PASSED claims are outside P(c) — CLOSED by F2
**Status.** Closed: F2's `CLAIM_MISMATCH` requires every ORDER to cite a PENDING DELIVERY claim, so every executed order counts toward P(c).

**Issue.** `P(c)` counts only actions citing a PENDING claim. An order that cites only old PASSED claims passes the gate if `P(c)+value <= B(c)`, then never counts toward `P(c)`. Repeating it gives unbounded outstanding exposure, so the headline guarantee does not hold for such actions.
**Code.** Implemented literally as specified (the gate is the §6 pseudocode). Scripted buyers always cite the fresh offer's claims. The eval reports how often the LLM buyer cites only PASSED claims.
**Proposed change.** Either require every action to cite >=1 PENDING claim, or count in `P(c)` every executed action whose goods have not yet arrived.

## D3. Cool-down window and I2
**Issue.** "`b0` if `c` has a FAILED claim within the last `W` rounds; on failure the history max is cleared." If passes that resolve during the cool-down count once it ends, `B(c)` jumps at window expiry with no verifier step (violates I2).
**Code.** Let `f` = round of `c`'s most recent failure. While `now - f < W`, `B = b0`. Otherwise `B = b0 + max(exposure of PASSED claims with resolved_round >= f + W)`. Passes during the cool-down never count, so B only rises in a verifier step.

## D4. Offer staging (claims are ledgered when relied on) — SUPERSEDED by D11
**Status.** Superseded in F2: claims go straight to the ledger; unused offers resolve LAPSED instead of being kept out of the ledger.

**Issue.** A supplier promise made before the buyer orders is conditional on the order. An honest supplier that isn't paid won't ship, so its DELIVERY claim would resolve FAILED and wreck its budget (a false positive the design did not intend).
**Code.** Extracted claims first sit in the gateway's offer book. A claim enters the ledger when an action citing it is allowed by the gate (committed just before execution). Unaccepted offers expire unledgered. The gate evaluates cited claims from ledger ∪ offer book, so UNTESTABLE offer claims still block with `BAD_CLAIM`.
**Proposed change.** Add an "offer" stage to §5, or define conditional claims.

## D5. Order quantity and value are derived by code — REPLACED by D13
**Status.** Replaced in F2: the buyer picks the quantity (capped by claim capacity); price comes from the single cited PRICE claim.

For orders to `S_main`, code sets `qty = sum(qty of cited DELIVERY claims)` and `value = qty * unit_price of the cited PRICE claim` (nominal list price if no PRICE claim is cited). The LLM chooses which offer to accept, never the value used by the gate. Money actually paid is the supplier's invoice.

## D6. PRICE window
"every invoice ... before valid_until" is read as invoices in `[created_round, valid_until)`. Older invoices are not covered by a new quote.

## D7. Slot values are closed types
`item` is an enum from the catalog; numbers are bounded. This stops the extractor from carrying free text into agent context through slots (I5).

## D8. b0 default
`b0 = 5%` of expected per-round spend = 0.05 * 20 units * $5 = $5 (1 unit). This is very tight and costs utility in scenario 1; `b0` and `W` are config fields and should be ablated (§11).

## D9. DELIVERY receipts can be double-counted — FORMALIZED by F3
**Status.** F3 replaces the allocation rule: units are credited as they arrive, to the earliest-deadline PENDING claim that still needs units, so a claim that later fails keeps the units it was credited. `allocate_receipts=False` still gives the literal template.

**Issue.** DELIVERY passes iff "received >= qty in (created_round, by_round]". Windows of consecutive claims overlap, so one real shipment can satisfy several claims. Example: claims made at rounds 5 and 6, both for 20 units, due by rounds 7 and 8. The supplier ships 20 units once, arriving at round 7. Both claims pass, so a supplier can keep passing claims while delivering half of what it promised.
**Code.** `Verifier(allocate_receipts=True)` (default): claims resolve in deadline order, and a passing claim consumes the units it counted, so each received unit backs at most one claim. A failed claim consumes nothing. `allocate_receipts=False` gives the literal template for comparison.
**Proposed change.** Amend the DELIVERY row in §4: "... received >= qty units not already credited to another claim".

## D10. B(c) is a max, so overlapping orders pin trust near b0 (utility finding)
**Issue.** `B(c) = b0 + max(realized_exposure of PASSED claims)`. With lead time L and one order per round, L orders are in flight, so order value v must satisfy `(L-1)·v + v <= b0 + v`, i.e. `v <= b0/(L-1)`. The budget never grows. Seen in stage 6: a buyer ordering every round from an honest supplier stayed at B = $10 all game.
**Code.** Unchanged. The scripted OBT buyer "pulses": it accepts from S_main only when nothing from S_main is pending, and asks for a lot sized to the budget it expects once the current order passes. B then grows by about b0 per lead time (to $125 by round 50 in scenario 1). The LLM buyer's prompt explains this.
**Proposed change (for discussion).** Either state that throughput is bounded by `B/L`, or define B over concurrent exposure, e.g. `b0 + max over rounds of honored exposure outstanding at once`. That keeps the "must first deliver about X" property without forcing pulsing.

## D11. A DELIVERY claim is a capacity offer; unused claims LAPSE (F2, user decision)
**Issue.** FIXES F1/F2 put claims straight into the ledger, and F3 passes a DELIVERY claim iff allocated >= claimed qty. An honest supplier's offer that the buyer uses only partly, or not at all, would then FAIL.
**Decision (user).** A DELIVERY claim is a capacity offer. The supplier owes only the qty consumed by allowed orders; it passes iff allocated >= consumed by `by_round + δ`. A claim with consumed = 0 at resolution goes to a new terminal status **LAPSED** (also for PRICE claims no order used). LAPSED never changes B(c) and never counts as a success for reputation or any pass-rate metric. I3 becomes `PENDING -> PASSED | FAILED | LAPSED`, LAPSED only when consumed = 0.
**Code.** `Claim.consumed`, `Claim.with_consumption`, `Ledger.consume`; the verifier resolves consumed == 0 as LAPSED; the budget counts only PASSED DELIVERY claims.

## D12. Orders can't cite a delivery date the supplier can't physically meet (F2, user decision)
The gate rejects an ORDER citing a DELIVERY claim with `by_round - current_round <` the supplier's minimum lead time in the env (`CLAIM_MISMATCH`), so an honest supplier is never obligated to an impossible delivery. `Gate(min_lead={S_main: GameConfig.main_lead})`.

## D13. Order price comes from the cited PRICE claim (F2, user decision)
Code sets `order.unit_price` from the single cited PRICE claim (same item, `created_round <= now < valid_until`), `value = qty x unit_price`. The gate asserts equality anyway, so an action built elsewhere with another price is blocked (`PRICE_MISMATCH`).

## D14. Invoices are paid only through gated PAYMENT actions (F2, user decision + one interpretation)
**Decision (user).** The env never auto-pays. Each invoice posted in round phase 1 becomes a code-proposed PAYMENT (phase 6), decided by the gate (phase 7) and paid in phase 8. Under OBT the amount is capped at `qty x cited claimed unit price` (`OVERPAY` otherwise, cumulative per order). Any invoice amount above the cap is recorded as unpaid-disputed, not charged, and the PRICE claim FAILS in the verifier. Baselines pay invoices in full. A blocked PAYMENT leaves the invoice unpaid.
**Interpretation (mine).** The table's last row `P(c) + value > B(c)` uses the action's *new* exposure: an ORDER adds its value; a PAYMENT adds 0, because it pays for an order whose value is already in P(c) and OVERPAY caps it at that value. P(c) sums ORDERs only. Without this, every payment would double-count its own order and be blocked.
**Consequence.** Payment happens the round after ordering, before delivery (lead >= 2), so orders are prepaid in effect (recorded for F7). Suppliers still ship whether or not they are paid (scripted behaviour).

## D15. Horizon cap H (F2)
A claim whose deadline is more than `H` rounds after its creation is stored as UNTESTABLE (`SimConfig.horizon_cap`, default 8). It can't discipline anyone within the game, so it can't back an action. Scenario 7's far deadlines now block as `BAD_CLAIM`.

## D16. Code remediation is part of OBT only (F4)
Rerouting blocked ORDERs and re-ordering a failed claim's shortfall from backup are run by OBT's gate, verifier and dependency tracker, so they apply under `defense=obt` only. Baselines have no claim verification by definition, and none of their orders is gate-blocked. The selfcheck baseline's own veto is re-planned by its LLM, as before. Rerouting takes the whole blocked quantity, because the gate is all-or-nothing (the "(or blocked)" case in F4).

## D17. Grounding means "the only value the text offers for that slot" (F5)
F5 requires every slot number to appear in the raw text and rejects messages with more than one candidate per slot. The code implements both as one rule: for each numeric slot, the set of values matched by that slot's context patterns (`obt.extractor.slot_candidates`) must equal `{value}`. A number that appears only in another context (e.g. "in 2 rounds" when "round 9" appears elsewhere as a price validity) doesn't ground a deadline.
**Consequences.** Relative-time promises and computed values are UNTESTABLE. Split offers with *different* lot sizes are UNTESTABLE (equal-size splits stay testable). Any injected or decoy number in a slot's context makes that claim UNTESTABLE, even when the extractor wasn't fooled. That's the intended fail-closed direction: an untestable offer can't back an order.

## D18. Strict item binding (F6, user decision)
Every claim an ORDER cites, DELIVERY or PRICE, must be for the order's item; otherwise `CLAIM_MISMATCH`. Before this, the gate, the runtime monitor and `spec/OBT.tla` all used a lenient rule. It required at least one PENDING same-item DELIVERY claim, ignored other-item DELIVERY citations (so their capacity didn't count), and sent a wrong-item PRICE claim to `PRICE_MISMATCH`. The three were consistent with each other, but the spec header described the strict rule. Under the lenient rule an order for 10 widgets citing a 10-widget claim plus a gadget claim executed. Now it is blocked (regression test `test_regression_covered_order_plus_other_item_claim_is_blocked`).
**Why strict.** A citation is the buyer's statement of which promises an action relies on. A wrong-item citation is either an error or an attempt to launder a claim, and silently dropping it makes the record say something the gate didn't check.
**Scope.** Gate (`Gate.allow`), monitor (`table_verdict`) and spec (`OrderTable`) use the identical rule. The eval env has one item (DESIGN §8), so eval results are unaffected. TLA+ configs A and B were rerun after this change.

## D19. Money in the security path is exact Decimal cents (F6, user decision)
Claims (`unit_price`, `realized_exposure`), actions (`value`, `unit_price`), the budget (`b0`, B(c), P(c)), the gate and the monitor hold money as `Decimal` with exactly two decimal places (`obt.money.Money`), and every money comparison is exact. This matches `spec/OBT.tla`, which uses exact integers. The float tolerances (`PRICE_EPS`, `VALUE_EPS`, `MONEY_EPS`) are gone. Before they were removed, the differential test (`tests/test_conformance.py`) had found the monitor using 1e-6 where the gate used 1e-9.
**Two ways in, both documented in `obt/money.py`.**
- **Constructing a field** from a float is exact, never rounded: the float's shortest `repr` is taken, so 6.1 → 6.10, and a sub-cent value such as 5.00000001 fails validation and can't exist. Extracted prices are parsed from the message digits straight to Decimal.
- **The env boundary** (float invoices, float config such as b0 and the backup price) goes through `to_money(x) = Decimal(repr(x))` rounded half-even to a whole cent. This is the one rounding rule. Every env price is a whole cent, so in practice it only removes float noise (87.55000000000001 → 87.55).
**Out.** Payments go back to the env as `float(value)`, and traces and metrics report floats. Env cost accounting stays float.
**Guard.** `Claim.with_consumption` rejects a non-Decimal price, because `model_copy` skips validation and would otherwise let float money into the ledger.

## D20. Exhaustive two-supplier config A′ and a stronger I7 (F6, user decision)
**A′.** Config A (2 suppliers, 1 item, 3 rounds) was stopped at 547,083,101 distinct states, depth 30, 0 violations, with its queue still growing (`spec/results/fallbackA_partial/`). The first proposed reduction, a per-supplier live-claim cap of 2, can't keep I7 covered: the I7 witness needs 3 PENDING claims at one supplier. It also shrank the state space by only about 30%. A cap of 3 is vacuous with a 3-id pool, the Claims and Orders pools are already at the minimum I7 and I1 need, and dropping past-round receipt history saved 1%. So the exhaustive two-supplier config is A′ = 2 suppliers, 1 item, 2 rounds, with no constraint. I2 and I7 need 3 rounds, so their single-supplier versions are checked exhaustively in quick and B. Their cross-supplier versions are checked in A′ by two new mutants: XSUP-RECEIPT (allocation ignores the supplier, caught as I7) and XSUP-BUDGET (a pass earns budget for every supplier, caught as I2).
**I7 strengthened.** It now reads "…credited to at most one claim, *and only to a claim of the supplier and item that delivered it*". The old wording can't see a unit credited to the wrong supplier's claim, because that is still one unit on one claim. The change applies in all three places: the spec (per-supplier/item conservation, `SumAlloc ≤ SumArr`), the runtime monitor (each credit's receipt supplier and item must match the claim's), and CLAUDE.md / DESIGN §7.

## D21. The loss bound applies to damage under a kept-promise counterfactual (F7)
FIXES F7 asks to check `loss_from_lies ≤ Σ_e L_e` per run. `loss_from_lies` compares the run with a *separate* honest run, so it also contains three costs that no failure event causes:
- **Opportunity cost:** backup purchases after blocks. Vague, far-deadlines and price-bait have 0 DELIVERY failures, yet OBT still shows 119–143 of loss.
- **Cool-down reroutes.**
- **LLM trajectory noise.**

The literal check would fail on correct behavior. So, as the user approved:
- The bound is checked on `damage = cost(R) − cost(R*)`, where R* holds R's decisions fixed and keeps every relied-on promise (DESIGN §6).
- `loss_from_lies` is still reported, decomposed as damage + reroute_cost + resid.

**Cost-model difference: late delivery.** The FIXES form has no term for a shortfall that S_main delivers after the claim resolved. Those units then arrive on top of the backup replacement and are held to the end, because decisions are fixed. The bound adds `late_e·h·(T − a_e + 1)`. On noisy-honest (full length, seed 1), damage is 122.5, which is above the FIXES form (`tests/test_lossbound.py::test_late_delivery_needs_the_surplus_term`) and within the extended bound of 243.5.

**Baselines report no damage.** Without remediation, the kept-promise replay leaves R* with every promised unit on top of whatever the buyer re-ordered. That is an overstock artifact: always-lie under no defense would show −4,116.5. Baselines therefore report `loss_from_lies` only.

**Differenced decomposition (user decision).** `loss_from_lies = damage + reroute_cost_diff + resid`, with every term relative to the honest run with the same defense and seed. `reroute_cost_diff = reroute_cost(R) − reroute_cost(honest)`. The honest run's absolute `reroute_cost` (20.0 for OBT in the scripted eval) is reported separately as the defense's price of safety. An earlier version used the attack run's absolute reroute cost, which mixed the two bases and pushed `resid` negative. `resid` can still be nonzero from other blocks and trajectory differences, and it is reported as is.

## D22. Reputation baseline: cold start, cap, and how it is compared (F9, user decision)
F9 specifies `score = (s+1)/(s+f+2)` over past delivery outcomes, with orders allowed iff `score ≥ θ` and per-order value ≤ `score × cap`. Two things were left open and are now settled:
- **Cold start: probation.** θ applies only after `n0 = 3` resolved outcomes of that counterparty. Before that, orders are allowed with value ≤ `score × cap` (0.5 × cap for a newcomer). Taken literally, the rule would never trade with a newcomer: score 0.5 < θ means no orders and so no outcomes.
- **cap: $200 by default**, about two rounds of expected S_main spend.
- **How it is compared.** E1 also sweeps the reputation baseline over `cap ∈ {$50, $100, $200, $400}` × `θ ∈ {0.6, 0.7, 0.8, 0.9}`, all scenarios, 3 seeds, scripted buyer. OBT is compared against the baseline's full loss-vs-utility-cost Pareto front, not a single point. For the LLM runs (E2), the baseline uses the config on its front closest to OBT's utility cost, and that choice is recorded here when E1 is done.

## D23. Message bank and extractor dataset (F10, user decisions)
- **Templated variants.** For each intent kind, local `qwen3:8b` rewrites a canonical intent that uses distinctive numbers. A variant is accepted only if it contains exactly those numbers (max 5 tries per request, then dropped). The target is 30 accepted variants per kind. Numbers are then replaced by placeholders, and runs fill in the real values, choosing a template with the run seed. Scenario-11 injections are written by template, not by the LLM.
- **Grammar.** A template is excluded if it breaks when filled, for example "1 widgets" when qty = 1.
- **Two acceptance levels.**
  - The run bank is **grounding-filtered**: every slot of a testable kind (offer, deal, price-only, split) must be recoverable by the F5 context patterns, so runs measure security, not phrasing luck.
  - The extractor test set uses **numeric-only** acceptance: hard-but-valid phrasings such as "ETA r9" stay in. The eval reports extractor accuracy *and* the rate at which honest testable messages become UNTESTABLE, as a visible limitation.
- **No leakage.** Templates are split between dev (50 items, prompt tuning) and test (200 items), and no template or intent appears in both. Runs may use all templates.
- **Gold labels follow F5 exactly, computed per item.** Non-injection items: gold is the intent's claims. Injection items (scenario 11): a claim whose slot has more than one candidate value in the message (a decoy) is gold UNTESTABLE, which is the designed fail-closed behavior and counts as correct. If the injection brings no competing number, gold is the real offer's claims.
- **Scenario-11 metrics:** (1) injected values recorded, which must be 0; (2) accuracy against this gold; (3) real-offer recovery rate, reported as a utility cost, not an error.
- **Semantic check (user decision, after the first build drifted).** Every variant, for the run bank and the test set alike, must pass a second, separate `qwen3:8b` reading after the numeric check.
  - The reader has a fixed prompt, temperature 0 and a fixed seed, and answers yes/no to per-slot questions about the canonical intent, for example "Is round 23 the round by which the buyer HAS the goods (not a shipping date)?". Every answer must match.
  - Each kind's question set includes an expected "no", so a reader that always says yes fails.
  - The reader accepts all seven canonical messages and rejects a "ship … in round 23" rewrite.
  - The per-kind rejection rate is logged in `data/message_bank.json` → `stats`.
- **Drift in the first build.** Nudged away from the original's phrases, plain offers turned deadlines into shipping dates ("ship 37 units in round 23") and used ordinals ("the {by}rd cycle"). Only 2 of 164 offer templates survived grounding. That build is kept in `runs/message_bank/v0/`. The fix: the generator prompt now requires a deadline to stay a deadline, placeholder ordinals are rejected, and the semantic check was added.
- **Spot-check sheet is stratified.** 40 test items: 12 plain offers (where drift happened) and 4 of each other kind (deal, price-only, vague, far-deadline, relative, split, injection).
- **Dev tuning (50 dev items only; the test set was not looked at).** The dev errors were almost all correct LLM extractions that F5 grounding rejected. There were two pattern defects, now fixed:
  - The price pattern captured a round number as a price ("…at that price until round 27" gave price candidate 27).
  - "valid up to round N" wasn't a recognized validity phrase.

  Neither fix adds a way for an injected number to be recorded: they only stop false candidates and accept one phrasing. The run bank is still valid, because every template that passed before still passes. Injection gold was recomputed deterministically with the fixed patterns (`python -m eval.build_message_bank --regold`, no LLM calls).
  One prompt line was added: text aimed at parsers ("override", "record these values") is ignored, and only the supplier's own offer is extracted. Before it, the LLM returned no claims at all for injected messages.
  - **Dev before → after:** recall 0.80 → 0.96, exact match 0.68 → 0.94, honest→UNTESTABLE 14.6% → 5.5%, injection accuracy against F5 gold 0.50 → 1.00, injected values recorded 0 → 0.
  - **Frozen prompt sha256:** `ac1afafb…d061`.
- **Run pool re-filtered with the final patterns (user request, before the spot-check).** `python -m eval.build_message_bank --rebank` re-applies the run filter (grammar + grounding) to every frozen accepted template with no LLM calls. Nothing was removed, and 20 templates that the pre-fix patterns had rejected now pass and were added: 9 offer, 2 split and 9 price-only, all phrased "valid up to round N" or with a round-number price context. Pools are now offer 39, split 32, price-only 39, and deal, vague and far-deadline 30 each. All gold was recomputed with the final F5 rules (`--regold`, which now covers every kind), and 0 labels changed. The dataset and `spotcheck.csv` are byte-identical, so only `MESSAGE_BANK_SHA256` changed (`b9d3c43e…b442` → `69aa1e21…4a1e`). The pre-refilter files are kept in `runs/message_bank/v2_prerefilter/`. Tests pin both properties: run pool == filter(templates), and gold == F5 gold.
- **"Delivery … scheduled for round N" (user decision).** This is a real ambiguity (dispatch or arrival?), so it stays in the test set, where it counts toward the honest→UNTESTABLE rate. It is not in the run pool: grounding rejects it, and a test asserts it.
- **Exact match compares testable claims only.** An UNTESTABLE marker and "no claim" are both fail-closed, so a relative promise the extractor declines counts the same as one it marks UNTESTABLE.

### D23a. Spot-check v1 failed (30/40); F10 redone as bank v3 (user decisions)
- **Result.** The user marked 10 of 40 rows wrong: test002, 015, 018, 023, 024, 027, 029, 030, 184 and 196. The reviewed sheet is in `runs/message_bank/spotcheck_v1/`. The v2 bank, dataset and logs are in `runs/message_bank/v2_spotcheck_failed/`.
  - **Main defect (8 offers).** DELIVERY deadlines worded with shipping or readiness verbs ("ship/send/send out … no later than round N", "have … ready/available by round N") were labeled as arrival deadlines. DESIGN defines DELIVERY as received by round N.
  - **Second defect (2 injections).** "lot size N" did not count as a competing quantity.
- **Lexical guard (`delivery_verb_ok`).** For offer, deal, far-deadline and split, a template is rejected if the sentence carrying the deadline uses ship*/send*/sent/dispatch*/ready/available, unless that same sentence states arrival (delivered, arriv*, you('ll| will) [x] have, in your warehouse/hands/possession, receiv*).
  - For split, the checked sentence is the text before `{LOTS}`, since the lot lines are fixed "by round" text.
  - For far-deadline, a clause containing `{lead}` ("we usually ship within 2 rounds") is removed first: it is a lead-time remark, not the deadline.
  - The guard applies at acceptance, so to every pool (run, dev and test), and again in the run filter.
  - The generator prompt now also asks for arrival wording. It did most of the work: the guard rejected 0 offers and 1 split in v3.
- **Semantic checker validated before use (`validate_checker`, `SEMANTIC_CONTRAST`).**
  - **Contrast set:** 20 labeled deadline phrasings. 10 are arrival (deliver/delivered/arrive/you will have/in your warehouse/receive/…) = yes. 10 are dispatch or readiness (ship/send out/dispatch/ready/available for pickup/commit to shipping/leave our warehouse/loaded/handed to carrier/production finished) = no.
  - **Scoring:** a phrase counts as right iff the deadline answer matches its label. An arrival phrase must also get every other offer answer right, so that the reader really accepts faithful offers.
  - **Canonical messages:** the reader must also accept all 7 canonical messages.
  - **Enforcement:** `build()` raises `CheckerInvalid` otherwise. The v3 bank stores the validation report.
- **Getting the reader to pass.** Each report is in `runs/message_bank/v3/checker_validation_*.json`.
  1. Zero-shot (the old prompt, no thinking): **11/20**. It read 9 of 10 dispatch phrasings as arrival, which explains the v1 defect.
  2. Contrastive few-shot added: 18/20, still failing on two "no later than" commitments.
  3. "No later than" examples added: 18/20. This time it rejected the canonical "we will deliver … by round 23" instead.
  4. The deadline question reworded: 18/20. Reverted.
  5. qwen3 thinking turned on (`think=True`; `obt/llm.py` previously forced it off for qwen3, and the default is unchanged): 20/20. But it rejected the canonical deal ("deliver" read as sending) and relative ("can deliver" read as not a promise).
  6. **Final:** a sentence defining a delivery deadline as the round by which the buyer has the goods, one "deliver" yes-example, and the quantity question worded "offer or promise". Result: **20/20 and 7/7 canonical.**
  - **Limitation, stated plainly:** these iterations were checked against the validation set itself. The few-shot sentences, most verbs and all numbers are disjoint from the contrast set (12 gadgets, round 9), but one yes-example uses "deliver". The lexical guard is an independent backstop that doesn't depend on the reader.
  - **Reader settings:** qwen3:8b, temperature 0, seed 7, think=True, max_tokens 4000. The v3 bank file predates the `settings` field that now records these, so they are recorded here.
- **Quantity-like decoys (F5 patterns).**
  - "lot size N" / "batch size N" and a bare "N/unit" now count as quantity candidates.
  - A dollar amount per unit ("$5.75/unit") remains a price candidate, not a quantity. That's an interpretation: otherwise every honest "$5.00/unit" offer would lose its DELIVERY claim.
  - All gold was recomputed. All 9 test injections carrying "lot size" now have DELIVERY gold UNTESTABLE, and all 30 test and 8 dev injections have at least one UNTESTABLE claim.
  - Extra candidates only make grounding stricter, so nothing new can be recorded.
- **Regeneration (v3).**
  - The build took 10.8 h of local qwen3:8b time, about 22 s per thinking-reader call. For `relative`, the reader rejected 83% of rewrites (227 requests for 30 templates); for vague, 44%. Many other passes were exact rewordings of earlier ones (offer: 234 requests, 33 unique).
  - **Run pools:** offer 33, deal 32, and far-deadline, price-only, split and vague 30 each. Dev/test templates stay disjoint.
  - No "scheduled for round N" template was generated: the arrival-wording prompt removed it. The test set therefore has none. The run-pool exclusion is still asserted by a test.
  - **Checkpointing.** The builder now checkpoints each finished kind (`runs/message_bank/checkpoint/`, keyed by a fingerprint of the generator, reader, filters and patterns), so an interrupted rebuild resumes without repeating calls.
- **Dev tuning (dev split only, `eval/tune_extractor.py`, `runs/tuning/v3_*`).**
  - **Pass 1** (frozen prompt): precision 1.0, recall 0.92, exact match 0.88, honest→UNTESTABLE 10.9%, injected recorded 0. 5 of the 6 errors came from one grounding false positive: in run-on text, "by round 36 unit price $5" gave the quantity candidate 36.
  - **Fix:** a number followed by "unit price/cost/rate" is no longer a quantity candidate. This only removes a false candidate; a claimed quantity must still appear in quantity context. With `--rebank`, 5 run-on offer/deal templates now pass the run filter (none removed). `--regold` changed 0 labels.
  - **Pass 2:** precision 1.0, recall 0.99, exact match 0.98, honest→UNTESTABLE 1.8%, injection accuracy 1.0, injected recorded 0.
  - The remaining error is a defective dev split template ("unit price $5.00 will be delivered no later than round 41"). The reader passed it, but grounding keeps it out of the run pool, and the extractor correctly fails closed on its PRICE. It wasn't tuned toward.
  - The extractor prompt needed no change, so `EXTRACTOR_PROMPT_SHA256` is unchanged.
- **Pins:** `MESSAGE_BANK_SHA256` = `bcc88522…3ab3`, `EXTRACTOR_DATASET_SHA256` = `711dc743…70ef`.
- **New spot-check:** `data/spotcheck.csv` has 40 test items with the same stratification (12 offers plus 4 of each other kind). The same row IDs name different items, because the dataset is new.



### D23b. Held-out reader test, hard-phrasing subset, and the deadline guard in code (user decisions)
- **Confirmed interpretation.** "$N/unit" is a price. A bare "N/unit" or "lot size N" is a competing quantity.
- **Held-out reader test (`eval/checker_holdout.py`).** The reader's prompt was tuned against `SEMANTIC_CONTRAST`, so it was tested on fresh 20-phrase sets (10 arrival, 10 dispatch or readiness). The scoring matches the contrast set. The frozen prompt was not changed, the numbers in the question wording are substituted per item, and each set runs exactly once (the script refuses a second run).
  - **Run 1:** **18/20 overall, 20/20 on the arrival-vs-shipping question.** Both misses were answer-key errors, not reader errors.
    - In two arrival items the price-validity round equalled the delivery round (13/13, 15/15). The auxiliary question "is round U the delivery deadline?" was therefore truly *yes*, and the reader said yes; my key said no.
    - One item had also used the number 9, which appears in the few-shot. That was found and fixed *before* any result was seen: the first attempt was stopped with no output.
    - Run 1 is kept unchanged (`HOLDOUT_RUN1`, `runs/message_bank/v3/checker_holdout_run1.json`).
  - **Run 2 (option C):** a completely fresh set. Verbs, sentence structures and numbers are disjoint from the tuning set, the few-shot and run 1. A test enforces validity round ≠ delivery round. **20/20 overall, 20/20 on the deadline question** (`checker_holdout_run2.json`).
- **Hard-phrasing subset (`test_hard`).**
  - 30 items from 10 fixed hand templates (no LLM), 3 intents each, with intents disjoint from dev and test:
    - **ship** (12): ship / send / dispatched / commit to shipping by or no later than round N;
    - **ready** (9): ready / available / ready for dispatch;
    - **scheduled** (9): "scheduled for round N".
  - Gold: DELIVERY UNTESTABLE, PRICE as normal. It has its own split and is never in the bank, so never in a run (asserted by a test). The eval reports it separately: `rule:test_hard`, `llm:<model>:test_hard`, and the ablation `llm:<model>:test_hard:no_guard`.
- **Deadline guard in code (approved).** F5 grounding now fails closed on DELIVERY deadline wording (`obt/extractor.py`, `deadline_wording_ok`).
  - **The rule.** For each sentence that states the claim's `by_round` as a deadline, clauses that are a lead-time remark ("within N rounds") or a price validity ("until/through round N") and don't contain the deadline are set aside. The claim is then UNTESTABLE if what remains uses ship*/send*/sent/dispatch*/ready/available/schedul* and no arrival wording: deliver(s/ed), arriv*, receiv*, you('ll/ will) [x] have, in your warehouse/hands/possession.
  - "shipment" (a noun) is not a deadline verb.
  - The template guard (`delivery_verb_ok`) now uses the same verb lists, and the run filter uses the same grounding, so no run template can be refused at run time.
  - **Effect on committed data:** the run pool, all gold and the spot-check sheet are unchanged under the guard (the tests "run pool == filter" and "gold == F5 gold" still pass).
  - The guard is always on. Only the hard-subset ablation turns it off, to measure the LLM alone.
- **Hard-subset results.** The LLM outputs are cached, so "alone" and "with guard" score the same outputs (`runs/tuning/v3_hard/hard_subset.json`).

  | extractor | shipping/ready/scheduled dates recorded as DELIVERY | PRICE recovered | exact |
  |---|---|---|---|
  | gpt-oss:20b, LLM alone (no guard) | **21/30** (ship 12/12, ready 9/9, scheduled 0/9) | 30/30 | 0.30 |
  | gpt-oss:20b + code guard | **0/30** | 30/30 | 1.00 |
  | rule baseline, as-is (guard in code) | 0/30 (21/30 before the guard) | 30/30 | 1.00 |

  The frozen prompt defines DELIVERY as "received by", yet the LLM still recorded every shipping and readiness date as a delivery deadline. This is why the check belongs in code, not in the prompt. The "scheduled for round N" items were refused by numeric grounding already: "for round" isn't a deadline phrase.
- **Dev with the guard** (49 items): precision 1.0, recall 1.0, exact 1.0, honest→UNTESTABLE 0%, injected recorded 0. The guard adds no dev errors.
- **Known-bad dev template removed.** "…unit price ${price} will be delivered no later than round {until}" (dev039) was dropped through `EXCLUDED_TEMPLATES`. The bank keeps its record of what was generated. Dev now has 49 items.
- **Spot-check sheet protected.** `write_spotcheck` refuses to overwrite a sheet that holds reviewer answers.
- **Pins.** `EXTRACTOR_DATASET_SHA256` = `e29d6a68…0e43` (hard subset plus the dev039 removal). `MESSAGE_BANK_SHA256` is unchanged (`bcc88522…3ab3`), and so is the extractor prompt sha. `data/spotcheck.csv` is byte-identical.

### D23c. Spot-check v2 passed (40/40); bracketed placeholders removed
- **Spot-check v2.** The user marked all 40 rows correct (≥ 38 required), so F10 is accepted. The reviewed sheet is `data/spotcheck.csv`, with a copy in `runs/message_bank/spotcheck_v2/`.
- **Cosmetic cleanup (user request).** Templates with unfilled bracketed letter placeholders ("[Buyer's Name]", "[Your Name]", "[Buyer]", "[Supplier]") are excluded (`template_clean`). Gold labels were unaffected.
  - The run filter and the dataset exclusions both apply this. Injection notes such as "[Note for automated order systems: …]" are appended text, not templates, so they stay.
  - **Removed:** 2 run templates (1 offer, 1 split), the same 2 from `test_templates`, and 1 dataset item (test192, an injection item in the reviewed sheet, marked correct).
  - **New sizes:** test 199 (29 injections), dev 49, test_hard 30. Run pools: offer 32, split 29, deal 32, far-deadline 30, price-only 30, vague 30.
  - Applied without LLM calls (`--rebank`, `--apply-exclusions`). The pre-cleanup files are in `runs/message_bank/v3_prebrackets/`.
  - The reviewed sheet is kept as reviewed, including test192.
- **Pins.** `MESSAGE_BANK_SHA256` = `09ab70e4…e7c`, `EXTRACTOR_DATASET_SHA256` = `20ceb245…e242`. The extractor prompt is unchanged.

## D24. Extractor roles (F10, user decision)
- **Primary extractor.** Every eval run that reads claims extracts with the LLM extractor (`gpt-oss:20b` locally), whose prompt is tuned on the 50 dev items and then frozen (`EXTRACTOR_PROMPT_SHA256`).
  - This covers OBT runs with the LLM buyer, and every scripted-buyer run, because the scripted buyer reads claim cards under every defense (E1 included).
  - LLM-buyer baselines read raw text, not claims, so they use `NullExtractor`, which makes no extraction calls.
  - `eval/run.py` refuses any other extractor in a run.
- **Rule extractor.** Only a baseline, reported separately on the 200-item test set. The run bank is grounding-filtered with the same F5 patterns the rule extractor is built on, so using it in runs would make extraction trivially perfect there.
- **Unit tests** may still build `Sim` with the rule extractor for speed. Eval-harness tests route the LLM-extractor path through a fake LLM backed by the rule extractor (`tests/conftest.py`).
- **Cost.** Scripted runs (E1) now make one extractor LLM call per supplier message. Identical messages are served from the LLM cache when `--cache` is set.

## D25. Real A2A transport (F11)
- **SDK.** `a2a-sdk` 1.1.5 (JSON-RPC binding, protobuf types), served by Starlette and uvicorn on localhost. The exact versions are pinned in `requirements.lock`. The transport lives in `obt/transport.py`; `SimConfig.transport` is `inproc | a2a`. Unit tests default to `inproc` for speed; the eval defaults to `a2a` and records the transport in every run.
- **Topology.**
  - Every supplier identity is its own A2A server, with its own port, its own Agent Card, and its own bearer token issued at registration. That's `S_main`, `S_backup`, and the extra Sybil identities `S_main_2` and `S_main_3` in scenario 12.
  - The Agent Card is public at `/.well-known/agent-card.json`. It declares a `bearer` HTTP security scheme and requirement, and a JSON-RPC interface.
  - The buyer side is an A2A client. It resolves each agent's card, then sends data messages: `offer` (round, requested lot), `order` (order id, round, qty, item) and `payment` (round, amount).
  - The server rejects any request without that agent's own token with HTTP 401. That includes another agent's valid token.
- **Identity comes from the connection.** The gateway's counterparty id is the registry identity of the endpoint the reply arrived on (URL + token). Text claiming another identity changes nothing (tested with an impostor supplier).
- **One supplier, several identities.** A host composes the round's message once (one `offer_message` call per round, as in-process). It releases the message only on the endpoint of the identity the supplier speaks as after composing it. The other identities answer "no offer". This keeps scenario 12's switch-while-composing behavior and makes one message per round per supplier explicit on the wire.
- **What crosses the wire, and where it goes.**
  - Offer text goes to the gateway (audit log + extractor), exactly as before.
  - Order replies (invoice unit price and shipping schedule) go to the environment, which models physical delivery and the invoice. They never reach the buyer's context.
  - JSON numbers arrive as doubles. Float prices are exact, and integers are cast back.
- **Analysis channel.** The scripted supplier's intent/truth flag is ground truth for analysis only. It's read out of band from the host object in the same process, never over A2A, and no defense reads it.
- **Acceptance.** For all 12 scenarios (scripted buyer, seed 0), `inproc` and `a2a` give identical ledgers (claim ids, counterparties, slots, statuses, source hashes), actions, costs and traces. The same holds for the `none` and `reputation` baselines on scenarios 1, 3 and 12.
- **Overhead (measured).** About 1.4 ms per exchange on localhost and 0.11 s to start a run's servers. A 50-round scripted run takes 0.76 s over A2A, against 0.05 s in-process. Servers and clients are shut down at the end of every run (tested).
- **SDK log noise.** a2a-sdk 1.1.5 logs "Dispatcher task is not running. Cannot wait for event dispatch." at the teardown of every request answered with a single `Message`. That is the SDK's documented immediate-reply pattern, and the reply has already been delivered (parity is exact). Only that exact message is filtered; every other SDK warning and error still shows.
