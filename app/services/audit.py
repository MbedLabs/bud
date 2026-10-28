"""Record audit events: who did what, from where, and with what outcome.

The acting user, the request id, the client address and the user agent come from
the request context; a call site names the action and its target. Every HTTP request
also leaves one ``api.request`` event, and an address refused too often within the
window leaves one ``security.repeated_refusals`` event.
"""

from __future__ import annotations

import hashlib
import logging
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import (
    client_ip_var,
    request_audit_var,
    request_id_var,
    user_agent_var,
)
from app.db import database
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)

audit_actor_var: ContextVar[Optional[tuple[str, Optional[int]]]] = ContextVar(
    "audit_actor", default=None
)

SECRET_KEYS = frozenset(
    {"password", "token", "secret", "api_key", "hashed_password", "credential", "webhook_secret"}
)


API_REQUEST_ACTION = "api.request"
REPEATED_REFUSALS_ACTION = "security.repeated_refusals"
DENIED_STATUSES = frozenset({401, 403, 429})


def set_audit_actor(
    actor_type: str,
    actor_user_id: Optional[int] = None,
    *,
    runner_id: Optional[int] = None,
    client: Optional[str] = None,
) -> None:
    """Remember who acts in the current request, for its events and its api.request event.

    ``runner_id`` names the Test Station of a runner actor; ``client`` is ``cli`` or ``web``
    for a user actor.
    """
    audit_actor_var.set((actor_type, actor_user_id))
    request_state = request_audit_var.get()
    if request_state is not None:
        request_state.update(
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            runner_id=runner_id,
            client=client,
        )


