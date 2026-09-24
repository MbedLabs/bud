"""Run-finished notifications: summary, renderers, filters, delivery, once per run and channel."""

import json

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from tenacity import wait_none

from app.core.config import settings
from app.models import (
    NotificationChannel,
    NotificationDelivery,
    Product,
    Runner,
    TestResult,
    TestRun,
    TestRunEvent,
)
from app.services import notify
from app.services.integration_secrets import encrypt_integration_secret


class _Recorder:
    """A stand-in httpx.AsyncClient that records posts and answers with scripted statuses."""

    posts: list = []
    statuses: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content=None, headers=None):
        _Recorder.posts.append({"url": url, "body": json.loads(content), "headers": headers})
        status = _Recorder.statuses.pop(0) if _Recorder.statuses else 200
        if status == "error":
            raise httpx.ConnectError("unreachable")
        return httpx.Response(status, text="nope" if status >= 400 else "ok")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "APP_BASE_URL", "https://bud.example.com")
    monkeypatch.setattr(notify.httpx, "AsyncClient", _Recorder)
    _Recorder.posts = []
    _Recorder.statuses = []


async def _channel(db, fmt="json", run_filter="all", secret=None, name=None):
    channel = NotificationChannel(
        name=name or f"{fmt}-{run_filter}",
        format=fmt,
        url_encrypted=encrypt_integration_secret(f"https://hooks.example.com/{fmt}"),
        url_prefix="https://hooks.example.com/",
        secret_encrypted=encrypt_integration_secret(secret) if secret else None,
        run_filter=run_filter,
        enabled=True,
    )
    db.add(channel)
    await db.commit()
    return channel


async def _run(
    db, *, passed=3, failed=0, failed_classes=(), product=None, runner=None, name="Nightly"
):
    run = TestRun(
        name=name,
        test_case_list="all",
        status="Completed",
        total_tests=passed + failed,
        passed_tests=passed,
        failed_tests=failed,
        duration_seconds=65.0,
        ref_software_under_test="2.4.1",
        product_id=product.id if product else None,
        runner_id=runner.id if runner else None,
    )
    db.add(run)
    await db.flush()
    for cls in failed_classes:
        db.add(TestResult(test_class=cls, test_method="test_it", passed=False, test_run_id=run.id))
    await db.commit()
    return run


def _summary(**overrides):
    base = dict(
        run_id=7,
        name="Nightly",
        product="Gateway",
        station="efr-testwand-01",
        software_under_test="2.4.1",
        started_by="efr-testwand-01",
        passed=10,
        failed=2,
        skipped=0,
        duration_seconds=65.0,
        run_url="https://bud.example.com/runs/7",
        bloom_url="https://bloom.example.com/suites/3",
        bloom_sync_error=None,
        failed_tests=["test_a", "test_b"],
        more_failed=0,
    )
    base.update(overrides)
    return notify.RunSummary(**base)


def test_outcome_colours():
    assert _summary().outcome == "failed"
    assert _summary(failed=0, failed_tests=[]).outcome == "passed"
    assert _summary(passed=0, failed=0, failed_tests=[]).outcome == "neutral"


def test_failed_list_is_capped_with_more():
    assert _summary(failed_tests=["a", "b"], more_failed=4).failed_line == "a, b +4 more"


def test_every_format_carries_the_links_and_the_sync_failure():
    summary = _summary(bloom_sync_error="Bloom returned HTTP 500.")
    for fmt, render in notify.RENDERERS.items():
        text = json.dumps(render(summary))
        assert "https://bud.example.com/runs/7" in text, fmt
        assert "https://bloom.example.com/suites/3" in text, fmt
        assert "Bloom returned HTTP 500." in text, fmt
        assert "test_a" in text, fmt


def test_renderer_shapes():
    summary = _summary()
    assert notify.render_teams(summary)["attachments"][0]["content"]["type"] == "AdaptiveCard"
    assert notify.render_slack(summary)["attachments"][0]["color"] == "#E01E5A"
    assert notify.render_discord(summary)["embeds"][0]["color"] == int("E01E5A", 16)
    assert notify.render_json(summary)["event"] == "run.finished"


