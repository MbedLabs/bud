"""The client address comes from X-Forwarded-For only through a proxy in TRUSTED_PROXY_NETWORKS."""

import ipaddress
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.core.observability import forwarded_client
from app.models import AuditEvent

ROOT = Path(__file__).resolve().parents[2]
PROXY = "10.10.0.7"
OUTSIDER = "203.0.113.9"
OTHER_OUTSIDER = "198.51.100.20"
FORGED = "192.0.2.66"
PROXY_NETWORKS = [ipaddress.ip_network("10.10.0.0/16")]


@pytest.fixture
def through_image(unauthenticated_client):
    """Send requests the way the image delivers them: nginx appends the address it received to
    X-Forwarded-For and reaches uvicorn's proxy headers, trusting loopback only, from 127.0.0.1."""
    from app.main import app

    def send(method, path, nginx_peer, forwarded_for=None, **kwargs):
        chain = f"{forwarded_for}, {nginx_peer}" if forwarded_for else nginx_peer
        headers = {**kwargs.pop("headers", {}), "X-Forwarded-For": chain}
        image = TestClient(
            ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1,::1"),
            client=("127.0.0.1", 50000),
        )
        return image.request(method, path, headers=headers, **kwargs)

    return send


@pytest.fixture
def trusted_proxy(monkeypatch):
    """Trust the proxy network for one test."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_NETWORKS", PROXY_NETWORKS)


async def _event(db_session, response):
    """The api.request event of one response."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.action == "api.request")
        .where(AuditEvent.request_id == response.headers["x-request-id"])
        .execution_options(populate_existing=True)
    )
    [event] = list((await db_session.execute(query)).scalars())
    return event


async def _flags(db_session):
    """The security.repeated_refusals events, oldest first."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.action == "security.repeated_refusals")
        .order_by(AuditEvent.id)
        .execution_options(populate_existing=True)
    )
    return list((await db_session.execute(query)).scalars())


def test_the_setting_is_empty_by_default():
    assert settings.model_fields["TRUSTED_PROXY_NETWORKS"].default == []


async def test_a_trusted_proxy_records_the_forwarded_address(
    through_image, trusted_proxy, db_session
):
    response = through_image("GET", "/api/health", PROXY, OUTSIDER)

    assert response.status_code == 200
    assert (await _event(db_session, response)).ip == OUTSIDER


async def test_further_trusted_proxies_are_skipped(through_image, trusted_proxy, db_session):
    response = through_image("GET", "/api/health", PROXY, f"{OUTSIDER}, 10.10.3.4")

    assert (await _event(db_session, response)).ip == OUTSIDER


async def test_an_untrusted_sender_cannot_forge_the_address(
    through_image, trusted_proxy, db_session
):
    response = through_image("GET", "/api/health", OTHER_OUTSIDER, f"{FORGED}, {PROXY}")

    assert (await _event(db_session, response)).ip == OTHER_OUTSIDER


async def test_a_forged_entry_passed_on_by_the_proxy_is_ignored(
    through_image, trusted_proxy, db_session
):
    response = through_image("GET", "/api/health", PROXY, f"{FORGED}, {OUTSIDER}")

    assert (await _event(db_session, response)).ip == OUTSIDER


async def test_the_empty_default_records_the_direct_peer(through_image, db_session):
    response = through_image("GET", "/api/health", PROXY, OUTSIDER)

    assert (await _event(db_session, response)).ip == PROXY


async def test_a_sender_on_the_container_loopback_is_read_as_part_of_the_image(
    through_image, db_session
):
    response = through_image("GET", "/api/health", "127.0.0.1", OUTSIDER)

    assert (await _event(db_session, response)).ip == OUTSIDER


async def test_repeated_refusals_count_the_resolved_address(
    through_image, trusted_proxy, db_session
):
    def refuse(client):
        response = through_image("GET", "/api/auth/me", PROXY, client)
        assert response.status_code == 401
        return response

    for _ in range(19):
        refuse(OUTSIDER)
        refuse(OTHER_OUTSIDER)
    assert await _flags(db_session) == []

    last = refuse(OUTSIDER)

    [flag] = await _flags(db_session)
    assert flag.ip == OUTSIDER
    assert flag.details["denied_requests"] == 20
    assert (await _event(db_session, last)).ip == OUTSIDER


async def test_the_rate_limit_counts_the_resolved_address(
    through_image, trusted_proxy, fresh_auth_rate_limits
):
    body = {"email": "nobody@example.com", "password": "wrong-password-1"}
    answers = [
        through_image("POST", "/api/auth/login", PROXY, OUTSIDER, json=body).status_code
        for _ in range(11)
    ]
    other = through_image("POST", "/api/auth/login", PROXY, OTHER_OUTSIDER, json=body)

    assert answers[-1] == 429
    assert other.status_code == 401


def test_forwarded_client_walks_from_the_right():
    hops = [b"192.0.2.1, 203.0.113.9", b"10.10.0.3"]

    assert forwarded_client(PROXY, hops, PROXY_NETWORKS) == OUTSIDER
    assert forwarded_client(OUTSIDER, hops, PROXY_NETWORKS) == OUTSIDER
    assert forwarded_client(PROXY, hops, []) == PROXY
    assert forwarded_client(PROXY, [], PROXY_NETWORKS) == PROXY
    assert forwarded_client(PROXY, [b"10.10.0.1, 10.10.0.2"], PROXY_NETWORKS) == "10.10.0.1"
    assert forwarded_client(PROXY, [b"not-an-address, 10.10.0.2"], PROXY_NETWORKS) == "10.10.0.2"
    assert forwarded_client(PROXY, [b"203.0.113.9:4711"], PROXY_NETWORKS) == OUTSIDER
    assert forwarded_client(PROXY, [b"[2001:db8::5]:443"], PROXY_NETWORKS) == "2001:db8::5"
    assert forwarded_client("::ffff:10.10.0.7", [b"203.0.113.9"], PROXY_NETWORKS) == OUTSIDER
    assert forwarded_client("testclient", [b"203.0.113.9"], PROXY_NETWORKS) == "testclient"


def test_the_image_nginx_appends_the_address_it_received():
    text = (ROOT / "docker" / "nginx.conf").read_text()

    assert text.count("proxy_pass http://127.0.0.1:8000;") == 2
    assert text.count("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;") == 2
    assert "real_ip" not in text


def test_the_image_uvicorn_trusts_forwarding_from_loopback_only():
    lines = (ROOT / "docker" / "supervisord.conf").read_text().splitlines()
    [command] = [line for line in lines if line.startswith("command=/usr/local/bin/uvicorn")]

    assert command.endswith("--forwarded-allow-ips 127.0.0.1,::1")
