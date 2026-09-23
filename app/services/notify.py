"""Run-finished notifications: one summary per finished run, rendered per channel format.

A channel posts to a chat tool (Teams, Slack, Discord) or to any endpoint that wants
the plain summary (json). Delivery reuses the ``bloom_sync`` pattern (httpx with
tenacity retries), records one ``NotificationDelivery`` row per attempt and a
``notify`` stage on the run timeline, and happens once per run and channel.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.db import database as db
from app.models import (
    NotificationChannel,
    NotificationDelivery,
    TestResult,
    TestRun,
    TestRunEvent,
)
from app.services.integration_secrets import decrypt_integration_secret
from app.services.run_events import record_test_run_event

logger = logging.getLogger(__name__)

FORMATS = ("teams", "slack", "discord", "json")
RUN_FILTERS = ("all", "failures", "first_failure")
MAX_FAILED_LISTED = 5
MAX_TEXT = 200
ATTEMPTS = 3

_COLOURS = {"passed": "2EB67D", "failed": "E01E5A", "neutral": "9CA3AF"}
_TEAMS_COLOURS = {"passed": "good", "failed": "attention", "neutral": "default"}


class DeliveryFailed(Exception):
    """A delivery attempt that the receiver did not accept."""


@dataclass
class RunSummary:
    """What one finished run looks like in a notification, independent of the format."""

    run_id: Optional[int]
    name: str
    product: Optional[str]
    station: Optional[str]
    software_under_test: Optional[str]
    started_by: str
    passed: int
    failed: int
    skipped: int
    duration_seconds: Optional[float]
    run_url: Optional[str]
    bloom_url: Optional[str] = None
    bloom_sync_error: Optional[str] = None
    failed_tests: list = field(default_factory=list)
    more_failed: int = 0

    @property
    def outcome(self) -> str:
        """``failed`` when any test failed, ``passed`` when some passed, else ``neutral``."""
        if self.failed > 0:
            return "failed"
        if self.passed > 0:
            return "passed"
        return "neutral"

    @property
    def headline(self) -> str:
        """One line: the run name and its counts."""
        return (
            f"{_clip(self.name)}: {self.passed} passed, {self.failed} failed, "
            f"{self.skipped} skipped"
        )

    @property
    def failed_line(self) -> Optional[str]:
        """The failed tests by name, up to five, then ``+N more``."""
        if not self.failed_tests:
            return None
        line = ", ".join(self.failed_tests)
        return f"{line} +{self.more_failed} more" if self.more_failed else line


def _clip(text: Optional[str], limit: int = MAX_TEXT) -> str:
    """Shorten text so every chat tool accepts the message."""
    text = text or ""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _duration(seconds: Optional[float]) -> str:
    """Render a duration as ``1m 05s``."""
    if seconds is None:
        return "n/a"
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m {secs:02d}s" if minutes else f"{secs}s"


def _facts(summary: RunSummary) -> list:
    """The label/value pairs every format shows."""
    return [
        ("Product", summary.product or "n/a"),
        ("Station", summary.station or "n/a"),
        ("Software under test", summary.software_under_test or "n/a"),
        ("Started by", summary.started_by),
        ("Duration", _duration(summary.duration_seconds)),
    ]


def render_json(summary: RunSummary) -> dict:
    """The plain summary object, for automation endpoints."""
    return {"event": "run.finished", "outcome": summary.outcome, **asdict(summary)}


def render_slack(summary: RunSummary) -> dict:
    """A Slack Block Kit message."""
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{summary.headline}*"}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{label}*\n{_clip(value)}"}
                for label, value in _facts(summary)
            ],
        },
    ]
    if summary.failed_line:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Failed:* {_clip(summary.failed_line, 1500)}"},
            }
        )
    if summary.bloom_sync_error:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Results not synced to Bloom: {_clip(summary.bloom_sync_error)}",
                    }
                ],
            }
        )
    buttons = []
    if summary.run_url:
        buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open in Bud"},
                "url": summary.run_url,
            }
        )
    if summary.bloom_url:
        buttons.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open in Bloom"},
                "url": summary.bloom_url,
            }
        )
    if buttons:
        blocks.append({"type": "actions", "elements": buttons})
    return {
        "text": summary.headline,
        "attachments": [{"color": f"#{_COLOURS[summary.outcome]}", "blocks": blocks}],
    }


def render_discord(summary: RunSummary) -> dict:
    """A Discord message with one embed."""
    fields = [
        {"name": label, "value": _clip(value), "inline": True} for label, value in _facts(summary)
    ]
    if summary.failed_line:
        fields.append(
            {"name": "Failed", "value": _clip(summary.failed_line, 1000), "inline": False}
        )
    if summary.bloom_sync_error:
        fields.append(
            {
                "name": "Results not synced to Bloom",
                "value": _clip(summary.bloom_sync_error),
                "inline": False,
            }
        )
    if summary.bloom_url:
        fields.append(
            {"name": "Bloom", "value": f"[Open in Bloom]({summary.bloom_url})", "inline": False}
        )
    embed = {
        "title": _clip(summary.headline, 250),
        "color": int(_COLOURS[summary.outcome], 16),
        "fields": fields,
    }
    if summary.run_url:
        embed["url"] = summary.run_url
    return {"embeds": [embed]}


def render_teams(summary: RunSummary) -> dict:
    """A Teams Adaptive Card, accepted by Workflows and classic Office 365 webhooks."""
    body = [
        {
            "type": "TextBlock",
            "text": summary.headline,
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
            "color": _TEAMS_COLOURS[summary.outcome],
        },
        {
            "type": "FactSet",
            "facts": [{"title": label, "value": _clip(value)} for label, value in _facts(summary)],
        },
    ]
    if summary.failed_line:
        body.append(
            {
                "type": "TextBlock",
                "text": f"Failed: {_clip(summary.failed_line, 1500)}",
                "wrap": True,
            }
        )
    if summary.bloom_sync_error:
        body.append(
            {
                "type": "TextBlock",
                "text": f"Results not synced to Bloom: {_clip(summary.bloom_sync_error)}",
                "wrap": True,
                "color": "warning",
            }
        )
    actions = []
    if summary.run_url:
        actions.append({"type": "Action.OpenUrl", "title": "Open in Bud", "url": summary.run_url})
    if summary.bloom_url:
        actions.append(
            {"type": "Action.OpenUrl", "title": "Open in Bloom", "url": summary.bloom_url}
        )
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }
    if actions:
        card["actions"] = actions
    return {
        "type": "message",
        "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}
        ],
    }


RENDERERS: dict = {
    "teams": render_teams,
    "slack": render_slack,
    "discord": render_discord,
    "json": render_json,
}


def sign(secret: str, body: bytes) -> str:
    """The ``X-Bud-Signature`` value: HMAC-SHA256 of the body under the channel secret."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def run_url(run_id: int) -> str:
    """The run page in Bud."""
    return f"{settings.APP_BASE_URL.rstrip('/')}/runs/{run_id}"