def _clean(details: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Drop every key that names a secret, at any depth."""
    if details is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in details.items():
        if any(part in key.lower() for part in SECRET_KEYS):
            continue
        cleaned[key] = _clean(value) if isinstance(value, dict) else value
    return cleaned


def build_audit_event(
    action: str,
    *,
    target_type: Optional[str] = None,
    target_id: Any = None,
    product_id: Optional[int] = None,
    outcome: str = "success",
    details: Optional[dict[str, Any]] = None,
    actor_user_id: Optional[int] = None,
    actor_type: Optional[str] = None,
) -> AuditEvent:
    """Build an audit row from the arguments and the request context."""
    context_actor = audit_actor_var.get()
    if actor_type is None:
        if actor_user_id is not None:
            actor_type = "user"
        elif context_actor is not None:
            actor_type, actor_user_id = context_actor
        else:
            actor_type = "anonymous"
    request_id = request_id_var.get()
    user_agent = user_agent_var.get()
    return AuditEvent(
        actor_user_id=actor_user_id,
        actor_type=actor_type,
        action=action,
        target_type=target_type,
        target_id=None if target_id is None else str(target_id),
        product_id=product_id,
        request_id=None if request_id == "-" else request_id,
        ip=client_ip_var.get(),
        user_agent=user_agent[:255] if user_agent else None,
        outcome=outcome,
        details=_clean(details),
    )


async def record_audit_event(db: AsyncSession, action: str, **fields: Any) -> None:
    """Add an audit row to the request's transaction, committed with the action."""
    db.add(build_audit_event(action, **fields))
    await db.flush()


async def record_audit_failure(db: AsyncSession, action: str, **fields: Any) -> None:
    """Commit a failure audit row on its own session, so the request's rollback keeps it.

    A failure to write the row is logged and never changes the request's answer.
    """
    fields.setdefault("outcome", "failure")
    try:
        async with AsyncSession(bind=db.bind) as session:
            session.add(build_audit_event(action, **fields))
            await session.commit()
    except SQLAlchemyError:
        logger.exception("Audit event %s could not be recorded", action)


def request_outcome(status: int) -> str:
    """Map an HTTP status to an audit outcome: success, denied or failure."""
    if status < 400:
        return "success"
    if status in DENIED_STATUSES:
        return "denied"
    return "failure"


def _request_target(path_params: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Return the type and value of the last path parameter whose name ends in ``_id``."""
    for name in reversed(list(path_params)):
        if name.endswith("_id") and len(name) > 3:
            return name[:-3], str(path_params[name])[:100]
    return None, None


def _request_product_id(path_params: dict[str, Any]) -> Optional[int]:
    """Return the integer ``product_id`` path parameter, or None."""
    try:
        return int(path_params["product_id"])
    except (KeyError, TypeError, ValueError):
        return None


def _address_lock_key(ip: str) -> int:
    """A signed 64-bit advisory lock key for one client address."""
    return int.from_bytes(hashlib.sha256(ip.encode()).digest()[:8], "big", signed=True)


async def _flag_repeated_refusals(session: AsyncSession, ip: str, **actor: Any) -> None:
    """Record security.repeated_refusals once per window when ``ip`` reaches the threshold."""
    window = settings.AUDIT_REFUSAL_WINDOW_MINUTES
    window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=window)
    if session.bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _address_lock_key(ip)}
        )
    denied = await session.scalar(
        select(func.count(AuditEvent.id)).where(
            AuditEvent.action == API_REQUEST_ACTION,
            AuditEvent.outcome == "denied",
            AuditEvent.ip == ip,
            AuditEvent.occurred_at >= window_start,
        )
    )
    if (denied or 0) < settings.AUDIT_REFUSAL_THRESHOLD:
        await session.rollback()
        return
    flagged = await session.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.action == REPEATED_REFUSALS_ACTION,
            AuditEvent.ip == ip,
            AuditEvent.occurred_at >= window_start,
        )
        .limit(1)
    )
    if flagged is not None:
        await session.rollback()
        return
    session.add(
        build_audit_event(
            REPEATED_REFUSALS_ACTION,
            outcome="denied",
            details={
                "denied_requests": denied,
                "threshold": settings.AUDIT_REFUSAL_THRESHOLD,
                "window_minutes": window,
            },
            **actor,
        )
    )
    await session.commit()


async def record_api_request(
    *,
    method: str,
    route: str,
    path: str,
    status: int,
    duration_ms: float,
    query_params: list[str],
    auth: str,
    path_params: dict[str, Any],
    created: int | str | None = None,
) -> None:
    """Commit one api.request event on its own session, then check the address for repeated
    refusals.

    The actor is the one the authentication dependencies recorded for the request, else
    ``anonymous``. Details hold the method, route template, path, status, duration, query
    parameter names, the kind of credential presented and the id a 201 answer created; no
    body or header value. A failure to write is logged and never raised.
    """
    request_state = request_audit_var.get() or {}
    actor_type = request_state.get("actor_type") or "anonymous"
    actor_user_id = request_state.get("actor_user_id")
    details: dict[str, Any] = {
        "method": method,
        "route": route,
        "path": path[:500],
        "status": status,
        "duration_ms": duration_ms,
        "query_params": query_params,
        "auth": auth,
    }
    if request_state.get("client"):
        details["client"] = request_state["client"]
    if request_state.get("runner_id") is not None:
        details["runner_id"] = request_state["runner_id"]
    if created is not None:
        details["created_id"] = created
    target_type, target_id = _request_target(path_params)
    outcome = request_outcome(status)
    actor = {"actor_type": actor_type, "actor_user_id": actor_user_id}
    try:
        async with database.async_session_maker() as session:
            event = build_audit_event(
                API_REQUEST_ACTION,
                target_type=target_type,
                target_id=target_id,
                product_id=_request_product_id(path_params),
                outcome=outcome,
                details=details,
                **actor,
            )
            ip = event.ip
            session.add(event)
            await session.commit()
            if outcome == "denied" and ip:
                await _flag_repeated_refusals(session, ip, **actor)
    except Exception:
        logger.exception("Audit event %s could not be recorded", API_REQUEST_ACTION)
