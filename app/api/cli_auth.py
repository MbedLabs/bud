"""Browser-link authorization for CLI clients using existing user permissions.

A rejected approve, deny, exchange or refresh rolls back the request's changes and records a
failure audit event with its rejection code. The answer is a generic message, except for a
code-mode request while code sign-in is turned off, which answers 403 at start, session lookup,
check and approve. The approver types the request code the client shows; check and approve
compare it with the code of the stored PKCE challenge.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, user_view
from app.core.deps import limiter
from app.db.database import get_db
from app.models.user import User
from app.schemas.cli_auth import (
    CliApproveRequest,
    CliCallbackApproval,
    CliCallbackDenial,
    CliCheckRequest,
    CliCodeApproval,
    CliCodeDenial,
    CliDenyRequest,
    CliExchangeRequest,
    CliRefreshRequest,
    CliSessionResponse,
    CliStartRequest,
    CliStartResponse,
    CliTokenResponse,
)
from app.services.audit import record_audit_event, record_audit_failure
from app.services.cli_auth import (
    CODE_MISMATCH,
    CODE_MODE_OFF,
    INVALID_AUTHORIZATION,
    CodeModeDisabledError,
    approve_session,
    callback_target,
    check_request_code,
    denial_target,
    deny_session,
    exchange_session,
    pending_session,
    refresh_credentials,
    start_session,
)
from app.services.token_service import TokenValidationError

AUTH_CLI_APPROVE = "auth.cli_approve"
AUTH_CLI_DENY = "auth.cli_deny"
AUTH_CLI_EXCHANGE = "auth.cli_exchange"
AUTH_CLI_REFRESH = "auth.cli_refresh"
AUTH_CLI_CODE_MISMATCH = "auth.cli_code_mismatch"
CLI_SESSION_TARGET = "cli_auth_session"
INVALID_SESSION = "Invalid or expired session"
NO_STORE = "no-store"
CODE_MODE_OFF_RESPONSE = {403: {"description": "Code sign-in is turned off"}}

router = APIRouter()


async def _rejection(
    db: AsyncSession,
    action: str,
    error: TokenValidationError,
    *,
    status_code: int,
    detail: str,
    **fields,
) -> HTTPException:
    """Roll back the request, record the failed attempt and return the generic error answer."""
    await db.rollback()
    await record_audit_failure(db, action, details={"reason": error.detail}, **fields)
    return HTTPException(status_code=status_code, detail=detail)


@router.post("/start", responses=CODE_MODE_OFF_RESPONSE)
@limiter.limit("10/minute")
async def cli_start(
    request: Request,
    data: CliStartRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliStartResponse:
    """Create an expiring authorization link for a client without user credentials."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        session = await start_session(db, data)
    except CodeModeDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CODE_MODE_OFF) from exc
    return CliStartResponse(
        session_id=session.id,
        authorize_url=f"/auth/cli?session_id={session.id}",
        expires_at=session.expires_at,
    )


@router.get(
    "/sessions/{session_id}",
    responses={400: {"description": "Bad Request"}, **CODE_MODE_OFF_RESPONSE},
)
async def cli_session(
    session_id: UUID,
    response: Response,
    _current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliSessionResponse:
    """Show pending-client metadata and request time to the signed-in account."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        session = await pending_session(db, session_id)
    except CodeModeDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CODE_MODE_OFF) from exc
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_AUTHORIZATION
        ) from exc
    return CliSessionResponse(
        session_id=session.id,
        client_name=session.client_name,
        mode=session.mode,
        redirect_uri=session.redirect_uri,
        expires_at=session.expires_at,
        consumed=session.consumed_at is not None,
        created_at=session.created_at,
    )


@router.post(
    "/check",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"description": "Bad Request"}, **CODE_MODE_OFF_RESPONSE},
)
@limiter.limit("30/minute")
async def cli_check(
    request: Request,
    data: CliCheckRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    """Answer 204 when the typed request code matches a pending request; nothing is written."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        await check_request_code(db, data.session_id, data.request_code)
    except CodeModeDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CODE_MODE_OFF) from exc
    except TokenValidationError as exc:
        if exc.detail != CODE_MISMATCH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_AUTHORIZATION
            ) from exc
        raise await _rejection(
            db,
            AUTH_CLI_CODE_MISMATCH,
            exc,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_AUTHORIZATION,
            actor_user_id=current_user.id,
            target_type=CLI_SESSION_TARGET,
            target_id=data.session_id,
        ) from exc