async def build_summary(session: AsyncSession, run: TestRun) -> RunSummary:
    """Collect everything a notification says about a finished run."""
    failed_classes = (
        (
            await session.execute(
                select(TestResult.test_class)
                .where(TestResult.test_run_id == run.id, TestResult.passed.is_(False))
                .distinct()
                .order_by(TestResult.test_class)
            )
        )
        .scalars()
        .all()
    )
    sync_failure = (
        await session.execute(
            select(TestRunEvent)
            .where(
                TestRunEvent.test_run_id == run.id,
                TestRunEvent.stage == "bloom_sync",
                TestRunEvent.status == "failed",
            )
            .order_by(TestRunEvent.sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return RunSummary(
        run_id=run.id,
        name=run.name,
        product=run.product.name if run.product else None,
        station=run.runner.account if run.runner else None,
        software_under_test=run.ref_software_under_test,
        started_by=run.runner.account if run.runner else "CI",
        passed=run.passed_tests or 0,
        failed=run.failed_tests or 0,
        skipped=run.skipped_tests or 0,
        duration_seconds=run.duration_seconds,
        run_url=run_url(run.id),
        bloom_url=run.bloom_artefact_url,
        bloom_sync_error=(sync_failure.message or sync_failure.title) if sync_failure else None,
        failed_tests=[_clip(name, 80) for name in failed_classes[:MAX_FAILED_LISTED]],
        more_failed=max(0, len(failed_classes) - MAX_FAILED_LISTED),
    )


async def _previous_run_was_green(session: AsyncSession, run: TestRun) -> bool:
    """Whether the previous finished run of the same product and station passed fully."""
    previous = (
        await session.execute(
            select(TestRun)
            .where(
                TestRun.id != run.id,
                TestRun.status == "Completed",
                TestRun.product_id == run.product_id,
                TestRun.runner_id == run.runner_id,
                TestRun.id < run.id,
            )
            .order_by(TestRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if previous is None:
        return True
    return (previous.failed_tests or 0) == 0 and (previous.total_tests or 0) > 0


async def channel_wants_run(
    session: AsyncSession, channel: NotificationChannel, run: TestRun
) -> bool:
    """Apply the channel's filter: all runs, failures only, or the first failure after green."""
    failed = (run.failed_tests or 0) > 0
    if channel.run_filter == "failures":
        return failed
    if channel.run_filter == "first_failure":
        return failed and await _previous_run_was_green(session, run)
    return True


async def deliver(
    session: AsyncSession,
    channel: NotificationChannel,
    summary: RunSummary,
    *,
    wait: Optional[Callable] = None,
) -> NotificationDelivery:
    """Post the summary to one channel with retries; one delivery row per attempt."""
    body = json.dumps(RENDERERS[channel.format](summary)).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Bud-Event": "run.finished"}
    if channel.secret_encrypted:
        headers["X-Bud-Signature"] = sign(
            decrypt_integration_secret(channel.secret_encrypted), body
        )
    url = decrypt_integration_secret(channel.url_encrypted)
    last: Optional[NotificationDelivery] = None
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(ATTEMPTS),
            wait=wait or wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(DeliveryFailed),
            reraise=False,
        ):
            with attempt:
                number = attempt.retry_state.attempt_number
                last = NotificationDelivery(
                    test_run_id=summary.run_id, channel_id=channel.id, attempt=number
                )
                session.add(last)
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(url, content=body, headers=headers)
                except httpx.RequestError as exc:
                    last.error = _clip(str(exc), 500)
                    await session.flush()
                    raise DeliveryFailed(last.error) from exc
                last.status_code = response.status_code
                if response.status_code >= 400:
                    last.error = _clip(response.text, 500)
                    await session.flush()
                    raise DeliveryFailed(f"HTTP {response.status_code}")
                last.delivered = True
                await session.flush()
    except RetryError:
        logger.warning("Notification to channel %s failed after %s attempts", channel.id, ATTEMPTS)
    return last


async def notify_run_finished(test_run_id: int, *, wait: Optional[Callable] = None) -> int:
    """Post a finished run to every enabled channel that wants it, once per channel."""
    sent = 0
    async with db.async_session_maker() as session:
        try:
            run = (
                await session.execute(
                    select(TestRun)
                    .options(selectinload(TestRun.product), selectinload(TestRun.runner))
                    .where(TestRun.id == test_run_id)
                )
            ).scalar_one_or_none()
            if run is None:
                return 0
            channels = (
                (
                    await session.execute(
                        select(NotificationChannel)
                        .where(NotificationChannel.enabled.is_(True))
                        .order_by(NotificationChannel.id)
                    )
                )
                .scalars()
                .all()
            )
            if not channels:
                return 0
            already = set(
                (
                    await session.execute(
                        select(NotificationDelivery.channel_id).where(
                            NotificationDelivery.test_run_id == run.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            summary = await build_summary(session, run)
            for channel in channels:
                if channel.id in already or not await channel_wants_run(session, channel, run):
                    continue
                delivery = await deliver(session, channel, summary, wait=wait)
                ok = bool(delivery and delivery.delivered)
                sent += int(ok)
                await record_test_run_event(
                    session,
                    test_run_id=run.id,
                    stage="notify",
                    status="completed" if ok else "failed",
                    title=f"Notification {'sent' if ok else 'failed'}: {channel.name}",
                    message=(
                        f"Posted to {channel.name} ({channel.format})."
                        if ok
                        else f"{channel.name} did not accept the message after "
                        f"{delivery.attempt if delivery else ATTEMPTS} attempt(s): "
                        f"{delivery.error if delivery else 'no response'}"
                    ),
                    event_metadata={
                        "channel_id": channel.id,
                        "format": channel.format,
                        "attempts": delivery.attempt if delivery else 0,
                        "status_code": delivery.status_code if delivery else None,
                    },
                )
            await session.commit()
        except Exception:
            logger.exception("Run notification failed for run %s", test_run_id)
    return sent


def sample_summary() -> RunSummary:
    """The summary posted by "Send test message"."""
    return RunSummary(
        run_id=None,
        name="Bud test message",
        product="Example product",
        station="example-station",
        software_under_test="1.0.0",
        started_by="example-station",
        passed=12,
        failed=1,
        skipped=0,
        duration_seconds=95.0,
        run_url=settings.APP_BASE_URL.rstrip("/"),
        failed_tests=["test_example_failure"],
    )


async def send_test_message(
    session: AsyncSession, channel: NotificationChannel, *, wait: Optional[Callable] = None
) -> NotificationDelivery:
    """Post the sample summary to one channel so an administrator can see it."""
    return await deliver(session, channel, sample_summary(), wait=wait)
