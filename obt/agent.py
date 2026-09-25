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


class ScriptedClaimBuyer:
    """Deterministic buyer that works from claim cards (the memory view), not raw text.

    Takes S_main's offer when it's no pricier than backup and not wildly more than
    it needs; backup covers the rest. It never checks claim status itself, so
    what stops a bad order is the gate, not buyer caution.

    Under OBT it "pulses" (DECISIONS D10): it only accepts when nothing from
    S_main is pending, and asks for a lot worth the budget it expects once the
    current order resolves. B(c) grows with the largest honored claim, so
    overlapping small orders would keep it pinned near b0.
    """

    def __init__(self, cfg: GameConfig, headroom_aware: bool = True, slack: int | None = None) -> None:
        self.cfg = cfg
        self.headroom_aware = headroom_aware
        self.slack = int(2 * cfg.demand_mean) if slack is None else slack
        self.target = base_stock(cfg, cfg.main_lead)

    def act(self, view, api) -> None:
        cfg = self.cfg
        obt = self.headroom_aware and view.defense == "obt"
        need = max(0, self.target - view.position)
        dels = [c for c in view.offer if c.template == "DELIVERY"]
        prices = [c for c in view.offer if c.template == "PRICE"]
        vague = [c for c in view.offer if c.template is None]
        got = 0
        if dels:
            q = sum(c.slot("qty") for c in dels)
            p = max((c.slot("unit_price") for c in prices), default=cfg.main_price)
            ok = need > 0 and p <= cfg.backup_price and q <= need + self.slack
            if obt:
                ok = ok and view.track[MAIN].pending_exposure == 0
            if ok:
                cites = [c.claim_id for c in dels + prices]
                rec = api.order(MAIN, cites)
                if rec is not None and rec.was_executed:
                    got = rec.qty
                    api.note(f"Relying on S_main lot of {rec.qty} by round {max(c.slot('by_round') for c in dels)}",
                             [c.claim_id for c in dels])
        elif vague and need > 0:
            # Believes the vague pitch and orders its usual amount against it.
            rec = api.order(MAIN, [c.claim_id for c in vague], qty=min(need, int(cfg.demand_mean)))
            if rec is not None and rec.was_executed:
                got = rec.qty
        if need - got > 0:
            api.order(BACKUP, qty=need - got)
        usual = int(cfg.demand_mean)
        if obt:
            tr = view.track[MAIN]
            # Budget expected once what's pending resolves, assuming it's honored.
            projected = max(tr.budget, tr.b0 + api.pending())
            api.request(min(2 * usual, int(projected // cfg.main_price)))
        else:
            api.request(usual)