@router.post("/approve", responses={400: {"description": "Bad Request"}, **CODE_MODE_OFF_RESPONSE})
@limiter.limit("10/minute")
async def cli_approve(
    request: Request,
    data: CliApproveRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliCallbackApproval | CliCodeApproval:
    """Approve a client once using the account's current permissions and session version.

    The typed request code must match; a mismatch is audited as auth.cli_code_mismatch.
    """
    response.headers["Cache-Control"] = NO_STORE
    try:
        session, code = await approve_session(db, data.session_id, current_user, data.request_code)
    except CodeModeDisabledError as exc:
        raise await _rejection(
            db,
            AUTH_CLI_APPROVE,
            exc,
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CODE_MODE_OFF,
            actor_user_id=current_user.id,
            target_type=CLI_SESSION_TARGET,
            target_id=data.session_id,
        ) from exc
    except TokenValidationError as exc:
        raise await _rejection(
            db,
            AUTH_CLI_CODE_MISMATCH if exc.detail == CODE_MISMATCH else AUTH_CLI_APPROVE,
            exc,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_AUTHORIZATION,
            actor_user_id=current_user.id,
            target_type=CLI_SESSION_TARGET,
            target_id=data.session_id,
        ) from exc
    await record_audit_event(
        db,
        AUTH_CLI_APPROVE,
        actor_user_id=current_user.id,
        target_type=CLI_SESSION_TARGET,
        target_id=session.id,
    )
    if session.mode == "callback":
        return CliCallbackApproval(redirect_to=callback_target(session, code))
    return CliCodeApproval(exchange_code=code, expires_at=session.expires_at)


@router.post("/deny", responses={400: {"description": "Bad Request"}})
async def cli_deny(
    data: CliDenyRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliCallbackDenial | CliCodeDenial:
    """End a pending request without approval, in either mode, and delete it."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        session = await deny_session(db, data.session_id)
    except TokenValidationError as exc:
        raise await _rejection(
            db,
            AUTH_CLI_DENY,
            exc,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_AUTHORIZATION,
            actor_user_id=current_user.id,
            target_type=CLI_SESSION_TARGET,
            target_id=data.session_id,
        ) from exc
    if session.mode == "callback":
        answer: CliCallbackDenial | CliCodeDenial = CliCallbackDenial(
            redirect_to=denial_target(session)
        )
    else:
        answer = CliCodeDenial()
    await record_audit_event(
        db,
        AUTH_CLI_DENY,
        actor_user_id=current_user.id,
        target_type=CLI_SESSION_TARGET,
        target_id=data.session_id,
    )
    return answer


@router.post("/exchange", responses={400: {"description": "Bad Request"}})
@limiter.limit("30/minute")
async def cli_exchange(
    request: Request,
    data: CliExchangeRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliTokenResponse:
    """Exchange an approved code and matching S256 verifier for user-scoped credentials."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        user, access_token, refresh_token = await exchange_session(db, **data.model_dump())
    except TokenValidationError as exc:
        raise await _rejection(
            db,
            AUTH_CLI_EXCHANGE,
            exc,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_AUTHORIZATION,
            target_type=CLI_SESSION_TARGET,
            target_id=data.session_id,
        ) from exc
    await record_audit_event(
        db,
        AUTH_CLI_EXCHANGE,
        actor_user_id=user.id,
        target_type=CLI_SESSION_TARGET,
        target_id=data.session_id,
    )
    return CliTokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=await user_view(db, user)
    )


@router.post("/refresh", responses={401: {"description": "Unauthorized"}})
@limiter.limit("30/minute")
async def cli_refresh(
    request: Request,
    data: CliRefreshRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CliTokenResponse:
    """Rotate JSON refresh credentials without changing browser refresh cookies."""
    response.headers["Cache-Control"] = NO_STORE
    try:
        user, access_token, refresh_token = await refresh_credentials(db, data.refresh_token)
    except TokenValidationError as exc:
        raise await _rejection(
            db,
            AUTH_CLI_REFRESH,
            exc,
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_SESSION,
        ) from exc
    await record_audit_event(
        db, AUTH_CLI_REFRESH, actor_user_id=user.id, target_type="user", target_id=user.id
    )
    return CliTokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=await user_view(db, user)
    )
