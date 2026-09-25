"""Buyer agents. Scripted policies here; the LLM buyer is added in stage 8."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .env.beer_game import BACKUP, MAIN, BackupSupplier, BeerGame, GameConfig, Supplier


def base_stock(cfg: GameConfig, lead: int, z: float = 1.65) -> int:
    """Order-up-to level covering demand over lead time + one review round."""
    n = lead + 1
    return math.ceil(cfg.demand_mean * n + z * cfg.demand_sd * math.sqrt(n))


@dataclass
class OrderUpToBuyer:
    """Classic base-stock policy sending every order to one supplier."""
    supplier: str
    target: int

    def decide(self, game: BeerGame) -> int:
        return max(0, self.target - game.inventory_position())


def run_plain(cfg: GameConfig, seed: int, main: Supplier, supplier: str = MAIN) -> BeerGame:
    """No-defense environment loop: the buyer orders straight from one supplier, no claims."""
    game = BeerGame(cfg, seed, {MAIN: main, BACKUP: BackupSupplier(cfg)})
    lead = cfg.main_lead if supplier == MAIN else cfg.backup_lead
    buyer = OrderUpToBuyer(supplier, base_stock(cfg, lead))
    while not game.done:
        game.begin_round()
        main.offer_message(game.round, 0)
        q = buyer.decide(game)
        if q > 0:
            game.place_order(supplier, q, game.round + lead)
    return game
