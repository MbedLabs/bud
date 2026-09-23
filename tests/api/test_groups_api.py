"""Groups over HTTP: the admin API, the role an admin group gives, and product scoping.

A viewer in no group reads every product exactly as before; a viewer in groups reads
only the products those groups grant; a member of an admin group is an administrator.
"""

from datetime import datetime

import pytest

from app.api.auth import get_current_active_entity, get_current_user
from app.main import app
from app.models import Artifact, Product, Runner
from app.models import TestRun as RunModel
from app.models.user import User, UserRole


async def _seed(db_session):
    first = Product(name="Gateway")
    second = Product(name="Sensor")
    viewer = User(
        email="viewer@example.com",
        full_name="Val Viewer",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
        session_version=1,
    )
    station = Runner(account="bench-1", password_hash="x", token="t", socket_port=53100)
    db_session.add_all([first, second, viewer, station])
    await db_session.flush()
    runs = [
        RunModel(
            name="gateway-suite",
            test_case_list="a",
            status="Running",
            product_id=first.id,
            runner_id=station.id,
            started_at=datetime.utcnow(),
        ),
        RunModel(name="sensor-suite", test_case_list="b", status="Completed", product_id=second.id),
        RunModel(name="loose-suite", test_case_list="c", status="Completed"),
    ]
    db_session.add_all(runs)
    await db_session.flush()
    artifact = Artifact(
        filename="log.txt",
        original_filename="log.txt",
        content_type="text/plain",
        size_bytes=3,
        storage_path="log.txt",
        test_run_id=runs[1].id,
    )
    db_session.add(artifact)
    await db_session.commit()
    return first, second, viewer, runs, artifact


def _as(user):
    async def current():
        return user

    app.dependency_overrides[get_current_user] = current
    app.dependency_overrides[get_current_active_entity] = current


def _run_names(client):
    response = client.get("/api/test-runs")
    assert response.status_code == 200, response.text
    return sorted(r["name"] for r in response.json()["runs"])


@pytest.mark.asyncio
async def test_group_admin_api(client, db_session):
    first, _, viewer, _, _ = await _seed(db_session)

    created = client.post("/api/groups", json={"name": "Lab", "role": "viewer"})
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]
    assert client.post("/api/groups", json={"name": "Lab"}).status_code == 400

    member = client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id})
    assert member.status_code == 201
    assert member.json()["members"] == [
        {"user_id": viewer.id, "email": "viewer@example.com", "full_name": "Val Viewer"}
    ]
    assert (
        client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id}).status_code
        == 400
    )
    assert client.post(f"/api/groups/{group_id}/members", json={"user_id": 999}).status_code == 404

    granted = client.post(f"/api/groups/{group_id}/grants", json={"product_id": first.id})
    assert granted.status_code == 201
    assert granted.json()["grants"][0]["product_name"] == "Gateway"
    assert (
        client.post(f"/api/groups/{group_id}/grants", json={"product_id": first.id}).status_code
        == 400
    )
    assert (
        client.post(f"/api/groups/{group_id}/grants", json={"product_id": 999}).status_code == 404
    )
    everything = client.post(f"/api/groups/{group_id}/grants", json={})
    assert {g["product_id"] for g in everything.json()["grants"]} == {first.id, None}
    assert client.post(f"/api/groups/{group_id}/grants", json={}).status_code == 400

    grant_id = everything.json()["grants"][0]["id"]
    assert len(client.delete(f"/api/groups/{group_id}/grants/{grant_id}").json()["grants"]) == 1
    assert client.delete(f"/api/groups/{group_id}/grants/9999").status_code == 404

    renamed = client.patch(
        f"/api/groups/{group_id}", json={"name": "Lab A", "role": "admin", "description": "Bench"}
    )
    assert (renamed.json()["name"], renamed.json()["role"], renamed.json()["description"]) == (
        "Lab A",
        "admin",
        "Bench",
    )
    client.post("/api/groups", json={"name": "Other"})
    assert client.patch(f"/api/groups/{group_id}", json={"name": "Other"}).status_code == 400
    assert [g["name"] for g in client.get("/api/groups").json()] == ["Lab A", "Other"]

    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").json()["members"] == []
    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").status_code == 404
    assert client.delete(f"/api/groups/{group_id}").status_code == 204
    assert client.delete(f"/api/groups/{group_id}").status_code == 404


