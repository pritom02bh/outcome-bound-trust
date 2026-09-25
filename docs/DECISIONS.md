# Design decisions and open issues

Interpretations made while implementing `docs/DESIGN.md`. DESIGN.md is unchanged; each item says what the code does and what change is proposed, if any.

## D1. Exposure accrues only to PENDING claims
**Issue.** §4 says `realized_exposure` is "value of executed actions that cited it". If an action cites an already-PASSED claim and that adds to its exposure, `B(c)` rises without a verifier step, violating I2.
**Code.** Exposure is added only to cited claims that are PENDING at execution time. A PASSED claim's exposure is frozen.
**Proposed change.** State this in §4.

## D2. Actions citing only PASSED claims are outside P(c)
**Issue.** `P(c)` counts only actions citing a PENDING claim. An order that cites only old PASSED claims passes the gate if `P(c)+value <= B(c)`, then never counts toward `P(c)`. Repeating it gives unbounded outstanding exposure, so the headline guarantee does not hold for such actions.
**Code.** Implemented literally as specified (the gate is the §6 pseudocode). Scripted buyers always cite the fresh offer's claims. The eval reports how often the LLM buyer cites only PASSED claims.
**Proposed change.** Either require every action to cite >=1 PENDING claim, or count in `P(c)` every executed action whose goods have not yet arrived.

## D3. Cool-down window and I2
**Issue.** "`b0` if `c` has a FAILED claim within the last `W` rounds; on failure the history max is cleared." If passes that resolve during the cool-down count once it ends, `B(c)` jumps at window expiry with no verifier step (violates I2).
**Code.** Let `f` = round of `c`'s most recent failure. While `now - f < W`, `B = b0`. Otherwise `B = b0 + max(exposure of PASSED claims with resolved_round >= f + W)`. Passes during the cool-down never count, so B only rises in a verifier step.

## D4. Offer staging (claims are ledgered when relied on)
**Issue.** A supplier promise made before the buyer orders is conditional on the order. An honest supplier that isn't paid won't ship, so its DELIVERY claim would resolve FAILED and wreck its budget (a false positive the design did not intend).
**Code.** Extracted claims first sit in the gateway's offer book. A claim enters the ledger when an action citing it is allowed by the gate (committed just before execution). Unaccepted offers expire unledgered. The gate evaluates cited claims from ledger ∪ offer book, so UNTESTABLE offer claims still block with `BAD_CLAIM`.
**Proposed change.** Add an "offer" stage to §5, or define conditional claims.

## D5. Order quantity and value are derived by code
For orders to `S_main`, code sets `qty = sum(qty of cited DELIVERY claims)` and `value = qty * unit_price of the cited PRICE claim` (nominal list price if no PRICE claim is cited). The LLM chooses which offer to accept, never the value used by the gate. Money actually paid is the supplier's invoice.

## D6. PRICE window
"every invoice ... before valid_until" is read as invoices in `[created_round, valid_until)`. Older invoices are not covered by a new quote.

## D7. Slot values are closed types
`item` is an enum from the catalog; numbers are bounded. This stops the extractor from carrying free text into agent context through slots (I5).

## D8. b0 default
`b0 = 5%` of expected per-round spend = 0.05 * 20 units * $5 = $5 (1 unit). This is very tight and costs utility in scenario 1; `b0` and `W` are config fields and should be ablated (§11).
