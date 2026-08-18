"""
Operational instrumentation: structured logging, request IDs, Prometheus metrics.

- ``setup_logging`` configures root logging once, as text (dev) or JSON lines
  (production) with the active request id stamped on every record.
- ``RequestObservabilityMiddleware`` is a pure ASGI middleware that assigns or
  propagates ``X-Request-ID``, emits one access-log line per request, and
  records Prometheus counters/histograms keyed by route template (bounded
  label cardinality — raw paths are never used as labels).
- ``metrics_router`` exposes ``GET /metrics`` in the Prometheus text format.
  The endpoint is unauthenticated by convention; disable it with
  ``ENABLE_METRICS=false`` or restrict it at the network layer.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

access_logger = logging.getLogger("bud.access")

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


class RequestObservabilityMiddleware:
    """Pure ASGI middleware: request id + access log + metrics."""

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

        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [
                    (k, v) for k, v in message["headers"] if k.lower() != b"x-request-id"
                ] + [(b"x-request-id", request_id.encode("latin-1"))]
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
            request_id_var.reset(token)


metrics_router = APIRouter()


@metrics_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    from app.core.config import settings

    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Not Found")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