@pytest.mark.asyncio
async def test_viewer_scope_follows_the_groups(client, db_session):
    first, second, viewer, runs, artifact = await _seed(db_session)
    group_id = client.post("/api/groups", json={"name": "Gateway team"}).json()["id"]

    _as(viewer)
    assert _run_names(client) == ["gateway-suite", "loose-suite", "sensor-suite"]
    assert client.get("/api/groups").status_code == 403

    _as(
        User(
            id=1,
            email="tester@example.com",
            full_name="Tester",
            hashed_password="x",
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )
    )
    client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id})
    client.post(f"/api/groups/{group_id}/grants", json={"product_id": first.id})

    _as(viewer)
    assert _run_names(client) == ["gateway-suite"]
    assert client.get(f"/api/test-runs/{runs[0].id}").status_code == 200
    assert client.get(f"/api/test-runs/{runs[1].id}").status_code == 404
    assert client.get(f"/api/test-runs/{runs[2].id}").status_code == 404
    assert [p["name"] for p in client.get("/api/products").json()] == ["Gateway"]
    assert client.get(f"/api/products/{second.id}").status_code == 404
    assert client.get(f"/api/products/{first.id}").status_code == 200
    assert client.get("/api/test-runs/stats").json()["total_runs"] == 1
    assert client.get("/api/test-runs/filter-options").json()["suites"] == ["gateway-suite"]
    assert client.get(f"/api/uploads/info/{artifact.id}").status_code == 404
    stations = client.get("/api/runners/status").json()["runners"]
    assert stations[0]["current_run"]["name"] == "gateway-suite"
    assert client.get("/api/auth/me").json()["role"] == "viewer"
    assert client.patch(f"/api/test-runs/{runs[0].id}", json={"name": "x"}).status_code == 403


@pytest.mark.asyncio
async def test_all_products_grant_and_admin_group(client, db_session):
    _, _, viewer, runs, artifact = await _seed(db_session)
    viewers = client.post("/api/groups", json={"name": "Everything"}).json()["id"]
    client.post(f"/api/groups/{viewers}/members", json={"user_id": viewer.id})
    client.post(f"/api/groups/{viewers}/grants", json={})
    empty = client.post("/api/groups", json={"name": "Nothing"}).json()["id"]
    client.post(f"/api/groups/{empty}/members", json={"user_id": viewer.id})

    _as(viewer)
    assert _run_names(client) == ["gateway-suite", "loose-suite", "sensor-suite"]
    assert client.get(f"/api/uploads/info/{artifact.id}").status_code == 200

    _as(
        User(
            id=1,
            email="tester@example.com",
            full_name="Tester",
            hashed_password="x",
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )
    )
    client.delete(f"/api/groups/{viewers}")
    _as(viewer)
    assert _run_names(client) == []
    assert client.get("/api/test-runs/stats").json()["total_runs"] == 0

    _as(
        User(
            id=1,
            email="tester@example.com",
            full_name="Tester",
            hashed_password="x",
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )
    )
    client.patch(f"/api/groups/{empty}", json={"role": "admin"})
    _as(viewer)
    assert client.get("/api/auth/me").json()["role"] == "admin"
    assert _run_names(client) == ["gateway-suite", "loose-suite", "sensor-suite"]
    assert client.get("/api/groups").status_code == 200
    renamed = client.patch(f"/api/test-runs/{runs[1].id}", json={"name": "sensor-suite-2"})
    assert renamed.status_code == 200, renamed.text
