# Walkthrough: one farm-then-lie run, round by round

E1, scripted buyer, default config (b0 5%, W 0, δ 0); scenario 3 (farm-then-lie), seed 1; defenses `obt`, `none` and `rep-default`, each against its honest run (scenario 1, same defense, config and seed). Read from existing logs only; no new runs (D46a). Figure: `paper/figures/walkthrough.pdf` (and `.png`). Per-round extract: `results/walkthrough/rounds.csv`; data: `results/figdata/walkthrough.json`.

Run records: `none` `runs/e1/none/results.jsonl` attack line 3, honest line 1 (commit `2668c22`); `obt` `runs/e1/obt_b0.05_W0_d0/results.jsonl` attack line 3, honest line 1 (commit `2668c22`); `rep-default` `runs/e1/rep_cap200_th0.8/results.jsonl` attack line 3, honest line 1 (commit `2668c22`).

**Why this run (D46a).** Every OBT farm-then-lie log was searched for a run where the gate blocked an S_main order in a lie round. LLM-buyer experiments came first:

| experiment | OBT farm-then-lie runs | with a blocked order on the lie |
|---|---|---|
| e1 (scripted buyer, obt) | 108 | 90 |
| e2 (llm buyer, obt) | 5 | 0 |
| e2b (llm buyer, obt) | 3 | 0 |
| e2c (llm buyer, obt+planner) | 5 | 0 |
| e3 (llm buyer, obt) | 1 | 0 |
| e3b (llm buyer, obt+planner) | 1 | 0 |
| e5 (llm buyer, obt+planner) | 6 | 0 |
| e9 (scripted buyer, obt) | 3 | 3 |
| e9_calib (scripted buyer, obt) | 54 | 15 |

No LLM-buyer run qualifies: those buyers sized their S_main orders inside the headroom, so the gate never had to block on the lie (D46's E2 run is kept as `walkthrough_appendix`). The run shown is E1's scripted buyer at the chosen default config, seed 1, the fallback the request named.

## Key events (OBT run unless stated)

| round | event | what the log shows | source (file:line → field) |
|---|---|---|---|
| 1 | First claim | S_main#1.1 DELIVERY 20 units by round 3; the buyer orders 20 units ($100.00) citing it; gate BLOCKED (OVER_BUDGET), 20 units rerouted to S_backup; B $5.00, P $0.00 | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[0].offer, actions, rerouted_orders, B, P |
| 4 | First honored claim | S_main#2.1 PASSED (arrived from S_main: 1); B steps $5.00 → $10.00 | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[3].resolved, arrived, B |
| 5 | Budget in use | committed exposure P reaches B ($10.00 = $10.00) | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[4].B, P |
| 25 | The lie | S_main#25.1 DELIVERY 24 units by round 27 at $4.25 (the farm-then-lie defection; the supplier lies in rounds 25-28). OBT's buyer places no S_main order this round. `none` orders 21 units on it ($89.25, UNGATED); `rep-default` orders 21 units on it ($89.25, UNGATED). | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[24].offer, intent, actions; `runs/e1/none/results.jsonl:3` trace[24].actions; `runs/e1/rep_cap200_th0.8/results.jsonl:3` trace[24].actions |
| 26 | The gate's decision on the lie | OBT's buyer proposes 20 units citing S_main#26.1+S_main#26.2 ($85.00); gate BLOCKED (OVER_BUDGET): $85.00 exceeds B $65.00 − P $0.00; 20 units rerouted to S_backup. Over the lie, 3 S_main orders citing lie claims are blocked (57 units rerouted) and none executes. | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[25].actions, rerouted_orders, B, P; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[26].actions; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[27].actions |
| 27 | The lie's claims lapse | S_main#25.1 LAPSED: no executed order relied on it, so it costs nothing beyond the reroutes and B is unchanged ($65.00). All 4 lie DELIVERY claims lapse (resolved in rounds 27-30); failure events: 0. | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[26].resolved; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[27].resolved; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[28].resolved; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` trace[29].resolved; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` metrics.loss_bound.events |
| 50 | Final loss vs bound | loss from lies `obt` $6.50, `none` $53.75, `rep-default` $53.75 (`rep-default` never blocks here, so its run is identical to `none`); OBT damage $0.00 ≤ Σ L_e $0.00; OBT's loss splits into damage $0.00 + reroute premium $99.75 (vs its honest run) + resid −$93.25 | `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` − `runs/e1/obt_b0.05_W0_d0/results.jsonl:1` trace[49].cost; `runs/e1/none/results.jsonl:3` − `runs/e1/none/results.jsonl:1` trace[49].cost; `runs/e1/rep_cap200_th0.8/results.jsonl:3` − `runs/e1/rep_cap200_th0.8/results.jsonl:1` trace[49].cost; `runs/e1/obt_b0.05_W0_d0/results.jsonl:3` metrics.loss_bound.damage, sum_bound, reroute_cost; `runs/e1/obt_b0.05_W0_d0/results.jsonl:1` metrics.loss_bound.reroute_cost |

## Notes

- **The gate blocks, it does not clip.** An order either passes the gate table or is blocked whole (here OVER_BUDGET: its value exceeds B − P); the blocked quantity is then rerouted to S_backup by code. 4 S_main orders are blocked in this run (77 units rerouted; the trace logs the reroute count per round and the quantity is the blocked order's, which sums to `metrics.rerouted_units`).
- **`rep-default` equals `none` in this run.** Reputation never blocked an order, so the two runs are identical round by round; the figure draws both (rep-default dotted over none).
- **Why OBT's loss curve alternates after round 28.** After the lie, OBT's buyer orders from S_main on the opposite rounds to its honest run (one round out of phase), and a purchase is charged when it is paid, so the cumulative difference swings between rounds. That is payment timing, not loss: the run ends at $6.50 (`rounds.csv` has every round).
- **Loss from lies** per round is the cumulative cost of the run minus the cumulative cost of its honest run (same defense and seed); it ends at the run's loss from lies. It includes reroute premiums and trajectory differences after the lie, not only damage.
- **The bound applies to damage** (DESIGN §6), not to the loss from lies: OBT's damage is $0.00 against Σ L_e = $0.00; its loss from lies is $6.50. The figure draws Σ L_e from the round its failure event resolves.
- Claim ids are `S_main#<round>.<n>`: `.1` is the round's DELIVERY claim and `.2` its PRICE claim; each resolves at its deadline (PASSED, FAILED, or LAPSED when no executed order relied on it).
