"""Stage 8 acceptance: LLM buyer under OBT with an honest S_main vs the scripted backup-only policy.

Local models only. Usage: python -m eval.stage8 --model gpt-oss:20b --seed 1
"""
from __future__ import annotations

import argparse
import json
import time

from obt.agent import BackupOnlyBuyer, LLMBuyer
from obt.attacks.suppliers import make_supplier
from obt.env.beer_game import GameConfig
from obt.extractor import LLMExtractor
from obt.llm import LLM, RUNS
from obt.sim import Sim, SimConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rounds", type=int, default=50)
    ap.add_argument("--defense", default="obt")
    args = ap.parse_args()
    cfg = GameConfig(rounds=args.rounds)
    tag = f"stage8_{args.model.replace(':', '-')}_{args.defense}_s{args.seed}"
    llm = LLM("ollama", args.model, cache_dir=RUNS / "cache", run_tag=tag)
    t0 = time.time()
    buyer = LLMBuyer(llm, cfg, args.defense)
    res = Sim(SimConfig(game=cfg, defense=args.defense), args.seed, make_supplier(1, cfg, args.seed), buyer,
              extractor=LLMExtractor(llm), scenario="1_honest").run()
    wall = time.time() - t0
    base = Sim(SimConfig(game=cfg), args.seed, make_supplier(1, cfg, args.seed), BackupOnlyBuyer(cfg)).run()
    out = {"model": args.model, "seed": args.seed, "rounds": args.rounds, "defense": args.defense,
           "llm_cost": res.total_cost, "llm_costs": res.costs, "backup_only_cost": base.total_cost,
           "beats_backup_only": res.total_cost < base.total_cost, "metrics": res.metrics,
           "llm_calls": llm.calls, "llm_tokens": llm.tokens, "llm_latency_s": round(llm.latency, 2),
           "wall_s": round(wall, 1), "trace": res.trace}
    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{tag}.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: v for k, v in out.items() if k != "trace"}, indent=1, default=str))


if __name__ == "__main__":
    main()
