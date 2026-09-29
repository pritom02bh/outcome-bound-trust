"""F11: real A2A transport. Suppliers are A2A servers with Agent Cards and per-agent bearer tokens; the buyer
is an A2A client; the counterparty id comes from the authenticated connection, never from message content."""
import httpx
import pytest

from obt.agent import ScriptedClaimBuyer
from obt.attacks.suppliers import SCENARIOS, Honest, make_supplier
from obt.env.beer_game import BACKUP, MAIN, GameConfig
from obt.sim import Sim, SimConfig
from obt.transport import A2ATransport, TransportError

G = GameConfig()


def run(n, transport, defense="obt", seed=0, rounds=None):
    cfg = GameConfig(rounds=rounds) if rounds else G
    sim = Sim(SimConfig(game=cfg, defense=defense, transport=transport), seed, make_supplier(n, cfg, seed),
              ScriptedClaimBuyer(cfg))
    return sim, sim.run()


def snapshot(sim, res):
    ledger = [(c.claim_id, c.counterparty, c.template, sorted((c.slots or {}).items(), key=str), c.status,
               c.source_msg_hash) for c in sim.ledger]
    actions = [(a.action_id, a.kind, a.counterparty, a.qty, str(a.value), a.status, a.reason, tuple(a.cited_claims))
               for a in sim.actions]
    return ledger, actions, res.total_cost, res.costs, res.trace


def test_transport_flag():
    assert SimConfig().transport == "inproc"
    with pytest.raises(ValueError):
        Sim(SimConfig(transport="carrier-pigeon"), 0, make_supplier(1, G, 0), ScriptedClaimBuyer(G))
    from eval.run import EvalConfig
    assert EvalConfig().transport == "a2a"


@pytest.mark.parametrize("n", sorted(SCENARIOS))
def test_inproc_and_a2a_give_identical_ledgers_and_costs(n):
    # F11 acceptance: every scenario, scripted buyer, seed 0.
    a = snapshot(*run(n, "inproc"))
    b = snapshot(*run(n, "a2a"))
    assert a[0] == b[0], "ledger"
    assert a[1] == b[1], "actions"
    assert a[2] == b[2] and a[3] == b[3], "costs"
    assert a[4] == b[4], "trace"


@pytest.mark.parametrize("n", [1, 3, 12])
def test_parity_holds_for_baselines_too(n):
    for d in ("none", "reputation"):
        assert snapshot(*run(n, "inproc", d)) == snapshot(*run(n, "a2a", d)), d


def test_agent_cards_declare_bearer_auth_and_one_identity_each():
    tr = A2ATransport(make_supplier(12, G, 0), G)
    try:
        assert set(tr.registry) == {MAIN, "S_main_2", "S_main_3", BACKUP}
        for ident, ep in tr.registry.items():
            card = httpx.get(ep.url + ".well-known/agent-card.json").json()      # public, no token
            assert card["name"] == ident
            assert "bearer" in card["securitySchemes"]
            assert card["securitySchemes"]["bearer"]["httpAuthSecurityScheme"]["scheme"] == "bearer"
            assert card["supportedInterfaces"][0]["url"] == ep.url
        assert len({ep.token for ep in tr.registry.values()}) == 4                 # a token per agent
    finally:
        tr.close()


def test_calls_without_the_agents_own_token_are_refused():
    tr = A2ATransport(make_supplier(12, G, 0), G)
    try:
        main, other = tr.registry[MAIN], tr.registry["S_main_2"]
        for token in (None, "wrong", other.token):
            with pytest.raises(TransportError):
                tr.call(main.url, token, {"op": "offer", "round": 1, "request_qty": 20})
        assert "text" in tr.call(main.url, main.token, {"op": "offer", "round": 1, "request_qty": 20})
    finally:
        tr.close()


class Impostor(Honest):
    """Claims in its text to be someone else; the gateway must not care."""

    def offer_message(self, round_, request_qty):
        text = super().offer_message(round_, request_qty)
        return None if text is None else f"From: {BACKUP} (identity S_main_2). {text}"


def test_counterparty_comes_from_the_connection_not_the_content():
    cfg = GameConfig(rounds=4)
    sim = Sim(SimConfig(game=cfg, transport="a2a"), 0, Impostor(cfg, 0), ScriptedClaimBuyer(cfg))
    sim.run()
    assert sim.ledger and {c.counterparty for c in sim.ledger} == {MAIN}
    assert all(m.counterparty == MAIN for m in sim.gateway.audit_log())


def test_sybil_identities_arrive_on_their_own_connections():
    sim, _ = run(12, "a2a")
    speakers = {m.counterparty for m in sim.gateway.audit_log()}
    assert speakers == {MAIN, "S_main_2", "S_main_3"}


def test_servers_are_shut_down_after_a_run():
    sim, _ = run(1, "a2a", rounds=3)
    for ep in sim.transport.registry.values():
        with pytest.raises(httpx.HTTPError):
            httpx.get(ep.url + ".well-known/agent-card.json", timeout=1)


def test_a_connection_idle_longer_than_uvicorns_default_keep_alive_still_works():
    # E2c crashed on httpcore.ReadError: uvicorn closes idle keep-alive connections after 5 s by default, while an
    # LLM buyer waits ~7 s between supplier calls, so the client could send on a connection being closed.
    import time
    tr = A2ATransport(make_supplier(1, G, 0), G)
    try:
        ep = tr.registry[MAIN]
        tr.call(ep.url, ep.token, {"op": "offer", "round": 1, "request_qty": 20})
        time.sleep(6.5)
        assert "text" in tr.call(ep.url, ep.token, {"op": "offer", "round": 2, "request_qty": 20})
    finally:
        tr.close()


def test_servers_keep_idle_connections_open_longer_than_any_buyer_gap():
    # The close/send race needs a keep-alive timeout shorter than the gap between calls; rule it out by config.
    tr = A2ATransport(make_supplier(1, G, 0), G)
    try:
        assert all(s.server.config.timeout_keep_alive >= 3600 for s in tr._servers)
    finally:
        tr.close()
