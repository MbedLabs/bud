"""Operational instrumentation: structured logging, request IDs, Prometheus metrics."""

from __future__ import annotations

import ipaddress
import json
import logging
import sys
import time
import uuid
import zlib
from contextvars import ContextVar
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
client_ip_var: ContextVar[str | None] = ContextVar("client_ip", default=None)
user_agent_var: ContextVar[str | None] = ContextVar("user_agent", default=None)
request_audit_var: ContextVar[dict[str, Any] | None] = ContextVar("request_audit", default=None)

access_logger = logging.getLogger("bud.access")
logger = logging.getLogger(__name__)

CREATED_BODY_LIMIT = 64 * 1024
QUERY_NAME_LIMIT = 50

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests processed, by method, route template and status code.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency, by method and route template.",
    ["method", "path"],
)


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line; safe for log shippers."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        extra = getattr(record, "http", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestIdTextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        return super().format(record)


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure root logging exactly once (idempotent on repeat calls)."""
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            RequestIdTextFormatter(
                "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s"
            )
        )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def credential_kind(headers: dict[str, bytes]) -> str:
    """Name the kind of credential a request presents: bearer, api-key or none."""
    authorization = headers.get("authorization", b"").decode("latin-1").strip()
    if authorization[:7].lower() == "bearer " and authorization[7:].strip():
        return "bearer"
    if headers.get("x-api-key", b"").strip():
        return "api-key"
    return "none"


def route_template(scope) -> str:
    """Return the full path template of the matched route, router prefixes included, or
    ``unmatched``."""
    fastapi_scope = scope.get("fastapi")
    context = (
        fastapi_scope.get("effective_route_context") if isinstance(fastapi_scope, dict) else None
    )
    template = getattr(context, "path", None)
    if template:
        return template
    return getattr(scope.get("route"), "path", None) or "unmatched"


def query_parameter_names(query_string: bytes) -> list[str]:
    """Return the sorted, distinct names of the query parameters, without their values."""
    pairs = parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)
    return sorted({name[:100] for name, _ in pairs})[:QUERY_NAME_LIMIT]


def _identifier(value: Any) -> int | str | None:
    """Return an integer or a string of at most 100 characters, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    return value[:100] if isinstance(value, str) else value


def created_ids(body: bytes, content_encoding: str) -> dict[str, int | str]:
    """Return the ids a JSON object response body names: ``created_id`` for its ``id`` and,
    when it has no ``id``, ``created_test_run_id`` for its ``test_run_id``; gzip is decoded
    within the size limit."""
    payload = _json_object(body, content_encoding)
    if payload is None:
        return {}
    created = _identifier(payload.get("id"))
    if created is not None:
        return {"created_id": created}
    run = _identifier(payload.get("test_run_id")) if "id" not in payload else None
    return {} if run is None else {"created_test_run_id": run}


def _json_object(body: bytes, content_encoding: str) -> dict[str, Any] | None:
    """Decode a JSON object response body, gzip within the size limit, else None."""
    if content_encoding == "gzip":
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            body = decompressor.decompress(body, CREATED_BODY_LIMIT)
        except zlib.error:
            return None
        if decompressor.unconsumed_tail:
            return None
    elif content_encoding not in ("", "identity"):
        return None
    try:
        payload = json.loads(body)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def created_id(body: bytes, content_encoding: str) -> int | str | None:
    """Return the ``id`` of a JSON object response body, decoding gzip within the size limit."""
    return created_ids(body, content_encoding).get("created_id")


class CreatedBodyCapture:
    """Keep the body of a 201 JSON response, up to CREATED_BODY_LIMIT bytes, to read its id."""

    def __init__(self) -> None:
        self.active = False
        self.encoding = ""
        self.body = bytearray()

    def start(self, status: int, headers: list[tuple[bytes, bytes]]) -> None:
        """Begin capturing when the response is a 201 whose body is JSON."""
        values = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in headers}
        self.encoding = values.get("content-encoding", "").strip().lower()
        content_type = values.get("content-type", "")
        self.active = status == 201 and content_type.startswith("application/json")

    def feed(self, chunk: bytes) -> None:
        """Append a body chunk, giving up once the body would exceed the limit."""
        if not self.active:
            return
        if len(self.body) + len(chunk) > CREATED_BODY_LIMIT:
            self.active = False
            self.body.clear()
            return
        self.body.extend(chunk)

    def created(self) -> dict[str, int | str]:
        """Return the ids the captured body names, empty when nothing was captured."""
        return created_ids(bytes(self.body), self.encoding) if self.active else {}


