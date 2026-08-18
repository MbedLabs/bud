"""Products and Test Station endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Product, Runner, TestStation


class TestProducts:
    def test_creates_a_product(self, client):
        response = client.post(
            "/api/products", json={"name": "Gateway ECU", "description": "Main gateway"}
        )
        assert response.status_code == 201, response.text
        assert response.json()["name"] == "Gateway ECU"

    def test_rejects_a_duplicate_name(self, client):
        payload = {"name": "Duplicate", "description": None}
        assert client.post("/api/products", json=payload).status_code == 201
        second = client.post("/api/products", json=payload)
        assert second.status_code == 400
        assert "already exists" in second.json()["detail"].lower()

    def test_lists_products_by_name(self, client):
        for name in ("Zebra", "Alpha", "Mango"):
            client.post("/api/products", json={"name": name})
        names = [p["name"] for p in client.get("/api/products").json()]
        assert names == sorted(names)

    def test_fetches_one_product(self, client):
        created = client.post("/api/products", json={"name": "Fetchable"})
        product_id = created.json()["id"]
        response = client.get(f"/api/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Fetchable"

    def test_unknown_product_is_404(self, client):
        assert client.get("/api/products/99999").status_code == 404

    @pytest.mark.asyncio
    async def test_deletes_a_product(self, client, db_session):
        created = client.post("/api/products", json={"name": "Deletable"})
        product_id = created.json()["id"]

        assert client.delete(f"/api/products/{product_id}").status_code == 204
        remaining = (
            await db_session.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
        assert remaining is None

    def test_deleting_an_unknown_product_is_404(self, client):
        assert client.delete("/api/products/99999").status_code == 404

    def test_products_require_authentication(self, unauthenticated_client):
        for method, path in [
            ("GET", "/api/products"),
            ("POST", "/api/products"),
            ("GET", "/api/products/1"),
            ("DELETE", "/api/products/1"),
        ]:
            response = unauthenticated_client.request(method, path, json={"name": "x"})
            assert response.status_code == 401, f"{method} {path} was {response.status_code}"


async def _station(db_session, account: str, **overrides) -> TestStation:
    station = TestStation(
        account=account,
        password_hash=overrides.pop("password_hash", "hashed"),
        token=overrides.pop("token", f"token-{account}"),
        location=overrides.pop("location", "Lab A"),
        is_active=overrides.pop("is_active", True),
        **overrides,
    )
    db_session.add(station)
    await db_session.commit()
    await db_session.refresh(station)
    return station


class TestTestStations:
    @pytest.mark.asyncio
    async def test_status_lists_registered_stations(self, client, db_session):
        await _station(db_session, "bench-01")
        await _station(db_session, "bench-02")

        response = client.get("/api/teststations/status")
        assert response.status_code == 200, response.text
        body = response.json()
        accounts = {s["account"] for s in body["teststations"]}
        assert {"bench-01", "bench-02"} <= accounts

    @pytest.mark.asyncio
    async def test_status_reports_a_stale_station_as_offline(self, client, db_session):
        await _station(
            db_session,
            "stale",
            last_heartbeat=datetime.utcnow() - timedelta(days=1),
        )
        await _station(db_session, "fresh", last_heartbeat=datetime.utcnow())

        listed = client.get("/api/teststations/status").json()["teststations"]
        stations = {s["account"]: s for s in listed}
        assert stations["stale"]["is_online"] is False
        assert stations["fresh"]["is_online"] is True

    @pytest.mark.asyncio
    async def test_fetches_one_station(self, client, db_session):
        await _station(db_session, "single")
        response = client.get("/api/teststations/single")
        assert response.status_code == 200, response.text
        assert response.json()["account"] == "single"

    def test_unknown_station_is_404(self, client):
        assert client.get("/api/teststations/nobody").status_code == 404

    @pytest.mark.asyncio
    async def test_deletes_a_station(self, client, db_session):
        await _station(db_session, "removable")
        assert client.delete("/api/teststations/removable").status_code == 204

        remaining = (
            await db_session.execute(select(TestStation).where(TestStation.account == "removable"))
        ).scalar_one_or_none()
        assert remaining is None

    def test_deleting_an_unknown_station_is_404(self, client):
        assert client.delete("/api/teststations/nobody").status_code == 404

    def test_stations_require_authentication(self, unauthenticated_client):
        for method, path in [
            ("GET", "/api/teststations/status"),
            ("GET", "/api/teststations/bench-01"),
            ("DELETE", "/api/teststations/bench-01"),
        ]:
            response = unauthenticated_client.request(method, path)
            assert response.status_code == 401, f"{method} {path} was {response.status_code}"


async def _runner(db_session, account: str, **overrides) -> Runner:
    runner = Runner(
        account=account,
        password_hash=overrides.pop("password_hash", "hashed"),
        token=overrides.pop("token", f"token-{account}"),
        **overrides,
    )
    db_session.add(runner)
    await db_session.commit()
    await db_session.refresh(runner)
    return runner


class TestRunners:
    @pytest.mark.asyncio
    async def test_status_lists_registered_runners(self, client, db_session):
        await _runner(db_session, "runner-01")
        response = client.get("/api/runners/status")
        assert response.status_code == 200, response.text
        accounts = {r["account"] for r in response.json()["runners"]}
        assert "runner-01" in accounts

    @pytest.mark.asyncio
    async def test_fetches_one_runner(self, client, db_session):
        await _runner(db_session, "runner-solo")
        response = client.get("/api/runners/runner-solo")
        assert response.status_code == 200, response.text
        assert response.json()["account"] == "runner-solo"

    def test_unknown_runner_is_404(self, client):
        assert client.get("/api/runners/ghost").status_code == 404

    @pytest.mark.asyncio
    async def test_deletes_a_runner(self, client, db_session):
        await _runner(db_session, "runner-gone")
        assert client.delete("/api/runners/runner-gone").status_code == 204

        remaining = (
            await db_session.execute(select(Runner).where(Runner.account == "runner-gone"))
        ).scalar_one_or_none()
        assert remaining is None

    def test_deleting_an_unknown_runner_is_404(self, client):
        assert client.delete("/api/runners/ghost").status_code == 404

    def test_runners_require_authentication(self, unauthenticated_client):
        for method, path in [
            ("GET", "/api/runners/status"),
            ("GET", "/api/runners/runner-01"),
            ("DELETE", "/api/runners/runner-01"),
        ]:
            response = unauthenticated_client.request(method, path)
            assert response.status_code == 401, f"{method} {path} was {response.status_code}"
