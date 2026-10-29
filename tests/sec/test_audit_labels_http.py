"""The audit log names the objects its events refer to and marks the deleted ones."""

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models import (
    AccessGroup,
    Artifact,
    AuditEvent,
    NotificationChannel,
    Policy,
    Product,
    Runner,
    RunnerApiKey,
    TestResult,
)
from app.models import TestRun as RunModel
from app.models.user import User, UserRole

PASSWORD = "Correct-Horse-Battery-9"

pytestmark = pytest.mark.usefixtures("fresh_auth_rate_limits")


async def _admin_headers(client, db_session):
    """Store an Admin, sign in and return the authorization header."""
    db_session.add(
        User(
            email="auditor@example.com",
            full_name="Ada Auditor",
            hashed_password=get_password_hash(PASSWORD),
            role=UserRole.admin,
            is_active=True,
        )
    )
    await db_session.commit()
    response = client.post(
        "/api/auth/login", json={"email": "auditor@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _gone_run_id(db_session):
    """The id of a run that was stored and then deleted."""
    run = RunModel(name="Removed run", test_case_list="suite", status="Completed")
    db_session.add(run)
    await db_session.commit()
    run_id = run.id
    await db_session.delete(run)
    await db_session.commit()
    return run_id


async def test_events_name_their_targets_and_mark_deleted_ones(unauthenticated_client, db_session):
    headers = await _admin_headers(unauthenticated_client, db_session)
    run = RunModel(name="Nightly smoke", test_case_list="suite", status="Completed")
    product = Product(name="Gateway board")
    station = Runner(account="bench-07", password_hash="x", token="t")
    member = User(
        email="member@example.com",
        full_name="Mia Member",
        hashed_password=get_password_hash(PASSWORD),
        role=UserRole.viewer,
        is_active=True,
    )
    db_session.add_all([run, product, station, member])
    await db_session.commit()
    gone_run = await _gone_run_id(db_session)
    group = (
        await db_session.execute(
            select(AccessGroup).where(AccessGroup.system_key == "test_operators")
        )
    ).scalar_one()
    events = {
        "label.run": dict(target_type="test_run", target_id=str(run.id)),
        "label.gone": dict(target_type="run", target_id=str(gone_run)),
        "label.product": dict(target_type="product", target_id=str(product.id)),
        "label.user": dict(target_type="user", target_id=str(member.id)),
        "label.account": dict(target_type="station", target_id="bench-07"),
        "label.setting": dict(target_type="setting", target_id="smtp_host"),
        "label.created": dict(
            target_type="group",
            target_id=str(group.id),
            details={"route": "/api/groups", "created_id": group.id, "runner_id": station.id},
        ),
        "label.upload": dict(
            details={"route": "/api/results", "created_test_run_id": run.id, "runner_id": 999999}
        ),
    }
    for action, fields in events.items():
        db_session.add(AuditEvent(action=action, actor_type="user", outcome="success", **fields))
    await db_session.commit()

    response = unauthenticated_client.get(
        "/api/audit", params={"action": "label.", "limit": 50}, headers=headers
    )

    assert response.status_code == 200, response.text
    items = {item["action"]: item for item in response.json()["items"]}

    def named(action, field):
        """The name and the deleted flag of one field of one event."""
        item = items[action]
        name_key = "station_name" if field == "station" else f"{field}_label"
        return item[name_key], item[f"{field}_deleted"]

    assert named("label.run", "target") == ("Nightly smoke", False)
    assert named("label.gone", "target") == (None, True)
    assert named("label.product", "target") == ("Gateway board", False)
    assert named("label.user", "target") == ("Mia Member", False)
    assert named("label.account", "target") == (None, False)
    assert named("label.setting", "target") == (None, False)
    assert named("label.created", "target") == (group.name, False)
    assert named("label.created", "created") == (group.name, False)
    assert named("label.created", "station") == ("bench-07", False)
    assert named("label.upload", "created") == ("Nightly smoke", False)
    assert named("label.upload", "station") == (None, True)
    assert named("label.run", "station") == (None, False)
    assert items["label.gone"]["target_id"] == str(gone_run)
    stored = (
        await db_session.execute(select(AuditEvent).where(AuditEvent.action == "label.run"))
    ).scalar_one()
    assert (stored.target_type, stored.target_id) == ("test_run", str(run.id))


async def test_policies_keys_artifacts_results_and_channels_are_named_and_odd_ids_are_not(
    unauthenticated_client, db_session
):
    headers = await _admin_headers(unauthenticated_client, db_session)
    run = RunModel(name="Nightly smoke", test_case_list="suite", status="Completed")
    db_session.add(run)
    await db_session.commit()
    key = RunnerApiKey(label="Bench key", key_hash="hash-1", key_prefix="bud_ab")
    artifact = Artifact(
        filename="stored.log",
        original_filename="console.log",
        content_type="text/plain",
        size_bytes=3,
        storage_path="x/stored.log",
        test_run_id=run.id,
    )
    result = TestResult(test_class="PowerTests", test_method="test_rail", passed=True)
    channel = NotificationChannel(
        name="Release room", format="slack", url_encrypted="x", url_prefix="https://"
    )
    db_session.add_all([key, artifact, result, channel])
    await db_session.commit()
    policy = (
        await db_session.execute(select(Policy).where(Policy.system_key == "results"))
    ).scalar_one()
    events = {
        "odd.policy": dict(target_type="policy", target_id=str(policy.id)),
        "odd.key": dict(target_type="key", target_id=str(key.id)),
        "odd.artifact": dict(target_type="artifact", target_id=str(artifact.id)),
        "odd.result": dict(target_type="result", target_id=str(result.id)),
        "odd.channel": dict(
            target_type="notification_channel",
            target_id=str(channel.id),
            details={"route": "/api/settings/notifications/channels", "created_id": channel.id},
        ),
        "odd.superscript": dict(target_type="run", target_id="\u00b2"),
        "odd.huge": dict(target_type="run", target_id="99999999999"),
        "odd.negative": dict(target_type="run", target_id="-1"),
    }
    for action, fields in events.items():
        db_session.add(AuditEvent(action=action, actor_type="user", outcome="success", **fields))
    await db_session.commit()

    response = unauthenticated_client.get(
        "/api/audit", params={"action": "odd.", "limit": 50}, headers=headers
    )

    assert response.status_code == 200, response.text
    items = {item["action"]: item for item in response.json()["items"]}
    labels = {
        action: (item["target_label"], item["target_deleted"]) for action, item in items.items()
    }
    assert labels == {
        "odd.policy": (policy.name, False),
        "odd.key": ("Bench key", False),
        "odd.artifact": ("console.log", False),
        "odd.result": ("PowerTests.test_rail", False),
        "odd.channel": ("Release room", False),
        "odd.superscript": (None, False),
        "odd.huge": (None, False),
        "odd.negative": (None, False),
    }
    assert items["odd.channel"]["created_label"] == "Release room"
