# Commit map (history cleanup, 2026-10-08)

The repository history was rewritten once, on 2026-10-08, before the repository was made shareable: an assistant co-author line was removed from commit messages, and local assistant-instruction files and raw TLC logs (`spec/results/**/*.out`, `*.log`, `spec/results/aborted/`) were removed from every commit. Every other file is unchanged, but every commit hash changed. Run records (`meta.git_commit`), `results/INDEX.md` and `docs/DECISIONS.md` cite the old hashes; this table maps each old commit to the current one.

| date | old | new | subject |
|---|---|---|---|
| 2026-09-25 | `c6e690e` | `0c4a0d9` | setup |
| 2026-09-25 | `6e9a575` | `10954f7` | stage 1: types + ledger |
| 2026-09-25 | `0197056` | `c1bbdee` | stage 2: environment + oracles |
| 2026-09-25 | `e1603a3` | `6fa6469` | stage 3: verifier |
| 2026-09-25 | `1a0b79e` | `c37329f` | stage 4: budget + gate |
| 2026-09-25 | `814db72` | `389bb65` | stage 5: dependency tracker |
| 2026-09-25 | `3c0132a` | `25d37b3` | stage 6: scripted attackers |
| 2026-09-25 | `5a568ee` | `18bd6f2` | stage 7: extractor + memory view |
| 2026-09-25 | `a968f2f` | `e03bc89` | stage 8 wip: LLM buyer, budget math in view |
| 2026-09-25 | `37bb7cf` | `6f686bc` | stage 8: LLM buyer agent |
| 2026-09-25 | `5521aed` | `fc35936` | stage 9: TLA+ spec |
| 2026-09-25 | `2c00a0c` | `47cc6e5` | stage 10: eval harness |
| 2026-09-25 | `ab37e81` | `0c02f28` | fix F0: freeze old state |
| 2026-09-25 | `b818df7` | `90d0771` | fix F1: fixed round order |
| 2026-09-25 | `000b7ba` | `bae766e` | fix F2: gate claim-action binding |
| 2026-09-25 | `749930c` | `93e5e7c` | fix F3: verifier receipt allocation and grace |
| 2026-09-25 | `23474e2` | `a891ae6` | fix F4: remediation in code |
| 2026-09-25 | `543ff93` | `5bba3e2` | fix F5: extractor hardening |
| 2026-09-25 | `193f0b6` | `46317d5` | F6 wip: runtime invariant monitors (I1-I4, I6, I7) with tamper tests |
| 2026-09-26 | `4a774ee` | `a7d31c9` | fix F6: invariants, monitors, mutants |
| 2026-09-26 | `eab4835` | `16e3261` | fix F7: loss bound |
| 2026-09-26 | `41613af` | `254cb95` | F7 follow-up: differenced loss decomposition and price of safety |
| 2026-09-26 | `d33ba49` | `ca9ee62` | fix F8: scenarios 11 (extraction attack) and 12 (Sybil re-entry) |
| 2026-09-26 | `87d673a` | `dda8786` | fix F9: reputation baseline |
| 2026-09-26 | `c8b0b0e` | `6e30d65` | F10: frozen message bank and extractor dataset (spot-check pending) |
| 2026-09-26 | `531282a` | `4372a97` | F10: re-apply run-pool grounding filter with final F5 patterns; regold |
| 2026-09-27 | `a2a7035` | `a5348b9` | F10 redo: bank v3 after spot-check v1 failed (30/40) |
| 2026-09-27 | `3fab52f` | `1f18c0f` | F10: held-out reader test, hard-phrasing subset, F5 deadline guard in code |
| 2026-09-27 | `9fda758` | `4179e5f` | fix F10: message bank and extractor dataset (spot-check v2 40/40) |
| 2026-09-27 | `b1bce19` | `b8a8c89` | fix F11: real A2A transport |
| 2026-09-27 | `7a850f5` | `d26e419` | fix F12: reproducibility |
| 2026-09-27 | `2668c22` | `7288ad6` | E1 harness: ablation grid runner, Pareto summary, results tables |
| 2026-09-27 | `3d44b8a` | `7d8dd3d` | E5 prepare-only paid projection; DESIGN §10 evaluation definitions |
| 2026-09-27 | `eaec6b1` | `5ba1241` | eval.run: --sim SimConfig overrides (typed, unknown fields refused) |
| 2026-09-27 | `4886e3a` | `6b3909c` | E1 run: 54 points x 36 runs, 0 invariant and 0 loss-bound violations |
| 2026-09-27 | `2d1cfa0` | `8426e21` | E2 setup: reputation variants as separate defenses; stop at the first violation |
| 2026-09-28 | `a4eeafa` | `1190fe1` | PROGRESS: E1 approved; E2 seed 1 done (0 violations) |
| 2026-09-28 | `b8113d1` | `9471b0b` | Final-report statistics: bootstrap CIs over seeds, utility cost first, OBT damage vs bound |
| 2026-09-28 | `bce6c49` | `6f32de5` | E2 seeds 1-2 done (144 runs, 0 violations); results rebuilt |
| 2026-09-28 | `e246fe2` | `6fd2843` | E2 done: 216 runs, 0 invariant and 0 loss-bound violations; final CI report |
| 2026-09-28 | `516d12b` | `995d34c` | Separate extractor model (E3, D28): qwen3 buyer, gpt-oss extractor |
| 2026-09-28 | `8161e8c` | `df32b44` | E4 script: both local models on test + hard subset (with/without guard); e4.md |
| 2026-09-28 | `a7e7463` | `2279597` | fix D21a: kept-promise counterfactual keeps early deliveries |
| 2026-09-28 | `ae82566` | `edb7b0d` | E6: adaptive attacker search against OBT; D21a recheck (no number changed) |
| 2026-09-28 | `b4c13bb` | `d77900e` | E6 done: 10,000 evaluations, max damage/bound 0.857 (no STOP); e6.md |
| 2026-09-28 | `daa8867` | `099abea` | E6: confirmation of the found attackers with the gpt-oss extractor over A2A |
| 2026-09-28 | `0a48044` | `a6739c4` | Trust-over-time figure, scenario-9 utility table, utility cost as % of honest cost |
| 2026-09-28 | `7ade3d3` | `3bf081c` | E2b harness: frozen trust-aware buyer view (D30), reputation score in trace, E2b report and overlay figure |
| 2026-09-29 | `1d555a7` | `810f843` | E2 extra-seed reporting (per-row seed counts) and Enron candidate prep (D31) |
| 2026-09-29 | `88b8efd` | `cfff0af` | D31: none for seeds 4-5 on honest and noisy-honest, so utility cost uses 5 seeds |
| 2026-09-29 | `ee550bc` | `c9bb49e` | E2b done: 30 runs, 0 violations; trust-aware view barely changes LLM buyer behavior |
| 2026-09-29 | `3264310` | `be84363` | D32: code order planner (obt+planner, rep+planner); TLA+ buyer already covers it |
| 2026-09-29 | `546c76b` | `2ec2d9e` | D33 reputation lock-out grid runner (n0 x theta x cap), non-locking front and D22-rule pick |
| 2026-09-29 | `86369ae` | `4c1d649` | E2c report: merged 5-seed CI with E2, trust-over-time panels |
| 2026-09-29 | `24e5975` | `960341a` | D33: exclude never-trading reputation configs (rule intent); choose n0 18, theta 0.9, cap 200 |
| 2026-09-29 | `3535c74` | `e7d07d8` | Enron prep: resumable, size-checked download (first attempt stopped at 320 of 443 MB) |
| 2026-09-29 | `469a80c` | `ba8fdf1` | Enron prep: decode quoted-printable bodies (declared or not) so candidates are clean sender text |
| 2026-09-29 | `e56cd92` | `ee6d639` | Enron candidates: 100 unlabeled rows (decoded), source and version recorded |
| 2026-09-29 | `f9cee0b` | `a5c245f` | Enron: stratified sample (50 delivery-like + 50 price-only), is_commitment column, per-stratum eval (D34) |
| 2026-09-29 | `8c0230e` | `d8f2437` | D34: Enron stratified sample, extractor behavior on real text, per-stratum metrics |
| 2026-09-29 | `fe49b3e` | `c61fb67` | Enron: stratified 50+50 sample with is_commitment column (unlabeled) |
| 2026-09-29 | `5103d2a` | `e0db09e` | A2A: keep idle connections open for an hour (uvicorn's 5 s default raced with LLM-buyer gaps; E2c crashed a... |
| 2026-09-29 | `e181454` | `bbcedc2` | E2c spans two commits (keep-alive fix at run 68): noted in D25 and the E2c report; 24/24 scripted runs iden... |
| 2026-09-30 | `b23cb69` | `ef38067` | D32a fix (OBT variants extract on the LLM-buyer path); D35 overnight chain: paper assets, horizon check, E3b |
| 2026-09-30 | `8aebb90` | `16495cf` | Attack loss uses only seeds with every attack scenario (none's utility-only seeds 4-5 were being averaged);... |
| 2026-09-30 | `5d935e8` | `a31185c` | D36: budget growth multiplier k (B = b0 + k x max honored); E7; E3 loss split into damage + reroute + resid... |
| 2026-09-30 | `b6efe2d` | `9607dae` | D36a: K as a TLA+ constant; K=1 reproduces quick and A' exactly; K=2 passes there but is vacuous (probe: bu... |
| 2026-09-30 | `f5a9121` | `81b7faf` | E3b final + refresh: results/ and paper/ rebuilt after the overnight chain (0 violations); loss-fix check: ... |
| 2026-09-30 | `790bb62` | `c81d75d` | D36b: B0=1 configs at k=1 pass with both non-vacuity witnesses; at k=2 the budget never binds once trust is... |
| 2026-09-30 | `e8b9618` | `46681d9` | D36b outcome: MaxQty constant (default 2); strict non-vacuity fails at k=2 even with MaxQty=3 (exhaustive, ... |
| 2026-09-30 | `91acfd3` | `3a94e94` | D37: E5 setup: reasoning_effort=low on paid calls, verified prices, per-call cost ledger, $16 hard stop, D2... |
| 2026-09-30 | `5d9d9ae` | `e6f24ec` | E5 done (Plan B, paid): 36 runs, 0 invariant / 0 loss-bound violations; spend $3.27 of $16 (ledger); result... |
| 2026-09-30 | `c706ade` | `54d8421` | D37a: run-scoped paid-reply cache (run id + config + call index; resume only, no cross-run reuse); archive ... |
| 2026-09-30 | `f0daeb6` | `f2d47b7` | E5 v2 done: 48 runs, fresh sampling (0 cross-run reuse), 0 invariant / 0 loss-bound violations; spend $9.18... |
| 2026-09-30 | `d5327b8` | `fbbbb35` | results/INDEX.md: one-page index (experiment, run commit, report, headline); generated listing renamed to r... |
| 2026-10-01 | `5b588cd` | `08a245f` | D38: Enron labels (drafted with LLM assistance, verified row by row by the author) and eval: 0 wrong claims... |
| 2026-10-01 | `96d2174` | `f62fe08` | Paper assets from results/ only: LaTeX tables for E5 v2, Enron and bound tightness (E7 budget_k regenerated... |
| 2026-10-01 | `d03460d` | `6e2f64e` | D39: align NUMBERS.md and DESIGN §10 with the paper's RQs (RQ1-RQ6 + Section 6 verification); drop 'price o... |
| 2026-10-01 | `7900846` | `8c56096` | Paper pack v1.3 from results/ only: NUMBERS.md, tables (.tex + .csv), figures (.pdf + .png), results_all.xl... |
| 2026-10-01 | `f1795a1` | `fd0146e` | D40 loss per 100 S_main units; D41 overnight batch: E5 seeds stage (no harness cap, retry transient, stop o... |
| 2026-10-01 | `298343e` | `ade6de4` | v1.4-results: E5 seeds 2-3 (paid, D41), loss per 100 S_main units (D40), full refresh; every unaffected num... |
| 2026-10-01 | `20cab4c` | `318252d` | v1.4.1: loss per 100 S_main units (D40) rejected for the paper and removed from every paper-facing output (... |
| 2026-10-01 | `a3ce052` | `b5a4bd6` | D42: annotator package (blind spot-check and Enron files, INSTRUCTIONS with fresh worked examples) and eval... |
| 2026-10-01 | `cdaebbf` | `10b541f` | D43 E8: LLM adversarial supplier (gpt-oss, black-/white-box, Sybil, plan enforced by the env, frozen prompt... |
| 2026-10-01 | `10d5c60` | `25ed8a5` | D42 update: spot-check made informative with 10 seeded v1 errors (50 rows, fixed-seed shuffle, no origin ma... |
| 2026-10-01 | `62297f4` | `8477004` | D43a: A2A client timeouts raised (30->300 s HTTP, 60->330 s wait): E8's LLM supplier composes offers with a... |
| 2026-10-01 | `1fddf61` | `f7a57c0` | E8 runs.csv: S_main share rounded to 6 decimals (a 17-digit float doesn't survive the workbook round trip; ... |
| 2026-10-01 | `6af5afc` | `893c813` | v1.5-results: E8 LLM adversarial supplier (D43), refreshed NUMBERS.md (RQ3), tables, workbook, paper pack; ... |
| 2026-10-01 | `c6c2d93` | `9656160` | E9 (D44) WIP on branch e9: cloud domain behind the domain flag (CloudGame, SLA template, capacity item, one... |
| 2026-10-01 | `312b95e` | `06f3f3d` | e9.sh: commit without a co-author trailer (user request) |
| 2026-10-01 | `d2fc85f` | `af55539` | Merge E9 (D44) into fixes-v2 |
| 2026-10-01 | `ad2755d` | `1644404` | Tests follow D44: SLA joins the fixed template registry; the hand-built pre-D36 config blob also drops the ... |
| 2026-10-01 | `4f6e24b` | `21c98ac` | e9.sh: run the equivalence script from a neutral directory (eval/numbers.py shadowed the stdlib module; onl... |
| 2026-10-01 | `3f356be` | `55ab9d4` | v1.6-results: E9 second domain (cloud/API capacity, D44): supply domain proven byte-identical to v1.4.1-res... |
| 2026-10-01 | `bb9655a` | `fecd178` | v1.6-results (corrected): E9 a-priori ratio is damage over the run's summed a-priori bounds (max 0.357, was... |
| 2026-10-01 | `bed2b1c` | `67bda24` | D45: E9 calibration grid (OBT b0 x k, reputation D33 grid) and E1's selection rule, recorded before any cal... |
| 2026-10-01 | `401793f` | `ee76198` | v1.7-results: E9 calibration (D45): OBT b0 x k and reputation D33 grid on the cloud domain, configs chosen ... |
| 2026-10-01 | `dbaf4fb` | `9b051cb` | D45a: extend the E9 OBT calibration grid (b0 40%/80% x k 1,2,4; k 4 at every b0); same rule, edge rule fixe... |
| 2026-10-02 | `d5bf4e8` | `7507434` | v1.8-results: E9 extended OBT calibration grid (D45a): 18 points, pick unchanged (b0 20%, k 1; on the k = 1... |
| 2026-10-02 | `e3283ca` | `8b1d7ee` | v1.9-final: independent annotator (D42a): spot-check raw agreement 0.98 (kappa 0.935), seeded-error detecti... |
| 2026-10-06 | `a4a3055` | `e711d70` | v1.9.1-paper: walkthrough figure (D46) from existing E2 logs: farm-then-lie seed 1, obt/none/rep-default; r... |
| 2026-10-06 | `8268914` | `0f01506` | v1.9.2-paper (D46a): walkthrough rebuilt on a run where the gate blocks the lie (no LLM-buyer run does; E1 ... |
| 2026-10-06 | `adc4f3b` | `fe0a846` | v1.9.3-paper: gate activity report (D47) from existing logs: 243 OBT/obt+planner LLM-buyer runs, 469 of 5,4... |
| 2026-10-06 | `04e5c81` | `613042c` | remove superseded pack zips; kept in git history |

Full 40-character hashes, one pair per line (old new):

```
c6e690ed5c2258002419617bc8025aad33b90fb2 0c4a0d94a52b63a8ccd98a2d5ae15bee256abfe8
6e9a5752134779c268dc677c1a8765c3abd7ebbf 10954f750723f17a6cb3b6bc568520571e75c8eb
0197056d213001b76e202835255ee52a79804105 c1bbdee6ae4c32b56d4ece990eb1edf57482c84b
e1603a33cdb7c60cb57923e9d68a3f6680a79819 6fa6469b2023d7d17d1fdc80bd4061dc26f31d98
1a0b79e46e4e5df2ecbb4c55b021142b29636a6a c37329f22d78594f0cc0299668e69a65f8a17c50
814db725354fe99e76ec548c455f006283aa6818 389bb65e07e0fd13f2c37ce6b9317eacc0c210d8
3c0132a50bfcc2a90a5879a841552552cf52049a 25d37b327a3d141c0ef2cb5d76be4dc7ca1d1789
5a568eef6af67024c16cfd490bb68de121fd56d6 18bd6f2dfab096ae55708dda4b34a4bbf5e21303
a968f2f69731db8e44cfefe3e5483a6beb480a47 e03bc895efe566dfbaa0654f174292b1231f552c
37bb7cf7dee5a6a032259b28b4c18b9835493fe5 6f686bc198ed73e9c1900a5cb0fcc1c932f35b9d
5521aed620f615061394d2d3e8fac1b12df10798 fc35936151b00f00385ca1dcda5864740d251f51
2c00a0c3a075b06fe2e2561def01729349c2969d 47cc6e55ecfc387403907774fffd459521acc8de
ab37e81cc19932fab01e0315134f6d78d8054268 0c02f28cbf3d77d24f1654dddc7c381c3bc867e1
b818df7782f5e7f00f0b7ed6e03d603facb55c89 90d0771ac72fe442ca6477371e63c84b930cf0a5
000b7ba8600e5f5a883a05932dc0fac4d424e341 bae766eba28dd5c7a191e5eefde2aa9c24f511bf
749930cfdf35619f8726aa3eb7649cbca62f02b7 93e5e7c4c41c70433d6f42287a90a04f3e48790b
23474e25fc30e7079a8370c6a4aabc3a56b52b88 a891ae6035492b22e1290f4fbc4f9c378639b67a
543ff93f8f267c23dd4b8a724f8836e4d2b5ed70 5bba3e2ee28e3f2aa304dfd333d204a8307b2c87
193f0b65c2fd151519c0173b3f467081b0c5ef3c 46317d5cd153acb55a0d549d92442cf0145d67c4
4a774ee7d8400c7e4bbdccb749868c5dba6f2547 a7d31c97f2aa51d72410ec7ea32819916affd050
eab48353b0a499f2835e89a414ee51643e07734c 16e3261914b4c5d3b050203b242d097273f757a2
41613af1ec8ed900b5e44b0f667e19643ef901cb 254cb95d0b86cf9c315664615656667476cc5774
d33ba498056fea9f0e9f10b6e7e87b91070fb97d ca9ee62cfc5a077188e31b343d5184cc2240eacd
87d673abd6499df8158a4566c1633cdb81754ad5 dda8786f0883ffddbf3ebe812b8a5ef878ccaffe
c8b0b0e3e06ac1d29273fb796c5186b5d189329e 6e30d657e2058e2e9e6d79cecd0e654fac56ee3f
531282a6d5cf6d95751802c128c587239d1993a5 4372a9770e768e1ef179454a3e0fff8baeab84e8
a2a7035a9b659a99869ccae232eaa014813878b6 a5348b98dac309c32e63550847aa657538490e23
3fab52fb67a001b8545658ae1460c976eabc67ed 1f18c0f1ca2681f4269a5f6e0f9c3eef29121b1d
9fda7585293cbdf1ceb1df3af69756a977405bfd 4179e5fe9624c01d2a0ec5b17cdd6502a1c3876f
b1bce195d0d570b41cae7362fe7c3aa9bba67205 b8a8c89a754915321c99301a5b98f9ba981091a1
7a850f50c9efbc80f56d5f95d64fd28941c670e4 d26e4197075eab1c8e493a9a8407f63d5922530a
2668c22003017fa42dd1d5a7da35e6c70f0462fd 7288ad6ecaab78304ec755284c2baca046c76112
3d44b8a38d29b4005e9786f78b4b657329db34da 7d8dd3db328895f3255c20de677e356d91864d94
eaec6b1eb4f70bf41f9e55243c533ca3f1a94011 5ba1241f7b9dcbe98a2e5b6502d76126b5325492
4886e3a2fb907b5300c5e60dbe7d67ad2ee4cde1 6b3909c810f199e26e6ec9ccc2febb6f012757d6
2d1cfa06f2870f050f7491f10ac5131fe461f2cb 8426e21609be1fc49ebebec9a647c231579ea19b
a4eeafab343770ef304185516e9a6572f8598bbd 1190fe14b693a0fe5357f0276b1a83a381f58125
b8113d1dd07018324c2df0b9854d1cd3ac6bb3d2 9471b0b2b0a7a0bd20a44883af21bbf43379f6e4
bce6c49a6843fd9012ea76bbe75f9d6593731b46 6f32de502b948b0b693fdd0122720dc9f9a5241c
e246fe2077e4ceb9805243897ba8a5e37e28b450 6fd2843169d9baf2967ac8b73e1e7ba2c5b7e538
516d12ba94b1243d73fbff86b77075f720dde5af 995d34c35451c5ac26b00e84ce2e57f80b34a25f
8161e8cffdc3a9ef47b937c40eef372d7cab292b df32b44f81a642b49544646be9ab11095933194d
a7e7463cfa656292cf8474b813fc1409f5e6d071 22795970fdb4da84c5e0be42dd94362b2e9cb50c
ae82566eb6855905136e02b589ec3ba74d73f75c edb7b0d3d725b85cee476a318ae003add3dacaf1
b4c13bb4bf33e25e44e56af0846f052fd3cfa5f8 d77900e2b3b0205ab293bd8ef70a9696d2d7245d
daa8867f771d96b80f4248c254a15f8146dfcd9f 099abea8081e0822681f6553eea9f337a0987647
0a480445b189bb8a1b16afa2c57c11e6f8c46b98 a6739c40e029e6e787a5f1f6bfb45048758b033f
7ade3d3e92de96d9a207cc4badb289c1385f950e 3bf081c76b5a42280ef46da29c20e0780f0e038f
1d555a7e32dc83a709d0d8f7542122c7fb5c0902 810f8439c0fd75efe8da766ebab570415426a7ee
88b8efda2e67108de3edc1432780af5bc47b998d cfff0afffe06b8fc505cd7d2549621d80d84a626
ee550bcfa119fd0139a6b776c56b892f45ab1b2c c9bb49e939d272fcec7a06f98d8aa38ec3891c67
3264310ef6a84b1c8b9f35d5caf856afccf128b7 be84363fe85e467dac4f7f5a7adac2979827da6f
546c76bfb4743eadd53c7cc3212776bd1816276b 2ec2d9ed717bf7ea0453924084e680f44458447f
86369ae28b26a3d469e4e79e3c9e16e5267ccf84 4c1d649af1bd0014ce01f303b5e2dba6aebfa9d4
24e5975fce973d20cf70da32cdbaeb06d8be19ba 960341a0534bdcbdd5174443b7e929cf1b0035a5
3535c74acfd0f7ea7abcd5387a28b65d5a8984d6 e7d07d8e220fdc359f93b0c54f1dca164d5d98c4
469a80c1af2ef88e90920143a11aceb5e136a9df ba8fdf185d1ef07e7f7649f2249f5bf338df22d6
e56cd922a87f201ebc7cb876342448a5b73f91d9 ee6d63965e0b9e53aae17a44507a0ab62c268209
f9cee0b1a6ebd8c1fd02b93bf43f4dc3f8a9df1b a5c245ffae7d1fd3dda6977ec2d7c0daca253628
8c0230e44a385196dcdb6239ed2c8216970c4eb1 d8f243758374cd0bde6202c22d87a0adc809853b
fe49b3e1afc61db4dfc1e3b2740b3a408b35c46b c61fb67cd14148258d5dc75ff9981221217b2e5d
5103d2a8fa0386d2f0142dc178f8d3f1a9b54d47 e0db09ecf9515da528c3bbdb83c1143c86739769
e181454f9731e7db9d2542b236cd7e81bb571d27 bbcedc2f388fbd76c4da881086ec9cb7ec616461
b23cb6909bcfd7d6d4305dd78e7985738daede37 ef38067f46c3f178c52b5b998bfa52803c22b498
8aebb90d8c0354513cef4575e6037f5db1d57394 16495cfcf3a7b0bc4f31140293e9d273f0644bae
5d935e8055fa1c0bc450f6a2fd75ebd237fab1a5 a31185cd342a67a3a6a142da816b726866ed1cc9
b6efe2d0618e06a540179eeb2b34757fc84f4597 9607daefa286e2ee8ddef6094af0e3d65fc84ef8
f5a9121e41c2df069972791dae6d86f0518d60dc 81b7fafad167f3a849ec15981f5ecfddd881419c
790bb629878aa1d7297e7dd9d4e0c6874dc6579a c81d75d6ceccdcefe93062f042bdf1b539938acb
e8b96183024bfdb997bf9ef64509f3a117103334 46681d9a1cfc3073763f11c1defbe6890c83b1c6
91acfd3dff66c9005db26c332d5504567b7e4693 3a94e9480785c92ec7c602a38ee8d4cd5dc06172
5d9d9ae11e33fc197a65a2509b4976b4314ecda4 e6f24ecfefdf849a1a92a138acaa0b839e7b8529
c706ade052373a9d06ad85eeec083855fb182e28 54d8421974ba41352f89a5a31dd5df4338a50bfc
f0daeb665ad4a75d7c5c0a9bd77576bd001b6cb1 f2d47b79bfd8a1bfaec73e8344c6c56b3110155a
d5327b832c3f0c9d43c4584317917595e6e341e6 fbbbb35501a3136690d80744a8f46aa23f2508c5
5b588cdbfb327250edba2e1e6f1070f06445c537 08a245fd5c448201dc3507d1c9bc2a77bd99f456
96d21740c59bf91ccd524c2b7f305f949fe75ffa f62fe086cf45a86cd4cdf3ac559cbb4af972f401
d03460d8526548b1d8a23b985c709aa9b3d4c70d 6e2f64ede3c3a3b7df20e3ceba4d0f19bf24b8cc
7900846817f39cfcf412e0e4e21d40bcd46989ac 8c56096388f799b236f376d408f4a8f073cfefa9
f1795a1e2d46df5b482c0ff882a8a455219b7124 fd0146e9019c8c4a7d8bc1afa3e31d9a339a9267
298343efe4e1feb2f8b81b7d36abf7a226b67ccb ade6de45198d2b1099cc310c3ef56425bdbc4789
20cab4c896076694bd967b5e75988dd564c19c49 318252d931a2312f68b6050676dd799be726afb6
a3ce052d292aad8c7f15b1aa3f14d5b75a5006c4 b5a4bd60632c52cfa1e5b604a0cec2e9c00e3a1c
cdaebbf8922a0119faa4a0d04d2f546936d3c1da 10b541f4aa96238f21ac44b39d04d3ac9fb18a15
10d5c6094f8f66608ba11751d571d0dca50fce3b 25ed8a53cfd70b7c90747673c81d3f8535d1a2fa
62297f4efa1091380cdb348bdd7e59dd8c7a729c 8477004026c060de3fa2b5156db3bccb838ee0b6
1fddf61ce88911681ec813ce5fe9045621d20b5f f7a57c00cab5a78c93ad896230a143df723fd0cc
6af5afc3f00b801297b4fc8f20676d2233bc14e3 893c813e3d4d5c4b316e7b54fe5301d84f6304ec
c6c2d93bb62a85fc64621c98d6ae061e8c219fbf 965616039c85b14a2371802b95f1ae8767f8c3cf
312b95edf30734004a7e0afb9eb4b8906a917986 06f3f3d409f772612ebfa1a857d8665296bc39ba
d2fc85fd9dced7ba9f602ecfb19962a011992e7c af55539a0850066f429721f3749dcb673e525508
ad2755dfcf8732b7c09a19fd7503c6953c171c68 16444042ec62c17e419431682fdf6c9de5265c71
4f6e24b1f8cda85560e2132311744cc30479534e 21c98acc798dc8a4f2cfd86c3ac90bffc0c7acc0
3f356beb77ff23f028da079d60dc39d57bad574d 55ab9d4ce81228699097ce55f911a53c15d3b86f
bb9655afeb15262d510f9b9011ac7de8b0251d0d fecd17886e75860c99436af4d1c3161ded0dc23a
bed2b1cfb57c5d4c2a4196902b2ea3e441cb38b6 67bda24eee643e3c4da230a7701bdbfecf4f6a95
401793fb3ee4b8093236eb3e06e4e3ee089a2166 ee761980e8b7df31c67531b12978a751be2ba475
dbaf4fb8603ce0a9e441c28382bd30494bb41fc3 9b051cbf4e1d59007760631d057b2d2ffdf85a3a
d5bf4e8d8435825cd5dca7fb7ccf14ef43f67031 7507434eb5d074aa8049a7309b262280c736f42a
e3283caa0c0e610d2793f878742147aafd411a52 8b1d7eea506d70aaeab4e57dbfcb310e80777f29
a4a3055c8eca1c3b68e29d83984821a6eb07f01f e711d706f6777ac1694f5ad01605eca1f71ba78a
8268914cc416a65d5b000d0934be1f5611cd2f53 0f015069125584b00f5de6f27d9eaca497680aab
adc4f3be4b29b013a9785ac0347ac00b1d5b482a fe0a846181e0bc93eac2fb9b8331755f7f5d2fc5
04e5c810d1eb36eb2c61540b8e491d725363fc98 613042c9a209e26ec8491f1270938f5adb6fbf83
```
