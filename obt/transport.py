"""Buyer <-> supplier transport (FIXES F11, DECISIONS D25).

`inproc` calls the supplier objects directly. `a2a` runs every supplier identity as its own A2A server on
localhost (a2a-sdk 1.x, JSON-RPC binding) with an Agent Card and a per-agent bearer token, and the buyer side
talks to them as an A2A client. Either way the sim sees the same three exchanges: the round's offer message,
an order (answered with the invoice price and shipping schedule, which go to the environment, never to the
buyer's context), and a payment notice.

Identity: the counterparty id of a message is the registry identity of the endpoint it arrived on (URL + that
agent's bearer token), never anything in the message. A supplier holding several identities (scenario 12) runs
one server per identity behind one host, which composes each round's message once and releases it only on the
endpoint of the identity it currently speaks as, exactly as the in-process supplier does.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from typing import Any

from .env.beer_game import BACKUP, MAIN, BackupSupplier, GameConfig, OrderRequest, Supplier, SupplierReply

TRANSPORTS = ("inproc", "a2a")
CARD_PATH = "/.well-known/agent-card.json"


class _DropTeardownNoise(logging.Filter):
    # a2a-sdk 1.1.5 logs this at teardown of every request answered with a single Message, the documented
    # immediate-reply pattern; the reply has already been delivered (inproc/a2a parity is exact, D25). Only
    # this exact message is dropped; every other SDK warning and error still shows.
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage() != "Dispatcher task is not running. Cannot wait for event dispatch."


logging.getLogger("a2a.server.events.event_queue_v2").addFilter(_DropTeardownNoise())


class TransportError(RuntimeError):
    pass


class InProcTransport:
    def __init__(self, main: Supplier, cfg: GameConfig) -> None:
        self.main = main
        self.backup = BackupSupplier(cfg)
        self.identities: tuple[str, ...] = tuple(getattr(main, "identities", ()) or (MAIN,))

    @property
    def speaker(self) -> str:
        return getattr(self.main, "identity", MAIN)

    def suppliers(self) -> dict[str, Supplier]:
        return {**{i: self.main for i in self.identities}, BACKUP: self.backup}

    def fetch_offers(self, round_: int, request_qty: int) -> list[tuple[str, str | None]]:
        text = self.main.offer_message(round_, request_qty)
        # The identity is read after the message: a Sybil supplier switches while composing it.
        return [(self.speaker, text)]

    def intent(self) -> dict | None:
        return getattr(self.main, "last_intent", None)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------- A2A


class SupplierHost:
    """One supplier behind one or more A2A identities. Composes each round's message once."""

    def __init__(self, supplier: Supplier, identities: tuple[str, ...]) -> None:
        self.supplier = supplier
        self.identities = identities
        self._round: int | None = None
        self._text: str | None = None
        self._speaker = identities[0]

    def handle(self, identity: str, req: dict) -> dict:
        op = req.get("op")
        if op == "offer":
            t, q = int(req["round"]), int(req["request_qty"])
            if self._round != t:
                self._round = t
                self._text = self.supplier.offer_message(t, q)
                self._speaker = getattr(self.supplier, "identity", self.identities[0])
            # Only the identity the supplier speaks as this round answers with a message (possibly none).
            return {"text": self._text} if identity == self._speaker else {}
        if op == "order":
            r = self.supplier.on_order(OrderRequest(str(req["order_id"]), int(req["round"]), int(req["qty"]),
                                                    str(req["item"])))
            return {"unit_price": r.unit_price, "shipments": [[q, a] for q, a in r.shipments]}
        if op == "payment":
            self.supplier.on_payment(int(req["round"]), float(req["amount"]))
            return {"ok": True}
        raise ValueError(f"unknown op {op!r}")


@dataclass
class Endpoint:
    identity: str
    url: str
    token: str
    card: Any = None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _card(identity: str, url: str, role: str):
    from a2a.types.a2a_pb2 import (AgentCapabilities, AgentCard, AgentInterface, AgentSkill, HTTPAuthSecurityScheme,
                                   SecurityRequirement, SecurityScheme, StringList)
    return AgentCard(
        name=identity, description=f"Beer Game widget supplier ({role})", version="1",
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url)],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["application/json"], default_output_modes=["application/json"],
        skills=[AgentSkill(id="supply", name="supply widgets", description="offers, orders and payments",
                           tags=["supply"])],
        security_schemes={"bearer": SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(
            scheme="bearer", description="per-agent token issued at registration"))},
        security_requirements=[SecurityRequirement(schemes={"bearer": StringList(list=[])})])


class _Server:
    """One identity's A2A server: Agent Card (public) + JSON-RPC endpoint behind its bearer token."""

    def __init__(self, host: SupplierHost, identity: str, token: str, role: str) -> None:
        import uvicorn
        from a2a.helpers.proto_helpers import get_data_parts, new_data_message
        from a2a.server.agent_execution import AgentExecutor
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
        from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
        from starlette.applications import Starlette
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse

        port = _free_port()
        self.url = f"http://127.0.0.1:{port}/"
        self.card = _card(identity, self.url, role)
        want = f"Bearer {token}".encode()

        class Executor(AgentExecutor):
            async def execute(self, context, event_queue) -> None:
                req = (get_data_parts(context.message.parts) or [{}])[0]
                await event_queue.enqueue_event(new_data_message(host.handle(identity, req)))

            async def cancel(self, context, event_queue) -> None:
                pass

        class BearerAuth(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                if request.url.path != CARD_PATH and not hmac.compare_digest(
                        request.headers.get("authorization", "").encode(), want):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return await call_next(request)

        handler = DefaultRequestHandler(agent_executor=Executor(), task_store=InMemoryTaskStore(), agent_card=self.card)
        app = Starlette(routes=create_agent_card_routes(self.card) + create_jsonrpc_routes(handler, "/"))
        app.add_middleware(BearerAuth)
        # Keep idle connections open for an hour: uvicorn's 5 s default races with an LLM buyer's ~7 s gaps between
        # calls (the client can send on a connection the server is closing), which crashed E2c once.
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                                                    timeout_keep_alive=3600))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started:
            if time.time() > deadline or not self.thread.is_alive():
                raise TransportError(f"A2A server for {identity} did not start")
            time.sleep(0.005)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


