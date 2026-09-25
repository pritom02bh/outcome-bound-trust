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
