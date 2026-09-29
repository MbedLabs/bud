"""Groups over HTTP: the admin API, the role a group gives, and that groups hide nothing.

A group carries the Developer or Viewer role and never Administrator; a member holds the
higher of their own role and their groups' roles; every user reads every product.
"""

from datetime import datetime

import pytest

from app.api.auth import get_current_active_entity, get_current_user
from app.main import app
from app.models import Artifact, Product, Runner
from app.models import TestRun as RunModel
from app.models.user import User, UserRole

ADMIN = User(
    id=1,
    email="tester@example.com",
    full_name="Tester",
    hashed_password="x",
    role=UserRole.admin,
    is_active=True,
    session_version=1,
)


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
    _, _, viewer, _, _ = await _seed(db_session)

    created = client.post("/api/groups", json={"name": "Lab", "role": "viewer"})
    assert created.status_code == 201, created.text
    assert "grants" not in created.json()
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

    renamed = client.patch(
        f"/api/groups/{group_id}",
        json={"name": "Lab A", "role": "developer", "description": "Bench"},
    )
    assert (renamed.json()["name"], renamed.json()["role"], renamed.json()["description"]) == (
        "Lab A",
        "developer",
        "Bench",
    )
    client.post("/api/groups", json={"name": "Other"})
    assert client.patch(f"/api/groups/{group_id}", json={"name": "Other"}).status_code == 400
    assert [g["name"] for g in client.get("/api/groups").json()] == ["Lab A", "Other"]

    assert client.post(f"/api/groups/{group_id}/grants", json={}).status_code in {404, 405}

    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").json()["members"] == []
    assert client.delete(f"/api/groups/{group_id}/members/{viewer.id}").status_code == 404
    assert client.delete(f"/api/groups/{group_id}").status_code == 204
    assert client.delete(f"/api/groups/{group_id}").status_code == 404


@pytest.mark.asyncio
async def test_a_group_never_carries_administrator(client, db_session):
    await _seed(db_session)
    assert client.post("/api/groups", json={"name": "Leads", "role": "admin"}).status_code == 422
    group_id = client.post("/api/groups", json={"name": "Leads"}).json()["id"]
    assert client.patch(f"/api/groups/{group_id}", json={"role": "admin"}).status_code == 422
    assert client.get("/api/groups").json()[0]["role"] == "viewer"


@pytest.mark.asyncio
async def test_groups_hide_nothing(client, db_session):
    first, second, viewer, runs, artifact = await _seed(db_session)
    group_id = client.post("/api/groups", json={"name": "Gateway team"}).json()["id"]
    client.post(f"/api/groups/{group_id}/members", json={"user_id": viewer.id})

    _as(viewer)
    assert _run_names(client) == ["gateway-suite", "loose-suite", "sensor-suite"]
    for run in runs:
        assert client.get(f"/api/test-runs/{run.id}").status_code == 200
    assert [p["name"] for p in client.get("/api/products").json()] == ["Gateway", "Sensor"]
    assert client.get(f"/api/products/{second.id}").status_code == 200
    assert client.get("/api/test-runs/stats").json()["total_runs"] == 3
    assert client.get("/api/test-runs/filter-options").json()["suites"] == [
        "gateway-suite",
        "loose-suite",
        "sensor-suite",
    ]
    assert client.get(f"/api/uploads/info/{artifact.id}").status_code == 200
    stations = client.get("/api/runners/status").json()["runners"]
    assert stations[0]["current_run"]["name"] == "gateway-suite"
    assert client.get("/api/groups").status_code == 403


@pytest.mark.asyncio
async def test_the_higher_role_of_user_and_groups_decides(client, db_session):
    _, _, viewer, runs, _ = await _seed(db_session)
    viewers = client.post("/api/groups", json={"name": "Readers"}).json()["id"]
    developers = client.post("/api/groups", json={"name": "Testers", "role": "developer"}).json()[
        "id"
    ]
    client.post(f"/api/groups/{viewers}/members", json={"user_id": viewer.id})

    _as(viewer)
    assert client.get("/api/auth/me").json()["role"] == "viewer"
    assert client.patch(f"/api/test-runs/{runs[1].id}", json={"name": "x"}).status_code == 403

    _as(ADMIN)
    client.post(f"/api/groups/{developers}/members", json={"user_id": viewer.id})
    _as(viewer)
    assert client.get("/api/auth/me").json()["role"] == "developer"
    renamed = client.patch(f"/api/test-runs/{runs[1].id}", json={"name": "sensor-suite-2"})
    assert renamed.status_code == 200, renamed.text
    assert client.delete(f"/api/test-runs/{runs[1].id}").status_code == 403
    assert client.get("/api/groups").status_code == 403

    _as(ADMIN)
    client.delete(f"/api/groups/{developers}")
    _as(viewer)
    assert client.get("/api/auth/me").json()["role"] == "viewer"
    assert client.patch(f"/api/test-runs/{runs[1].id}", json={"name": "y"}).status_code == 403
