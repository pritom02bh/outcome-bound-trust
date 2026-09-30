# E5 v1: superseded (cross-run reply reuse)

**Superseded: cross-run reply reuse** (DECISIONS D37a). In v1 the paid-reply cache was keyed by prompt only, so a
buyer prompt byte-identical to one already paid for in another run or scenario was answered with that earlier reply
instead of a fresh sample: 134 of Luna's 1,200 buyer calls, 70 of Terra's 600. v2 (`results/e5/`) reruns every buyer
run with a run-scoped cache and adds Terra `none`. The extractor eval is per item (no cross-run reuse) and is kept.

Kept unchanged for reference: `e5/report.md` (the v1 report), `e5__luna/`, `e5__terra/` (per-eval tables).
Run data: `runs/e5/_v1_shared_cache/` (local).
