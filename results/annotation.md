# Independent annotator agreement (D42, D42a)

Independent annotator (a professor not involved in the project) vs our labels (D42, D42a). Kappa is marked degenerate when one side gives every row the same label (our v2 spot-check labels are all yes; the seeded rows are all no); raw agreement and the disagreements then carry the information. Detection rate: seeded errors the annotator marked no.

| set | rows | raw agreement | kappa | kappa degenerate | detection rate | disagreements |
|---|---|---|---|---|---|---|
| spot-check, all | 50 | 0.980 | 0.935 | no | - | 1 |
| spot-check, v2 rows | 40 | 1.000 | - | yes | - | 0 |
| spot-check, seeded errors | 10 | 0.900 | 0.000 | yes | 0.900 | 1 |
| Enron is_commitment | 100 | 0.990 | 0.942 | no | - | 1 |

Enron slot agreement on the rows both we and the annotator mark is_commitment = yes (D42a).

| slot | rows | agree |
|---|---|---|
| has_delivery_claim | 9 | 9 |
| qty | 9 | 9 |
| deadline | 9 | 9 |
| has_price_claim | 9 | 9 |
| price | 9 | 9 |
| valid_until | 9 | 9 |

## Every disagreement

- Spot-check row 8 (v1_seeded, test015): ours no, annotator yes. "We will have the 23 widgets available no later than round 26. The unit price of $5.25 remains valid up to round 27." Recorded: DELIVERY; PRICE [{"item": "widget", "qty": 23, "by_round": 26}, {"item": "widget", "unit_price": "5.25", "valid_until": 27}].
- Enron row 60: ours yes, annotator no. "Preschedule: We will reduce our preschedule by the 5 mw's for 12/27 through 12/21, but will schedule the full 7 mw's for…" Our note: borderline; power scheduling; 7 MW; garbled date range in first clause. Annotator's note: borderline; plan or expectation / schedule.