def test_signature_is_hmac_sha256():
    signature = notify.sign("s3cr3t", b"{}")
    assert signature.startswith("sha256=") and len(signature) == 7 + 64


@pytest.mark.asyncio
async def test_summary_from_a_finished_run(db_session):
    product = Product(name="Gateway")
    runner = Runner(account="efr-testwand-01", password_hash="x", token="t")
    db_session.add_all([product, runner])
    await db_session.commit()
    names = [f"test_case_{i}" for i in range(7)]
    run = await _run(
        db_session, passed=2, failed=7, failed_classes=names, product=product, runner=runner
    )
    db_session.add(
        TestRunEvent(
            test_run_id=run.id,
            sequence=1,
            stage="bloom_sync",
            status="failed",
            title="Bloom sync failed",
            message="Bloom returned HTTP 502.",
        )
    )
    await db_session.commit()
    run = (
        await db_session.execute(
            select(TestRun).where(TestRun.id == run.id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    await db_session.refresh(run, ["product", "runner"])

    summary = await notify.build_summary(db_session, run)

    assert summary.product == "Gateway"
    assert summary.station == "efr-testwand-01"
    assert summary.started_by == "efr-testwand-01"
    assert summary.run_url == f"https://bud.example.com/runs/{run.id}"
    assert summary.failed_tests == names[:5]
    assert summary.more_failed == 2
    assert summary.bloom_sync_error == "Bloom returned HTTP 502."


@pytest.mark.asyncio
async def test_run_without_station_was_started_by_ci(db_session):
    run = await _run(db_session)
    await db_session.refresh(run, ["product", "runner"])
    summary = await notify.build_summary(db_session, run)
    assert summary.started_by == "CI"
    assert summary.station is None


@pytest.mark.asyncio
async def test_delivery_retries_and_records_each_attempt(db_session):
    channel = await _channel(db_session, secret="s3cr3t")
    _Recorder.statuses = [500, "error", 204]

    delivery = await notify.deliver(db_session, channel, _summary(), wait=wait_none())
    await db_session.commit()

    assert delivery.delivered is True and delivery.attempt == 3
    rows = (await db_session.execute(select(NotificationDelivery))).scalars().all()
    assert [(r.attempt, r.delivered, r.status_code) for r in rows] == [
        (1, False, 500),
        (2, False, None),
        (3, True, 204),
    ]
    headers = _Recorder.posts[-1]["headers"]
    assert headers["X-Bud-Event"] == "run.finished"
    assert headers["X-Bud-Signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_delivery_gives_up_after_three_attempts(db_session):
    channel = await _channel(db_session)
    _Recorder.statuses = [500, 500, 500]
    delivery = await notify.deliver(db_session, channel, _summary(), wait=wait_none())
    assert delivery.delivered is False and delivery.attempt == 3


@pytest.mark.asyncio
async def test_finished_run_posts_once_per_channel_with_timeline_event(db_session):
    await _channel(db_session, "slack", name="team")
    await _channel(db_session, "json", name="n8n")
    run = await _run(db_session, passed=2, failed=1, failed_classes=["test_boot"])

    assert await notify.notify_run_finished(run.id, wait=wait_none()) == 2
    assert await notify.notify_run_finished(run.id, wait=wait_none()) == 0

    assert len(_Recorder.posts) == 2
    events = (
        (
            await db_session.execute(
                select(TestRunEvent).where(
                    TestRunEvent.test_run_id == run.id, TestRunEvent.stage == "notify"
                )
            )
        )
        .scalars()
        .all()
    )
    assert sorted(e.status for e in events) == ["completed", "completed"]


@pytest.mark.asyncio
async def test_no_channel_means_nothing_is_sent(db_session):
    run = await _run(db_session)
    assert await notify.notify_run_finished(run.id, wait=wait_none()) == 0
    assert _Recorder.posts == []


@pytest.mark.asyncio
async def test_filters(db_session):
    product = Product(name="Gateway")
    db_session.add(product)
    await db_session.commit()
    all_runs = await _channel(db_session, run_filter="all")
    failures = await _channel(db_session, run_filter="failures")
    first = await _channel(db_session, run_filter="first_failure")

    green = await _run(db_session, passed=3, product=product, name="green")
    red1 = await _run(db_session, passed=1, failed=2, product=product, name="red1")
    red2 = await _run(db_session, passed=1, failed=2, product=product, name="red2")

    assert await notify.channel_wants_run(db_session, all_runs, green)
    assert not await notify.channel_wants_run(db_session, failures, green)
    assert await notify.channel_wants_run(db_session, failures, red2)
    assert await notify.channel_wants_run(db_session, first, red1)
    assert not await notify.channel_wants_run(db_session, first, red2)


CONNECTOR_URL = "https://acme.webhook.office.com/webhookb2/abc/IncomingWebhook/def"
WORKFLOW_URLS = (
    "https://prod-12.westeurope.logic.azure.com:443/workflows/abc/triggers/manual/paths/invoke",
    "https://default1234.environment.api.powerplatform.com/powerautomate/automations/direct/x",
)


def test_teams_connector_urls_get_a_message_card():
    summary = _summary(bloom_sync_error="Bloom returned HTTP 500.")
    card = notify.render_payload("teams", CONNECTOR_URL, summary)
    assert card["@type"] == "MessageCard" and card["themeColor"] == "E01E5A"
    assert card["summary"] == summary.headline
    section = card["sections"][0]
    assert {f["name"] for f in section["facts"]} >= {"Product", "Station", "Duration"}
    assert "test_a" in section["text"] and "Bloom returned HTTP 500." in section["text"]
    assert [a["targets"][0]["uri"] for a in card["potentialAction"]] == [
        "https://bud.example.com/runs/7",
        "https://bloom.example.com/suites/3",
    ]
    bare = notify.render_teams_connector(_summary(failed_tests=[], run_url=None, bloom_url=None))
    assert "text" not in bare["sections"][0] and bare["potentialAction"] == []


def test_teams_workflow_urls_get_an_adaptive_card():
    for url in WORKFLOW_URLS:
        payload = notify.render_payload("teams", url, _summary())
        assert payload["attachments"][0]["content"]["type"] == "AdaptiveCard", url
    assert not notify.is_teams_workflow_url("https://powerplatform.com.attacker.example/x")
    assert notify.render_payload("slack", CONNECTOR_URL, _summary())["attachments"][0]["blocks"]


def test_discord_embed_has_a_timestamp():
    embed = notify.render_discord(_summary())["embeds"][0]
    assert embed["timestamp"].endswith("+00:00")


@pytest.mark.asyncio
async def test_teams_delivery_picks_the_card_from_the_url(db_session):
    connector = await _channel(db_session, "teams", name="connector")
    connector.url_encrypted = encrypt_integration_secret(CONNECTOR_URL)
    workflow = await _channel(db_session, "teams", name="workflow")
    workflow.url_encrypted = encrypt_integration_secret(WORKFLOW_URLS[1])
    await db_session.commit()
    _Recorder.statuses = [200, 202]

    assert (await notify.deliver(db_session, connector, _summary(), wait=wait_none())).delivered
    assert (await notify.deliver(db_session, workflow, _summary(), wait=wait_none())).delivered
    assert _Recorder.posts[0]["body"]["@type"] == "MessageCard"
    assert _Recorder.posts[1]["body"]["type"] == "message"


@pytest.mark.asyncio
async def test_a_redirect_is_not_a_delivery(db_session):
    channel = await _channel(db_session)
    _Recorder.statuses = [302, 302, 302]
    delivery = await notify.deliver(db_session, channel, _summary(), wait=wait_none())
    assert delivery.delivered is False and delivery.status_code == 302