def _address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an address, bare or with a port, an IPv4-mapped IPv6 address as IPv4; None when
    the value is not an address."""
    text = value.strip()
    if text.startswith("["):
        text = text[1:].split("]", 1)[0]
    elif text.count(":") == 1:
        text = text.split(":", 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def _in_networks(address, networks) -> bool:
    """Whether ``address`` lies in one of ``networks``."""
    return any(address in network for network in networks)


def forwarded_client(peer: str | None, forwarded_for: list[bytes], networks) -> str | None:
    """Return the client address of a request.

    When ``peer`` lies in one of ``networks``, it is the right-most X-Forwarded-For address
    outside them; the left-most address when all lie inside them, and the last address read
    when an entry is not an address. Otherwise, and when ``networks`` is empty, it is ``peer``.
    """
    peer_address = _address(peer) if peer and networks else None
    if peer_address is None or not _in_networks(peer_address, networks):
        return peer
    hops = ",".join(value.decode("latin-1") for value in forwarded_for).split(",")
    resolved = peer
    for hop in reversed(hops):
        address = _address(hop)
        if address is None:
            break
        resolved = str(address)
        if not _in_networks(address, networks):
            break
    return resolved


def resolve_client(scope) -> tuple[str, int] | None:
    """Set ``scope["client"]`` to the forwarded client when the peer is in
    TRUSTED_PROXY_NETWORKS, and return the client."""
    from app.core.config import settings

    client = scope.get("client")
    networks = settings.TRUSTED_PROXY_NETWORKS
    if not client or not networks:
        return client
    forwarded_for = [v for k, v in scope.get("headers", []) if k.lower() == b"x-forwarded-for"]
    host = forwarded_client(client[0], forwarded_for, networks)
    if host != client[0]:
        scope["client"] = (host, 0)
    return scope["client"]


class RequestObservabilityMiddleware:
    """Pure ASGI middleware: client address, request id, access log, metrics and one
    api.request audit event.

    The client address is resolved first and written to ``scope["client"]``.

    The audit event is written after the response is finished, with the actor that the
    authentication dependencies recorded in ``request_audit_var``; a failed write is logged.
    When an error escapes the application, ``request_id_var`` keeps the request's id for the
    server error handler that answers outside this middleware.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v for k, v in scope.get("headers", [])}
        incoming = headers.get("x-request-id", b"").decode("latin-1").strip()
        request_id = incoming[:64] if incoming else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        client = resolve_client(scope)
        ip_token = client_ip_var.set(client[0] if client else None)
        agent = headers.get("user-agent", b"").decode("latin-1")
        agent_token = user_agent_var.set(agent or None)
        audit_state: dict[str, Any] = {}
        audit_token = request_audit_var.set(audit_state)

        status_code = 500
        start = time.perf_counter()
        capture = CreatedBodyCapture()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    (k, v) for k, v in message["headers"] if k.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode("latin-1"))]
                capture.start(status_code, message["headers"])
            elif message["type"] == "http.response.body":
                capture.feed(message.get("body", b""))
            await send(message)

        escaped = False
        try:
            await self.app(scope, receive, send_wrapper)
        except BaseException:
            escaped = True
            raise
        finally:
            duration = time.perf_counter() - start
            route = scope.get("route")
            path_template = getattr(route, "path", None) or "unmatched"
            method = scope.get("method", "-")
            HTTP_REQUESTS_TOTAL.labels(method, path_template, str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method, path_template).observe(duration)
            access_logger.info(
                "%s %s %s %.1fms",
                method,
                scope.get("path", "-"),
                status_code,
                duration * 1000,
                extra={
                    "http": {
                        "method": method,
                        "path": scope.get("path", "-"),
                        "route": path_template,
                        "status": status_code,
                        "duration_ms": round(duration * 1000, 1),
                    }
                },
            )
            await self._audit(scope, headers, status_code, duration, capture.created())
            request_audit_var.reset(audit_token)
            if not escaped:
                request_id_var.reset(token)
            client_ip_var.reset(ip_token)
            user_agent_var.reset(agent_token)

    @staticmethod
    async def _audit(
        scope, headers: dict[str, bytes], status: int, duration: float, created: dict[str, Any]
    ) -> None:
        """Record the finished request as an api.request audit event, logging any failure."""
        try:
            from app.services.audit import record_api_request

            await record_api_request(
                method=scope.get("method", "-"),
                route=route_template(scope),
                path=scope.get("path", "-"),
                status=status,
                duration_ms=round(duration * 1000, 1),
                query_params=query_parameter_names(scope.get("query_string", b"")),
                auth=credential_kind(headers),
                path_params=dict(scope.get("path_params") or {}),
                created=created,
            )
        except Exception:
            logger.exception("The api.request audit event could not be recorded")


metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    from app.core.config import settings

    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Not Found")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
