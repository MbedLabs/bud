"""Every HTTP request leaves one api.request audit event, and repeated refusals are flagged."""

import gzip
import json
import logging
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.observability import (
    RequestObservabilityMiddleware,
    created_id,
    created_ids,
)
from app.core.runner_keys import mint_key
from app.core.security import (
    create_access_token,
    generate_runner_token,
    get_password_hash,
)
from app.db import database
from app.models import AuditEvent, Runner
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.services.audit import set_audit_actor

PASSWORD = "Correct-Horse-Battery-9"
STATION_PASSWORD = "a-very-long-runner-password-123"


async def _user(db_session, email, role=UserRole.viewer):
    """Persist an active user that signs in with PASSWORD."""
    user = User(
        email=email,
        full_name=email.split("@")[0],
        hashed_password=get_password_hash(PASSWORD),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _station(db_session, account="station-01"):
    """Persist an active station holding its current runner token."""
    station = Runner(
        account=account,
        password_hash=get_password_hash(STATION_PASSWORD),
        token="pending",
        socket_port=53035,
        is_active=True,
    )
    db_session.add(station)
    await db_session.commit()
    station.token = generate_runner_token(station.account, station.id)
    await db_session.commit()
    return station


async def _key(db_session, station=None):
    """Persist an enrolment key, bound to ``station`` when given, and return its plaintext."""
    record, plaintext = mint_key(label="bench key", created_by_user_id=None)
    if station is not None:
        record.runner_id = station.id
    db_session.add(record)
    await db_session.commit()
    return plaintext


async def _requests(db_session, **filters):
    """The api.request events matching the column filters, oldest first."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.action == "api.request")
        .execution_options(populate_existing=True)
    )
    for name, value in filters.items():
        query = query.where(getattr(AuditEvent, name) == value)
    return list((await db_session.execute(query.order_by(AuditEvent.id))).scalars())


async def _request_for(db_session, response):
    """The single api.request event of one response, found by its request id."""
    [event] = await _requests(db_session, request_id=response.headers["x-request-id"])
    return event


def _login(client, email):
    """Sign in through the browser login and return the bearer header."""
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _upload():
    """One passing result from a station run."""
    return {
        "results": [{"test_class": "Smoke", "test_method": "test_boots", "passed": True}],
        "test_suite_name": "smoke",
    }


async def test_a_browser_session_is_recorded_as_a_web_user(unauthenticated_client, db_session):
    user = await _user(db_session, "web@example.com")
    headers = _login(unauthenticated_client, "web@example.com")

    response = unauthenticated_client.get(
        "/api/auth/me?include=groups", headers={**headers, "user-agent": "browser/1.0"}
    )

    assert response.status_code == 200
    event = await _request_for(db_session, response)
    assert event.actor_type == "user"
    assert event.actor_user_id == user.id
    assert event.outcome == "success"
    assert event.ip == "testclient"
    assert event.user_agent == "browser/1.0"
    assert event.details["client"] == "web"
    assert event.details["method"] == "GET"
    assert event.details["route"] == "/api/auth/me"
    assert event.details["path"] == "/api/auth/me"
    assert event.details["status"] == 200
    assert event.details["auth"] == "bearer"
    assert event.details["query_params"] == ["include"]
    assert isinstance(event.details["duration_ms"], float)


async def test_a_cli_token_is_recorded_as_a_cli_user(unauthenticated_client, db_session):
    user = await _user(db_session, "cli@example.com")
    refresh = UserToken(
        user_id=user.id,
        purpose=UserTokenPurpose.refresh,
        token_hash="c" * 64,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(refresh)
    await db_session.commit()
    token = create_access_token(
        {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": refresh.id}
    )

    response = unauthenticated_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, response.text
    event = await _request_for(db_session, response)
    assert event.actor_type == "user"
    assert event.actor_user_id == user.id
    assert event.details["client"] == "cli"


async def test_a_station_token_names_the_station_and_its_created_run(
    unauthenticated_client, db_session
):
    station = await _station(db_session)
    headers = {"Authorization": f"Bearer {station.token}"}

    heartbeat = unauthenticated_client.post(
        "/api/runners/heartbeat", json={"runner_account": station.account}, headers=headers
    )
    created = unauthenticated_client.post(
        "/api/test-runs",
        json={"test_case_list": "[]", "test_suite_name": "smoke"},
        headers=headers,
    )

    assert heartbeat.status_code == 200, heartbeat.text
    assert created.status_code == 201, created.text
    beat = await _request_for(db_session, heartbeat)
    assert beat.actor_type == "runner"
    assert beat.actor_user_id is None
    assert beat.details["runner_id"] == station.id
    assert beat.details["route"] == "/api/runners/heartbeat"
    assert beat.details["auth"] == "bearer"
    run = await _request_for(db_session, created)
    assert run.actor_type == "runner"
    assert run.details["runner_id"] == station.id
    assert run.details["method"] == "POST"
    assert run.details["status"] == 201
    assert run.details["created_id"] == created.json()["id"]


async def test_an_enrolment_key_names_its_station(unauthenticated_client, db_session):
    station = await _station(db_session, "station-02")
    key = await _key(db_session, station)

    response = unauthenticated_client.post(
        "/api/results", json=_upload(), headers={"X-API-Key": key}
    )

    assert response.status_code == 201, response.text
    event = await _request_for(db_session, response)
    assert event.actor_type == "runner"
    assert event.details["runner_id"] == station.id
    assert event.details["route"] == "/api/results"
    assert event.details["auth"] == "api-key"
    assert event.outcome == "success"
    assert event.details["created_test_run_id"] == response.json()["test_run_id"]
    assert "created_id" not in event.details


async def test_a_created_object_and_its_path_parameters_are_recorded(
    unauthenticated_client, db_session
):
    await _user(db_session, "admin@example.org", UserRole.admin)
    headers = _login(unauthenticated_client, "admin@example.org")

    created = unauthenticated_client.post("/api/products", json={"name": "Widget"}, headers=headers)
    product_id = created.json()["id"]
    read = unauthenticated_client.get(f"/api/products/{product_id}", headers=headers)

    assert created.status_code == 201, created.text
    assert (await _request_for(db_session, created)).details["created_id"] == product_id
    event = await _request_for(db_session, read)
    assert event.product_id == product_id
    assert event.target_type == "product"
    assert event.target_id == str(product_id)
    assert event.details["route"] == "/api/products/{product_id}"
    assert event.details["path"] == f"/api/products/{product_id}"


async def test_health_probes_are_recorded_as_anonymous(unauthenticated_client, db_session):
    response = unauthenticated_client.get("/api/health")

    assert response.status_code == 200
    event = await _request_for(db_session, response)
    assert event.actor_type == "anonymous"
    assert event.details["auth"] == "none"
    assert event.outcome == "success"


async def test_a_forged_token_is_denied_with_the_address(unauthenticated_client, db_session):
    forged = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIiwidHlwZSI6InVzZXIifQ.forged-signature"

    response = unauthenticated_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401
    event = await _request_for(db_session, response)
    assert event.outcome == "denied"
    assert event.actor_type == "anonymous"
    assert event.ip == "testclient"
    assert event.details["auth"] == "bearer"
    assert forged not in json.dumps(event.details)


async def test_insufficient_permissions_are_denied(unauthenticated_client, db_session):
    viewer = await _user(db_session, "viewer@example.com")
    headers = _login(unauthenticated_client, "viewer@example.com")

    response = unauthenticated_client.get("/api/audit", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions."
    event = await _request_for(db_session, response)
    assert event.outcome == "denied"
    assert event.actor_user_id == viewer.id
    assert event.ip == "testclient"


async def test_a_wrong_enrolment_key_is_denied(
    unauthenticated_client, db_session, fresh_auth_rate_limits
):
    response = unauthenticated_client.post(
        "/api/runners/register",
        json={"username": "station-09", "password": STATION_PASSWORD},
        headers={"X-API-Key": "budrnr_not-a-key-anyone-ever-issued"},
    )

    assert response.status_code == 403
    event = await _request_for(db_session, response)
    assert event.outcome == "denied"
    assert event.actor_type == "anonymous"
    assert event.details["auth"] == "api-key"
    assert event.ip == "testclient"


async def test_a_rate_limited_request_is_denied(
    unauthenticated_client, db_session, fresh_auth_rate_limits
):
    body = {"email": "nobody@example.com", "password": "wrong-password-1"}
    responses = [unauthenticated_client.post("/api/auth/login", json=body) for _ in range(11)]

    assert responses[-1].status_code == 429
    event = await _request_for(db_session, responses[-1])
    assert event.outcome == "denied"
    assert event.details["status"] == 429
    assert event.ip == "testclient"


async def test_twenty_refusals_from_one_address_leave_one_flag(unauthenticated_client, db_session):
    headers = {"Authorization": "Bearer not-a-token"}
    for _ in range(19):
        assert unauthenticated_client.get("/api/auth/me", headers=headers).status_code == 401
    flag = (
        select(AuditEvent)
        .where(AuditEvent.action == "security.repeated_refusals")
        .execution_options(populate_existing=True)
    )
    assert list((await db_session.execute(flag)).scalars()) == []

    for _ in range(6):
        assert unauthenticated_client.get("/api/auth/me", headers=headers).status_code == 401

    [event] = list((await db_session.execute(flag)).scalars())
    assert event.ip == "testclient"
    assert event.outcome == "denied"
    assert event.details == {"denied_requests": 20, "threshold": 20, "window_minutes": 10}
    assert len(await _requests(db_session, outcome="denied")) == 25


async def test_refusals_outside_the_window_do_not_count(unauthenticated_client, db_session):
    old = datetime.utcnow() - timedelta(minutes=11)
    db_session.add_all(
        AuditEvent(
            occurred_at=old,
            actor_type="anonymous",
            action="api.request",
            ip="testclient",
            outcome="denied",
        )
        for _ in range(30)
    )
    await db_session.commit()

    response = unauthenticated_client.get("/api/auth/me")

    assert response.status_code == 401
    flags = select(AuditEvent).where(AuditEvent.action == "security.repeated_refusals")
    assert list((await db_session.execute(flags)).scalars()) == []


async def test_no_secret_or_body_value_is_stored(unauthenticated_client, db_session):
    station = await _station(db_session, "station-03")
    key = await _key(db_session, station)
    await _user(db_session, "secret@example.com")
    headers = _login(unauthenticated_client, "secret@example.com")

    unauthenticated_client.post("/api/results", json=_upload(), headers={"X-API-Key": key})
    unauthenticated_client.get("/api/auth/me?token=query-secret-value", headers=headers)

    stored = json.dumps(
        [[e.details, e.user_agent, e.target_id] for e in await _requests(db_session)]
    )
    assert PASSWORD not in stored
    assert key not in stored
    assert headers["Authorization"].split()[1] not in stored
    assert "query-secret-value" not in stored
    assert "test_boots" not in stored
    assert '"token"' in stored


async def test_a_failed_audit_write_does_not_change_the_response(
    unauthenticated_client, monkeypatch, caplog
):
    def broken_session():
        raise RuntimeError("audit database unavailable")

    monkeypatch.setattr(database, "async_session_maker", broken_session)

    with caplog.at_level(logging.ERROR):
        response = unauthenticated_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "api.request could not be recorded" in caplog.text


async def test_an_actor_set_in_an_async_dependency_reaches_the_middleware(_engine, db_session):
    async def acting_user():
        set_audit_actor("user", 4242, client="web")

    probe = FastAPI()
    probe.add_middleware(RequestObservabilityMiddleware)

    @probe.get("/probe/{run_id}", dependencies=[Depends(acting_user)])
    async def read_probe(run_id: int):
        return {"run_id": run_id}

    with TestClient(probe) as client:
        response = client.get("/probe/7")

    assert response.status_code == 200
    event = await _request_for(db_session, response)
    assert event.actor_type == "user"
    assert event.actor_user_id == 4242
    assert event.details["client"] == "web"
    assert event.target_type == "run"
    assert event.target_id == "7"


async def test_audit_filters_select_by_actor_type_address_request_and_status(
    unauthenticated_client, db_session
):
    await _user(db_session, "auditor@example.com", UserRole.admin)
    headers = _login(unauthenticated_client, "auditor@example.com")
    refused = unauthenticated_client.get("/api/auth/me", headers={"Authorization": "Bearer x"})

    by_request = unauthenticated_client.get(
        "/api/audit",
        params={"request_id": refused.headers["x-request-id"]},
        headers=headers,
    ).json()
    by_status = unauthenticated_client.get(
        "/api/audit", params={"status": 401, "action": "api."}, headers=headers
    ).json()
    by_actor = unauthenticated_client.get(
        "/api/audit", params={"actor_type": "user", "action": "api.request"}, headers=headers
    ).json()
    by_ip = unauthenticated_client.get(
        "/api/audit", params={"ip": "203.0.113.9"}, headers=headers
    ).json()

    assert [item["details"]["status"] for item in by_request["items"]] == [401]
    assert by_status["total"] == 1
    assert by_status["items"][0]["request_id"] == refused.headers["x-request-id"]
    assert by_actor["total"] >= 1
    assert {item["actor_type"] for item in by_actor["items"]} == {"user"}
    assert by_ip == {"items": [], "total": 0}


def test_created_id_reads_a_gzip_body_within_the_limit():
    body = json.dumps({"id": 12, "name": "x" * 2000}).encode()

    assert created_id(gzip.compress(body), "gzip") == 12
    assert created_id(body, "") == 12
    assert created_id(b"[1, 2]", "") is None
    assert created_id(b"not json", "") is None
    assert created_id(json.dumps({"id": True}).encode(), "") is None
    assert created_id(gzip.compress(b"{" + b" " * 200_000 + b"}"), "gzip") is None
    assert created_id(body, "br") is None


async def test_a_cors_preflight_is_recorded(unauthenticated_client, db_session):
    response = unauthenticated_client.options(
        "/api/auth/me",
        headers={
            "Origin": settings.CORS_ORIGINS[0],
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["access-control-allow-origin"] == settings.CORS_ORIGINS[0]
    event = await _request_for(db_session, response)
    assert event.details["method"] == "OPTIONS"
    assert event.details["path"] == "/api/auth/me"
    assert event.details["status"] == 200
    assert event.actor_type == "anonymous"
    assert event.outcome == "success"


async def test_the_route_is_the_full_template_of_a_router_prefixed_route(
    unauthenticated_client, db_session
):
    response = unauthenticated_client.get("/api/auth/me")

    assert response.status_code == 401
    event = await _request_for(db_session, response)
    assert event.details["route"] == "/api/auth/me"
    assert event.details["route"] != "/me"


def test_a_results_answer_names_its_run_and_an_id_wins():
    assert created_ids(b'{"test_run_id": 5, "count": 1}', "") == {"created_test_run_id": 5}
    assert created_ids(b'{"id": 3, "test_run_id": 5}', "") == {"created_id": 3}
    assert created_ids(b'{"id": null, "test_run_id": 5}', "") == {}
    assert created_ids(b'{"count": 1}', "") == {}
