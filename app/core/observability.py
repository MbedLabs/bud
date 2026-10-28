"""Operational instrumentation: structured logging, request IDs, Prometheus metrics."""

from __future__ import annotations

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


def created_id(body: bytes, content_encoding: str) -> int | str | None:
    """Return the ``id`` of a JSON object response body, decoding gzip within the size limit."""
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
    if not isinstance(payload, dict):
        return None
    value = payload.get("id")
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    return value[:100] if isinstance(value, str) else value


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

    def created_id(self) -> int | str | None:
        """Return the id of the captured body, or None."""
        return created_id(bytes(self.body), self.encoding) if self.active else None


class RequestObservabilityMiddleware:
    """Pure ASGI middleware: request id, access log, metrics and one api.request audit event.

    The audit event is written after the response is finished, with the actor that the
    authentication dependencies recorded in ``request_audit_var``; a failed write is logged.
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
        client = scope.get("client")
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

        try:
            await self.app(scope, receive, send_wrapper)
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
            await self._audit(scope, headers, status_code, duration, capture.created_id())
            request_audit_var.reset(audit_token)
            request_id_var.reset(token)
            client_ip_var.reset(ip_token)
            user_agent_var.reset(agent_token)

    @staticmethod
    async def _audit(
        scope, headers: dict[str, bytes], status: int, duration: float, created: int | str | None
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