class RemoteSupplier(Supplier):
    """The environment's handle on a supplier reached over A2A (orders and payments)."""

    def __init__(self, transport: "A2ATransport", identity: str) -> None:
        self.transport = transport
        self.identity = identity
        self.name = identity

    def on_order(self, req: OrderRequest) -> SupplierReply:
        r = self.transport.send(self.identity, {"op": "order", "order_id": req.order_id, "round": req.round,
                                                "qty": req.qty, "item": req.item})
        # JSON numbers arrive as doubles: the float price is exact, integers are cast back.
        return SupplierReply(float(r["unit_price"]), tuple((int(q), int(a)) for q, a in r["shipments"]))

    def on_payment(self, round_: int, amount: float) -> None:
        self.transport.send(self.identity, {"op": "payment", "round": round_, "amount": amount})


class A2ATransport:
    def __init__(self, main: Supplier, cfg: GameConfig) -> None:
        self.main = main
        self.identities: tuple[str, ...] = tuple(getattr(main, "identities", ()) or (MAIN,))
        self._hosts = {"main": SupplierHost(main, self.identities),
                       "backup": SupplierHost(BackupSupplier(cfg), (BACKUP,))}
        self._servers: list[_Server] = []
        self.registry: dict[str, Endpoint] = {}
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()
        self._clients: dict[tuple[str, str | None], Any] = {}
        self.speaker = self.identities[0]
        try:
            for ident in (*self.identities, BACKUP):
                host = self._hosts["backup" if ident == BACKUP else "main"]
                token = secrets.token_urlsafe(24)       # issued per agent at registration
                srv = _Server(host, ident, token, "backup" if ident == BACKUP else "main")
                self._servers.append(srv)
                # The buyer discovers each agent from its public Agent Card.
                self.registry[ident] = Endpoint(ident, srv.url, token, self._run(self._resolve(srv.url)))
        except Exception:
            self.close()
            raise
        self._closed = False

    # -- plumbing
    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=60)

    async def _resolve(self, url: str):
        import httpx
        from a2a.client import A2ACardResolver
        async with httpx.AsyncClient() as hc:
            return await A2ACardResolver(hc, url).get_agent_card()

    async def _send(self, url: str, token: str | None, payload: dict) -> dict:
        import httpx
        from a2a.client import A2AClientError, ClientConfig, ClientFactory
        from a2a.helpers.proto_helpers import get_data_parts, new_data_message
        from a2a.types.a2a_pb2 import Role, SendMessageRequest
        key = (url, token)
        if key not in self._clients:
            headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
            hc = httpx.AsyncClient(headers=headers, timeout=30)
            card = next((ep.card for ep in self.registry.values() if ep.url == url), None) or await self._resolve(url)
            self._clients[key] = (hc, ClientFactory(ClientConfig(streaming=False, httpx_client=hc)).create(card))
        _, client = self._clients[key]
        try:
            async for resp in client.send_message(SendMessageRequest(
                    message=new_data_message(payload, role=Role.ROLE_USER))):
                return (get_data_parts(resp.message.parts) or [{}])[0]
        except A2AClientError as e:
            raise TransportError(str(e)) from e
        raise TransportError("no reply")

    def call(self, url: str, token: str | None, payload: dict) -> dict:
        """One raw exchange with an endpoint (tests use it to check that auth is enforced)."""
        return self._run(self._send(url, token, payload))

    def send(self, identity: str, payload: dict) -> dict:
        ep = self.registry[identity]
        return self.call(ep.url, ep.token, payload)

    # -- the sim's interface
    def suppliers(self) -> dict[str, Supplier]:
        return {i: RemoteSupplier(self, i) for i in (*self.identities, BACKUP)}

    def fetch_offers(self, round_: int, request_qty: int) -> list[tuple[str, str | None]]:
        out = []
        for ident in self.identities:
            r = self.send(ident, {"op": "offer", "round": round_, "request_qty": request_qty})
            if "text" in r:
                # The counterparty is the endpoint this reply came from, not anything the reply says.
                out.append((ident, r["text"]))
                self.speaker = ident
        return out

    def intent(self) -> dict | None:
        # Ground truth for analysis only (never read by any defense); read out of band from the host.
        return getattr(self.main, "last_intent", None)

    def close(self) -> None:
        if getattr(self, "_closed", False):
            return
        self._closed = True

        async def _close_clients():
            for hc, _ in self._clients.values():
                await hc.aclose()
        if self._clients:
            self._run(_close_clients())
        for srv in self._servers:
            srv.stop()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=10)


def make_transport(kind: str, main: Supplier, cfg: GameConfig):
    if kind == "inproc":
        return InProcTransport(main, cfg)
    if kind == "a2a":
        return A2ATransport(main, cfg)
    raise ValueError(f"transport must be one of {TRANSPORTS}, not {kind!r}")
