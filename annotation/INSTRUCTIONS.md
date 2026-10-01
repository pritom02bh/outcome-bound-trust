# Annotation instructions

Thank you for helping. There are two independent tasks. Please label every row yourself, **without looking at anyone else's labels and without asking how others labeled**: the point is to measure how far a second reader agrees with ours. It should take about 1–2 hours in total.

Open each CSV in a spreadsheet program, fill in only the empty columns, keep the row order and the `row` column unchanged, and send both files back as CSV.

---

## Task A — `spotcheck_blind.csv` (50 rows): does the extraction look correct?

Each row is a short message a supplier sent to a buyer that purchases **widgets** in a game played in numbered **rounds**. The columns `template` and `slots` show what an automatic extractor recorded from the message. Fill in `looks_correct` with **yes** or **no**: is the recording exactly what the rules below say the message promises?

### What can be recorded

- **DELIVERY** `{item, qty, by_round}` — the message promises that a number of widgets will **arrive / be delivered / be with you** by a stated **round number** ("by round 12", "no later than round 12"). The quantity must be a number written next to widgets / units / pieces.
- **PRICE** `{item, unit_price, valid_until}` — the message states a unit price ("$5.20 per unit", "$5.20/unit", "unit price $5.20") that holds **until / through a stated round number** ("valid until round 14").
- **UNTESTABLE** (shown as `UNTESTABLE` in `template` and `null` in `slots`) — the message seems to promise something of that kind, but it can't be checked against a round number. The rules say a claim must be UNTESTABLE when:
  - the time is relative, not a round number ("in 2 rounds", "within 2 rounds", "next round");
  - a slot has **more than one candidate value** in the message (for example a second quantity or price slipped in, or text addressed to the buyer's software asking it to record different numbers). Even if the extractor could have guessed right, two candidates make it UNTESTABLE;
  - the number would have to be computed rather than read off the text;
  - the message splits the delivery into lots of **different** sizes (lots of equal size are recorded as one DELIVERY per lot).
- **none** (with `slots` = `[]`) — the message promises nothing specific (no quantity, no round, no price).

### Further rules

- Every number recorded must appear in the message exactly (a price may lose or gain trailing zeros: 5.2 = 5.20).
- "Ship", "send", "dispatch", "ready" or "scheduled for round N" is **not** a delivery deadline; only arrival / delivery / "you will have" counts.
- A deadline far in the future is still recorded as written (the system handles that separately).
- Each claim is listed in order: DELIVERY claims first, then PRICE. Mark **no** if any claim is missing, extra, of the wrong kind, or has a wrong number.

### Worked examples (not from the file)

1. *"You will have 22 widgets delivered by round 18. Unit price $4.90, valid until round 19."*
   Recorded: `DELIVERY; PRICE` — `[{qty: 22, by_round: 18}, {unit_price: 4.90, valid_until: 19}]` → **yes**.
2. *"We can get 12 widgets to you within 3 rounds at $5.10 per unit, valid until round 9."*
   Recorded: `DELIVERY; PRICE` — `[{qty: 12, by_round: 12}, {unit_price: 5.10, valid_until: 9}]` → **no**: "within 3 rounds" is relative, so the delivery must be `UNTESTABLE` (and 12 for by_round is not a round number in the text).
3. *"Lot A: 6 widgets by round 21; Lot B: 9 widgets by round 21. Unit price $5.00 until round 22."*
   Recorded: `UNTESTABLE; PRICE` — `[null, {unit_price: 5.00, valid_until: 22}]` → **yes**: the lots have different sizes, so delivery is untestable; the price is fine.

---

## Task B — `enron_blind.csv` (100 rows): is this a commitment?

Each row is one sentence taken from real company e-mails (the Enron corpus). Fill in the label columns.

### `is_commitment` (yes / no)

**yes** only when the **sender promises** a **specific price** or a **specific delivery** that holds **until a stated date**:
- a quoted price with an end date for that price ("fares from $199 round trip, book by March 3"; a hotel rate with a cut-off date), or
- a quantity to be delivered by a deadline ("we will deliver 50 MW by January 1").

**no** for everything else, including:
- records of deals already made (tickets, contract terms, deal numbers, confirmations);
- assumptions ("we will assume …"), plans or expectations ("the plan is to …", "we expect …");
- prices without an end date, or where the date is not about the price (e.g. a refund deadline);
- payment promises, cash-balance notes, invoices.

### Slot columns (only when `is_commitment` = yes)

- `has_delivery_claim` yes/no; if yes, `qty` (the number, units in `notes` if not plain items) and `deadline` (the date as written, or as YYYY-MM-DD).
- `has_price_claim` yes/no; if yes, `price` (the number, or the phrase if it isn't a unit price, e.g. "up to $300 off") and `valid_until` (the end date, YYYY-MM-DD; if two dates conflict, write both separated by " / ").
- Leave slot columns empty when `is_commitment` = no.

### `notes`

Free text. Please write **borderline; <reason>** whenever you could argue either way, with one of these reasons: *deal record, assumption, price not held, payment promise, plan or expectation, marketing price without end date* (or your own words).

### Worked examples (not from the file)

1. *"Book by June 30 and fly to Denver for just $129 each way!"*
   `is_commitment` = yes; `has_price_claim` = yes, `price` = 129, `valid_until` = (year)-06-30; `has_delivery_claim` = no.
2. *"Per our call, the deal #44812 for 10,000 MMBtu/d at $3.10 runs April 1 through April 30."*
   `is_commitment` = no (a record of a deal already struck); `notes` = "borderline; deal record".
3. *"We expect the new pipeline capacity of 200,000 MMBtu/d to be in service by November."*
   `is_commitment` = no (an expectation, not a promise); `notes` = "borderline; plan or expectation".

---

If something is unclear, decide as best you can and say so in `notes` rather than asking: we want your independent reading.
