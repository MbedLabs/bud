"""
* @file     ${tests/sec/BUD_api_request_audit.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Every request leaves one api.request event naming its actor, outcome and route; refusals are flagged.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh signed-out app whose audit events are read back by request id.
"""

import gzip
import json
import logging
from datetime import datetime, timedelta
from unittest import mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core import observability
from app.core.config import settings
from app.core.runner_keys import mint_key
from app.core.security import create_access_token, generate_runner_token, get_password_hash
from app.db import database
from app.models import AuditEvent, Runner
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.services.audit import set_audit_actor
from tests.sec.api_request_audit import ApiRequestAuditBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class ApiRequestAuditTest(ApiRequestAuditBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for scenario in (
            self.web_user,
            self.cli_user,
            self.station_request,
            self.enrolment_key,
            self.created_object,
            self.health,
            self.forged_token,
            self.insufficient,
            self.deactivated_person,
            self.deactivated_station,
            self.anonymous_not_found,
            self.signed_in_not_found,
            self.wrong_key,
            self.rate_limited,
            self.flag,
            self.old_refusals,
            self.secrets,
            self.failed_write,
            self.probe,
            self.filters,
            self.preflight,
            self.refused_preflight,
            self.foreign_origin,
            self.route_template,
        ):
            self.bud.bud_start_app(signed_in=False)
            scenario()
        self.created_id()
        self.created_ids()

    def person(self, email, role="viewer"):
        """Store an active person with the test password."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(self.parameters.AUDIT_HTTP_PASSWORD),
                role=UserRole(role),
                is_active=True,
            )
        )

    def station(self, account="station-01"):
        """Store an active station holding its current station token."""
        station = self.bud.bud_add_to_app(
            Runner(
                account=account,
                password_hash=get_password_hash(self.parameters.AUDIT_HTTP_STATION_PASSWORD),
                token="pending",
                socket_port=53035,
                is_active=True,
            )
        )
        station.token = generate_runner_token(station.account, station.id)
        return self.bud.bud_add_to_app(station)

    def key(self, station=None):
        """Store an enrolment key, bound to a station when given, and return its plaintext."""
        record, plaintext = mint_key(label="bench key", created_by_user_id=None)
        if station is not None:
            record.runner_id = station.id
        self.bud.bud_add_to_app(record)
        return plaintext

    def requests(self, **filters):
        """The api.request events matching the column values, oldest first."""
        events = self.bud.bud_find_in_app(
            AuditEvent, action=self.parameters.AUDIT_HTTP_ACTION, **filters
        )
        return sorted(events, key=lambda event: event.id)

    def event_of(self, response):
        """The number of api.request events of one response and the first of them."""
        events = self.requests(request_id=response.headers.get("x-request-id"))
        return len(events), (events[0] if events else AuditEvent(details={}))

    def headers(self, email):
        """The bearer header of a signed-in person."""
        response = self.bud.bud_log_in(email, self.parameters.AUDIT_HTTP_PASSWORD)
        return {"Authorization": f"Bearer {body_of(response).get('access_token')}"}

    def get(self, path, **kwargs):
        """Read from the started app."""
        return self.bud.bud_request(self.parameters.GET, path, **kwargs)

    def post(self, path, **kwargs):
        """Post to the started app."""
        return self.bud.bud_request(self.parameters.POST, path, **kwargs)

    def web_user(self):
        p = self.parameters
        user = self.person("web@example.com")
        response = self.get(
            "/api/auth/me?include=groups",
            headers={**self.headers("web@example.com"), "user-agent": "browser/1.0"},
        )
        count, event = self.event_of(response)
        details = event.details or {}
        self.tc_checks["web user"] = {
            "the profile is read": (response.status_code, p.STATUS_OK),
            "one event is recorded": (count, 1),
            "the actor is a person": (event.actor_type, "user"),
            "the person is named": (event.actor_user_id, user.id),
            "the request succeeded": (event.outcome, "success"),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
            "the user agent is recorded": (event.user_agent, "browser/1.0"),
            "the client is the web": (details.get("client"), "web"),
            "the method is recorded": (details.get("method"), "GET"),
            "the route is recorded": (details.get("route"), "/api/auth/me"),
            "the path is recorded": (details.get("path"), "/api/auth/me"),
            "the status is recorded": (details.get("status"), 200),
            "the bearer is recorded": (details.get("auth"), "bearer"),
            "the query names are recorded": (details.get("query_params"), ["include"]),
            "the duration is a number": (type_name(details.get("duration_ms")), "float"),
        }

    def cli_user(self):
        p = self.parameters
        user = self.person("cli@example.com")
        refresh = self.bud.bud_add_to_app(
            UserToken(
                user_id=user.id,
                purpose=UserTokenPurpose.refresh,
                token_hash="c" * 64,
                expires_at=datetime.utcnow() + timedelta(days=1),
            )
        )
        token = create_access_token(
            {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": refresh.id}
        )
        response = self.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        count, event = self.event_of(response)
        self.tc_checks["cli user"] = {
            "the profile is read": (response.status_code, p.STATUS_OK),
            "one event is recorded": (count, 1),
            "the actor is a person": (event.actor_type, "user"),
            "the person is named": (event.actor_user_id, user.id),
            "the client is the CLI": ((event.details or {}).get("client"), "cli"),
        }

    def station_request(self):
        p = self.parameters
        station = self.station()
        headers = {"Authorization": f"Bearer {station.token}"}
        heartbeat = self.post(
            "/api/runners/heartbeat", json={"runner_account": station.account}, headers=headers
        )
        created = self.post(
            p.TEST_RUNS_PATH,
            json={"test_case_list": "[]", "test_suite_name": "smoke"},
            headers=headers,
        )
        beat_count, beat = self.event_of(heartbeat)
        run_count, run = self.event_of(created)
        beat_details, run_details = beat.details or {}, run.details or {}
        self.tc_checks["station"] = {
            "the heartbeat is answered": (heartbeat.status_code, p.STATUS_OK),
            "the run is created": (created.status_code, p.STATUS_CREATED),
            "one heartbeat event is recorded": (beat_count, 1),
            "the heartbeat actor is a station": (beat.actor_type, "runner"),
            "the heartbeat names no person": (type_name(beat.actor_user_id), p.NONE_TYPE),
            "the heartbeat names the station": (beat_details.get("runner_id"), station.id),
            "the heartbeat route is recorded": (
                beat_details.get("route"),
                "/api/runners/heartbeat",
            ),
            "the heartbeat bearer is recorded": (beat_details.get("auth"), "bearer"),
            "one run event is recorded": (run_count, 1),
            "the run actor is a station": (run.actor_type, "runner"),
            "the run event names the station": (run_details.get("runner_id"), station.id),
            "the run method is recorded": (run_details.get("method"), "POST"),
            "the run status is recorded": (run_details.get("status"), 201),
            "the created run is named": (run_details.get("created_id"), body_of(created).get("id")),
        }

    def enrolment_key(self):
        p = self.parameters
        station = self.station("station-02")
        response = self.post(
            "/api/results", json=p.AUDIT_HTTP_UPLOAD, headers={"X-API-Key": self.key(station)}
        )
        count, event = self.event_of(response)
        details = event.details or {}
        self.tc_checks["enrolment key"] = {
            "the results are stored": (response.status_code, p.STATUS_CREATED),
            "one event is recorded": (count, 1),
            "the actor is a station": (event.actor_type, "runner"),
            "the station is named": (details.get("runner_id"), station.id),
            "the route is recorded": (details.get("route"), "/api/results"),
            "the key is recorded": (details.get("auth"), "api-key"),
            "the request succeeded": (event.outcome, "success"),
            "the created run is named": (
                details.get("created_test_run_id"),
                body_of(response).get("test_run_id"),
            ),
            "no created id is named": ("created_id" in details, False),
        }

    def created_object(self):
        p = self.parameters
        self.person("admin@example.org", "admin")
        headers = self.headers("admin@example.org")
        created = self.post("/api/products", json={"name": "Widget"}, headers=headers)
        product_id = body_of(created).get("id")
        read = self.get(f"/api/products/{product_id}", headers=headers)
        _, creation = self.event_of(created)
        count, event = self.event_of(read)
        details = event.details or {}
        self.tc_checks["created object"] = {
            "the product is created": (created.status_code, p.STATUS_CREATED),
            "the created product is named": (
                (creation.details or {}).get("created_id"),
                product_id,
            ),
            "one read event is recorded": (count, 1),
            "the product is recorded": (event.product_id, product_id),
            "the target type is recorded": (event.target_type, "product"),
            "the target is recorded": (event.target_id, str(product_id)),
            "the route template is recorded": (details.get("route"), "/api/products/{product_id}"),
            "the path is recorded": (details.get("path"), f"/api/products/{product_id}"),
        }

    def health(self):
        p = self.parameters
        response = self.get("/api/health")
        count, event = self.event_of(response)
        self.tc_checks["health"] = {
            "the probe is answered": (response.status_code, p.STATUS_OK),
            "one event is recorded": (count, 1),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "no credential is recorded": ((event.details or {}).get("auth"), "none"),
            "the request succeeded": (event.outcome, "success"),
        }

    def forged_token(self):
        p = self.parameters
        response = self.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {p.AUDIT_HTTP_FORGED}"}
        )
        count, event = self.event_of(response)
        self.tc_checks["forged token"] = {
            "the token is refused": (response.status_code, p.STATUS_UNAUTHORIZED),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
            "the bearer is recorded": ((event.details or {}).get("auth"), "bearer"),
            "the token is not stored": (p.AUDIT_HTTP_FORGED in json.dumps(event.details), False),
        }

    def insufficient(self):
        p = self.parameters
        viewer = self.person("viewer@example.com")
        response = self.get("/api/audit", headers=self.headers("viewer@example.com"))
        count, event = self.event_of(response)
        self.tc_checks["insufficient"] = {
            "the audit is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal says why": (body_of(response).get("detail"), p.AUDIT_HTTP_INSUFFICIENT),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the person is named": (event.actor_user_id, viewer.id),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
        }

    def deactivated_person(self):
        p = self.parameters
        user = self.person("gone@example.com")
        headers = self.headers("gone@example.com")
        stored = self.bud.bud_find_in_app(User, id=user.id)[0]
        stored.is_active = False
        self.bud.bud_add_to_app(stored)
        response = self.get("/api/auth/me", headers=headers)
        count, event = self.event_of(response)
        self.tc_checks["deactivated person"] = {
            "the profile is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal says why": (body_of(response).get("detail"), p.AUDIT_HTTP_DEACTIVATED),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the actor is a person": (event.actor_type, "user"),
            "the person is named": (event.actor_user_id, user.id),
            "the client is the web": ((event.details or {}).get("client"), "web"),
        }

    def deactivated_station(self):
        p = self.parameters
        station = self.station("station-03")
        station.is_active = False
        station = self.bud.bud_add_to_app(station)
        response = self.get("/api/auth/me", headers={"Authorization": f"Bearer {station.token}"})
        count, event = self.event_of(response)
        self.tc_checks["deactivated station"] = {
            "the request is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal says why": (body_of(response).get("detail"), p.AUDIT_HTTP_DEACTIVATED),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the actor is a station": (event.actor_type, "runner"),
            "no person is named": (type_name(event.actor_user_id), p.NONE_TYPE),
            "the station is named": ((event.details or {}).get("runner_id"), station.id),
        }

    def anonymous_not_found(self):
        p = self.parameters
        response = self.get(p.AUDIT_HTTP_NOT_FOUND)
        count, event = self.event_of(response)
        self.tc_checks["anonymous not found"] = {
            "the path is not found": (response.status_code, p.STATUS_NOT_FOUND),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "the status is recorded": ((event.details or {}).get("status"), 404),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
        }

    def signed_in_not_found(self):
        p = self.parameters
        self.person("finder@example.com", "admin")
        station = self.station("station-04")
        by_user = self.get(f"{p.TEST_RUNS_PATH}/987654", headers=self.headers("finder@example.com"))
        by_station = self.get(
            f"{p.TEST_RUNS_PATH}/987654", headers={"Authorization": f"Bearer {station.token}"}
        )
        _, user_event = self.event_of(by_user)
        _, station_event = self.event_of(by_station)
        self.tc_checks["signed-in not found"] = {
            "the person's read is not found": (by_user.status_code, p.STATUS_NOT_FOUND),
            "the station's read is not found": (by_station.status_code, p.STATUS_NOT_FOUND),
            "the person's read is a failure": (
                (user_event.actor_type, user_event.outcome),
                ("user", "failure"),
            ),
            "the station's read is a failure": (
                (station_event.actor_type, station_event.outcome),
                ("runner", "failure"),
            ),
            "the station is named": ((station_event.details or {}).get("runner_id"), station.id),
        }

    def wrong_key(self):
        p = self.parameters
        response = self.post(
            "/api/runners/register",
            json={"username": "station-09", "password": p.AUDIT_HTTP_STATION_PASSWORD},
            headers={"X-API-Key": "budrnr_not-a-key-anyone-ever-issued"},
        )
        count, event = self.event_of(response)
        self.tc_checks["wrong key"] = {
            "the key is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "the key is recorded": ((event.details or {}).get("auth"), "api-key"),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
        }

    def rate_limited(self):
        p = self.parameters
        body = {"email": "nobody@example.com", "password": "wrong-password-1"}
        responses = [self.post(p.LOGIN_PATH, json=body) for _ in range(11)]
        count, event = self.event_of(responses[-1])
        self.tc_checks["rate limited"] = {
            "the eleventh login is limited": (responses[-1].status_code, p.STATUS_TOO_MANY),
            "one event is recorded": (count, 1),
            "the request is denied": (event.outcome, "denied"),
            "the status is recorded": ((event.details or {}).get("status"), 429),
            "the address is recorded": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
        }

    def flag(self):
        p = self.parameters
        headers = {"Authorization": "Bearer not-a-token"}
        first = [self.get("/api/auth/me", headers=headers).status_code for _ in range(19)]
        before = self.bud.bud_find_in_app(AuditEvent, action=p.AUDIT_HTTP_FLAG)
        second = [self.get("/api/auth/me", headers=headers).status_code for _ in range(6)]
        flags = self.bud.bud_find_in_app(AuditEvent, action=p.AUDIT_HTTP_FLAG)
        event = flags[0] if flags else AuditEvent(details={})
        self.tc_checks["flag"] = {
            "every refusal is a 401": (set(first + second), {p.STATUS_UNAUTHORIZED}),
            "nineteen refusals leave no flag": (len(before), 0),
            "twenty-five refusals leave one flag": (len(flags), 1),
            "the flag names the address": (event.ip, p.AUDIT_HTTP_CLIENT_IP),
            "the flag is a denial": (event.outcome, "denied"),
            "the flag counts against the threshold": (event.details, p.AUDIT_HTTP_FLAG_DETAILS),
            "every refusal is recorded": (len(self.requests(outcome="denied")), 25),
        }

    def old_refusals(self):
        p = self.parameters
        old = datetime.utcnow() - timedelta(minutes=11)
        for _ in range(30):
            self.bud.bud_add_to_app(
                AuditEvent(
                    occurred_at=old,
                    actor_type="anonymous",
                    action=p.AUDIT_HTTP_ACTION,
                    ip=p.AUDIT_HTTP_CLIENT_IP,
                    outcome="denied",
                )
            )
        response = self.get("/api/auth/me")
        self.tc_checks["old refusals"] = {
            "the request is refused": (response.status_code, p.STATUS_UNAUTHORIZED),
            "old refusals leave no flag": (
                len(self.bud.bud_find_in_app(AuditEvent, action=p.AUDIT_HTTP_FLAG)),
                0,
            ),
        }

    def secrets(self):
        p = self.parameters
        key = self.key(self.station("station-03"))
        self.person("secret@example.com")
        headers = self.headers("secret@example.com")
        self.post("/api/results", json=p.AUDIT_HTTP_UPLOAD, headers={"X-API-Key": key})
        self.get("/api/auth/me?token=query-secret-value", headers=headers)
        stored = json.dumps(
            [[event.details, event.user_agent, event.target_id] for event in self.requests()]
        )
        self.tc_checks["secrets"] = {
            "the password is not stored": (p.AUDIT_HTTP_PASSWORD in stored, False),
            "the key is not stored": (key in stored, False),
            "the bearer token is not stored": (
                headers["Authorization"].split()[1] in stored,
                False,
            ),
            "the query value is not stored": ("query-secret-value" in stored, False),
            "the body is not stored": ("test_boots" in stored, False),
            "the query name is stored": ('"token"' in stored, True),
        }

    def failed_write(self):
        p = self.parameters

        def broken_session():
            raise RuntimeError("audit database unavailable")

        self.bud.bud_start_log_capture(logging.ERROR)
        with mock.patch.object(database, "async_session_maker", broken_session):
            response = self.get("/api/health")
        records = self.bud.bud_stop_log_capture()
        text = "\n".join(logging.Formatter().format(record) for record in records)
        self.tc_checks["failed write"] = {
            "the probe is answered": (response.status_code, p.STATUS_OK),
            "the probe is healthy": (body_of(response).get("status"), "healthy"),
            "the lost event is logged": (p.AUDIT_HTTP_WRITE_FAILED in text, True),
        }

    def probe(self):
        async def acting_user():
            set_audit_actor("user", 4242, client="web")

        app = FastAPI()
        app.add_middleware(observability.RequestObservabilityMiddleware)

        @app.get("/probe/{run_id}", dependencies=[Depends(acting_user)])
        async def read_probe(run_id: int):
            return {"run_id": run_id}

        with TestClient(app) as client:
            response = client.get("/probe/7")
        count, event = self.event_of(response)
        self.tc_checks["probe"] = {
            "the probe is answered": (response.status_code, self.parameters.STATUS_OK),
            "one event is recorded": (count, 1),
            "the actor is a person": (event.actor_type, "user"),
            "the person is named": (event.actor_user_id, 4242),
            "the client is the web": ((event.details or {}).get("client"), "web"),
            "the target type is the run": (event.target_type, "run"),
            "the target is the run": (event.target_id, "7"),
        }

    def filters(self):
        p = self.parameters
        self.person("auditor@example.com", "admin")
        headers = self.headers("auditor@example.com")
        refused = self.get("/api/auth/me", headers={"Authorization": "Bearer x"})
        audit = lambda **params: body_of(self.get("/api/audit", params=params, headers=headers))
        by_request = audit(request_id=refused.headers.get("x-request-id"))
        by_status = audit(status=401, action="api.")
        by_actor = audit(actor_type="user", action="api.request")
        by_ip = audit(ip="203.0.113.9")
        self.tc_checks["filters"] = {
            "the request filter finds the refusal": (
                [(item.get("details") or {}).get("status") for item in by_request.get("items", [])],
                [401],
            ),
            "the status filter finds one event": (by_status.get("total"), 1),
            "the status filter finds the refusal": (
                (by_status.get("items") or [{}])[0].get("request_id"),
                refused.headers.get("x-request-id"),
            ),
            "the actor filter finds events": ((by_actor.get("total") or 0) >= 1, True),
            "the actor filter keeps people only": (
                {item.get("actor_type") for item in by_actor.get("items", [])},
                {"user"},
            ),
            "the address filter finds nothing elsewhere": (by_ip, {"items": [], "total": 0}),
        }

    def created_id(self):
        body = json.dumps({"id": 12, "name": "x" * 2000}).encode()
        read = observability.created_id
        self.tc_checks["created id"] = {
            "a gzip body names its id": (read(gzip.compress(body), "gzip"), 12),
            "a plain body names its id": (read(body, ""), 12),
            "a list names no id": (type_name(read(b"[1, 2]", "")), self.parameters.NONE_TYPE),
            "a broken body names no id": (
                type_name(read(b"not json", "")),
                self.parameters.NONE_TYPE,
            ),
            "a true id names no id": (
                type_name(read(json.dumps({"id": True}).encode(), "")),
                self.parameters.NONE_TYPE,
            ),
            "an oversized body names no id": (
                type_name(read(gzip.compress(b"{" + b" " * 200_000 + b"}"), "gzip")),
                self.parameters.NONE_TYPE,
            ),
            "an unknown encoding names no id": (
                type_name(read(body, "br")),
                self.parameters.NONE_TYPE,
            ),
        }

    def preflight(self):
        p = self.parameters
        origin = settings.CORS_ORIGINS[0]
        response = self.bud.bud_request(
            "OPTIONS",
            "/api/auth/me",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        self.tc_checks["preflight"] = {
            "the preflight is answered": (response.status_code, p.STATUS_OK),
            "the origin is allowed": (response.headers.get("access-control-allow-origin"), origin),
            "no request id is sent": ("x-request-id" in response.headers, False),
            "no event is recorded": (
                [e for e in self.requests() if (e.details or {}).get("method") == "OPTIONS"],
                [],
            ),
        }

    def refused_preflight(self):
        p = self.parameters
        response = self.bud.bud_request(
            "OPTIONS",
            "/api/auth/me",
            headers={
                "Origin": p.AUDIT_HTTP_FOREIGN_ORIGIN,
                "Access-Control-Request-Method": "DELETE",
            },
        )
        count, event = self.event_of(response)
        details = event.details or {}
        self.tc_checks["refused preflight"] = {
            "the preflight is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "no origin is allowed": ("access-control-allow-origin" in response.headers, False),
            "one event is recorded": (count, 1),
            "the method is recorded": (details.get("method"), "OPTIONS"),
            "the path is recorded": (details.get("path"), "/api/auth/me"),
            "the status is recorded": (details.get("status"), 403),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "the request is denied": (event.outcome, "denied"),
        }

    def foreign_origin(self):
        p = self.parameters
        response = self.get("/api/auth/me", headers={"Origin": p.AUDIT_HTTP_FOREIGN_ORIGIN})
        count, event = self.event_of(response)
        self.tc_checks["foreign origin"] = {
            "the request is refused": (response.status_code, p.STATUS_UNAUTHORIZED),
            "no origin is allowed": ("access-control-allow-origin" in response.headers, False),
            "one event is recorded": (count, 1),
            "the path is recorded": ((event.details or {}).get("path"), "/api/auth/me"),
            "the actor is anonymous": (event.actor_type, "anonymous"),
            "the request is denied": (event.outcome, "denied"),
        }

    def route_template(self):
        p = self.parameters
        response = self.get("/api/auth/me")
        count, event = self.event_of(response)
        route = (event.details or {}).get("route")
        self.tc_checks["route template"] = {
            "the request is refused": (response.status_code, p.STATUS_UNAUTHORIZED),
            "one event is recorded": (count, 1),
            "the route is the full template": (route, "/api/auth/me"),
            "the route is not the router's own path": (route != "/me", True),
        }

    def created_ids(self):
        read = observability.created_ids
        self.tc_checks["created ids"] = {
            "a results answer names its run": (
                read(b'{"test_run_id": 5, "count": 1}', ""),
                {"created_test_run_id": 5},
            ),
            "an id wins over the run": (
                read(b'{"id": 3, "test_run_id": 5}', ""),
                {"created_id": 3},
            ),
            "a null id names nothing": (read(b'{"id": null, "test_run_id": 5}', ""), {}),
            "an answer without ids names nothing": (read(b'{"count": 1}', ""), {}),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ApiRequestAuditTest().run()
