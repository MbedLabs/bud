"""Record audit events: who did what, from where, and with what outcome.

The acting user, the request id, the client address and the user agent come from
the request context, so a call site names only the action and its target.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import client_ip_var, request_id_var, user_agent_var
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)

audit_actor_var: ContextVar[Optional[tuple[str, Optional[int]]]] = ContextVar(
    "audit_actor", default=None
)

SECRET_KEYS = frozenset(
    {"password", "token", "secret", "api_key", "hashed_password", "credential", "webhook_secret"}
)


def set_audit_actor(actor_type: str, actor_user_id: Optional[int] = None) -> None:
    """Remember who acts in the current request."""
    audit_actor_var.set((actor_type, actor_user_id))


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
