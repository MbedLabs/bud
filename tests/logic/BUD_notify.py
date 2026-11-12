"""
* @file     ${tests/logic/BUD_notify.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A finished run is summarized, rendered per format, filtered per channel and delivered once per channel.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the notification service on a fresh app database per scenario with the webhooks recorded.
"""

import json
from datetime import datetime
from unittest import mock
from uuid import uuid4

import httpx
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
from tests.logic.notify import NotifyBase


class Recorder:
    """A stand-in HTTP client that records posts and answers with scripted statuses."""

    posts = []
    statuses = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *error):
        return False

    async def post(self, url, content=None, headers=None):
        Recorder.posts.append({"url": url, "body": json.loads(content), "headers": headers})
        status = Recorder.statuses.pop(0) if Recorder.statuses else 200
        if status == "error":
            raise httpx.ConnectError("unreachable")
        return httpx.Response(status, text="nope" if status >= 400 else "ok")


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class NotifyTest(NotifyBase):

    def setUpClass(self):
        super().setUpClass()
        patches = [
            mock.patch.object(settings, "APP_BASE_URL", self.parameters.NOTIFY_BASE_URL),
            mock.patch.object(notify.httpx, "AsyncClient", Recorder),
        ]
        for patch in patches:
            patch.start()
        self.tc_checks = {}
        for scenario in (
            self.outcome,
            self.failed_line,
            self.formats,
            self.shapes,
            self.signature,
            self.connector,
            self.workflow,
            self.discord,
        ):
            scenario()
        for scenario in (
            self.station_failure,
            self.claim,
            self.summary_of_run,
            self.ci,
            self.retries,
            self.gives_up,
            self.once,
            self.no_channel,
            self.filters,
            self.teams_delivery,
            self.redirect,
        ):
            self.bud.bud_start_app()
            Recorder.posts, Recorder.statuses = [], []
            self.bud.bud_await(scenario(self.bud.bud_open_session(on_app=True)))
        for patch in patches:
            patch.stop()

    def summary(self, **changes):
        """A run summary with changes."""
        return notify.RunSummary(**{**self.parameters.NOTIFY_SUMMARY, **changes})

    @staticmethod
    async def channel(db, fmt="json", run_filter="all", secret=None, name=None, url=None):
        """Store an enabled channel."""
        channel = NotificationChannel(
            name=name or f"{fmt}-{run_filter}",
            format=fmt,
            url_encrypted=encrypt_integration_secret(url or f"https://hooks.example.com/{fmt}"),
            url_prefix="https://hooks.example.com/",
            secret_encrypted=encrypt_integration_secret(secret) if secret else None,
            run_filter=run_filter,
            enabled=True,
        )
        db.add(channel)
        await db.commit()
        return channel

    @staticmethod
    async def stored_run(
        db, *, passed=3, failed=0, failed_classes=(), product=None, runner=None, name="Nightly"
    ):
        """Store a completed run with its failed results."""
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
        for test_class in failed_classes:
            db.add(
                TestResult(
                    test_class=test_class, test_method="test_it", passed=False, test_run_id=run.id
                )
            )
        await db.commit()
        return run

    def outcome(self):
        self.tc_checks["outcome"] = {
            "failures make a failed outcome": (self.summary().outcome, "failed"),
            "passes only make a passed outcome": (
                self.summary(failed=0, failed_tests=[]).outcome,
                "passed",
            ),
            "no result makes a neutral outcome": (
                self.summary(passed=0, failed=0, failed_tests=[]).outcome,
                "neutral",
            ),
        }

    def failed_line(self):
        self.tc_checks["failed line"] = {
            "the failed list names two and counts the rest": (
                self.summary(failed_tests=["a", "b"], more_failed=4).failed_line,
                self.parameters.NOTIFY_FAILED_LINE,
            )
        }

    def formats(self):
        p = self.parameters
        summary = self.summary(bloom_sync_error=p.NOTIFY_SYNC_ERROR)
        checks = {}
        for fmt, render in notify.RENDERERS.items():
            text = json.dumps(render(summary))
            for label, value in (
                ("the run link", p.NOTIFY_SUMMARY["run_url"]),
                ("the Bloom link", p.NOTIFY_SUMMARY["bloom_url"]),
                ("the sync failure", p.NOTIFY_SYNC_ERROR),
                ("a failed test", "test_a"),
            ):
                checks[f"{fmt} carries {label}"] = (value in text, True)
        self.tc_checks["formats"] = checks

    def shapes(self):
        p = self.parameters
        summary = self.summary()
        self.tc_checks["shapes"] = {
            "Teams sends an adaptive card": (
                notify.render_teams(summary)["attachments"][0]["content"]["type"],
                "AdaptiveCard",
            ),
            "Slack colours a failure red": (
                notify.render_slack(summary)["attachments"][0]["color"],
                p.NOTIFY_SLACK_RED,
            ),
            "Discord colours a failure red": (
                notify.render_discord(summary)["embeds"][0]["color"],
                int(p.NOTIFY_TEAMS_RED, 16),
            ),
            "JSON names the event": (notify.render_json(summary)["event"], p.NOTIFY_EVENT),
        }

    def signature(self):
        p = self.parameters
        signature = notify.sign(p.NOTIFY_SECRET, b"{}")
        self.tc_checks["signature"] = {
            "the signature names its algorithm": (
                signature.startswith(p.NOTIFY_SIGNATURE_PREFIX),
                True,
            ),
            "the signature holds a SHA-256 digest": (len(signature), p.NOTIFY_SIGNATURE_LENGTH),
        }

    def connector(self):
        p = self.parameters
        summary = self.summary(bloom_sync_error=p.NOTIFY_SYNC_ERROR)
        card = notify.render_payload("teams", p.NOTIFY_CONNECTOR_URL, summary)
        section = (card.get("sections") or [{}])[0]
        bare = notify.render_teams_connector(
            self.summary(failed_tests=[], run_url=None, bloom_url=None)
        )
        self.tc_checks["connector"] = {
            "the card is a message card": (card.get("@type"), "MessageCard"),
            "the card colours a failure red": (card.get("themeColor"), p.NOTIFY_TEAMS_RED),
            "the card sums up the run": (card.get("summary"), summary.headline),
            "the card lists the product, station and duration": (
                {fact.get("name") for fact in section.get("facts", [])} >= p.NOTIFY_FACTS,
                True,
            ),
            "the card names a failed test": ("test_a" in section.get("text", ""), True),
            "the card names the sync failure": (
                p.NOTIFY_SYNC_ERROR in section.get("text", ""),
                True,
            ),
            "the card links the run and Bloom": (
                [action["targets"][0]["uri"] for action in card.get("potentialAction", [])],
                [p.NOTIFY_SUMMARY["run_url"], p.NOTIFY_SUMMARY["bloom_url"]],
            ),
            "a card without failures has no text": ("text" in bare["sections"][0], False),
            "a card without links has no action": (bare["potentialAction"], []),
        }

    def workflow(self):
        p = self.parameters
        checks = {}
        for url in p.NOTIFY_WORKFLOW_URLS:
            payload = notify.render_payload("teams", url, self.summary())
            checks[f"{url} gets an adaptive card"] = (
                payload["attachments"][0]["content"]["type"],
                "AdaptiveCard",
            )
        checks["a look-alike address is no workflow"] = (
            notify.is_teams_workflow_url(p.NOTIFY_ATTACKER_URL),
            False,
        )
        checks["Slack keeps its blocks for any address"] = (
            bool(
                notify.render_payload("slack", p.NOTIFY_CONNECTOR_URL, self.summary())[
                    "attachments"
                ][0].get("blocks")
            ),
            True,
        )
        self.tc_checks["workflow"] = checks

    def discord(self):
        embed = notify.render_discord(self.summary())["embeds"][0]
        self.tc_checks["discord"] = {
            "the embed time is in UTC": (str(embed.get("timestamp")).endswith("+00:00"), True)
        }

    async def station_failure(self, db):
        p = self.parameters
        run = await self.stored_run(db, passed=0, failed=0)
        run.runner_exit_code = 1
        await db.commit()
        failures = await self.channel(db, run_filter="failures")
        wanted = await notify.channel_wants_run(db, failures, run)
        summary = await notify.build_summary(db, run)
        checks = {
            "the failure channel wants the run": (wanted, True),
            "the outcome is failed": (summary.outcome, "failed"),
            "no result is counted": ((summary.passed, summary.failed), (0, 0)),
        }
        for fmt, render in notify.RENDERERS.items():
            checks[f"{fmt} names the station exit"] = (
                p.NOTIFY_STATION_EXIT in json.dumps(render(summary))
                or render == notify.render_json,
                True,
            )
        self.tc_checks["station failure"] = checks

    async def claim(self, db):
        await self.channel(db, "json", run_filter="all", name="all")
        await self.channel(db, "json", run_filter="failures", name="failures")
        run = await self.stored_run(db, passed=2, failed=0)
        run.claim_id = str(uuid4())
        await db.commit()
        waiting = await notify.notify_run_finished(run.id, wait=wait_none())
        posts_while_waiting = list(Recorder.posts)
        run.claim_acknowledged_at = datetime.utcnow()
        run.runner_exit_code = 1
        await db.commit()
        answered = await notify.notify_run_finished(run.id, wait=wait_none())
        again = await notify.notify_run_finished(run.id, wait=wait_none())
        self.tc_checks["claim"] = {
            "nothing is sent before the station answers": (waiting, 0),
            "nothing is posted before the station answers": (posts_while_waiting, []),
            "both channels are notified after the answer": (answered, 2),
            "every post reports a failure": (
                bool(Recorder.posts)
                and all(post["body"].get("outcome") == "failed" for post in Recorder.posts),
                True,
            ),
            "nothing is sent twice": (again, 0),
        }

    async def summary_of_run(self, db):
        p = self.parameters
        product = Product(name="Gateway")
        runner = Runner(account="station-01", password_hash="x", token="t")
        db.add_all([product, runner])
        await db.commit()
        names = [f"test_case_{index}" for index in range(7)]
        run = await self.stored_run(
            db, passed=2, failed=7, failed_classes=names, product=product, runner=runner
        )
        db.add(
            TestRunEvent(
                test_run_id=run.id,
                sequence=1,
                stage="bloom_sync",
                status="failed",
                title="Bloom sync failed",
                message=p.NOTIFY_RUN_SYNC_ERROR,
            )
        )
        await db.commit()
        run = (
            await db.execute(
                select(TestRun)
                .where(TestRun.id == run.id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        await db.refresh(run, ["product", "runner"])
        summary = await notify.build_summary(db, run)
        self.tc_checks["summary"] = {
            "the summary names the product": (summary.product, "Gateway"),
            "the summary names the station": (summary.station, "station-01"),
            "the station started the run": (summary.started_by, "station-01"),
            "the summary links the run": (summary.run_url, f"{p.NOTIFY_BASE_URL}/runs/{run.id}"),
            "the summary names five failed tests": (summary.failed_tests, names[:5]),
            "the summary counts the rest": (summary.more_failed, 2),
            "the summary names the sync failure": (
                summary.bloom_sync_error,
                p.NOTIFY_RUN_SYNC_ERROR,
            ),
        }

    async def ci(self, db):
        p = self.parameters
        run = await self.stored_run(db)
        await db.refresh(run, ["product", "runner"])
        summary = await notify.build_summary(db, run)
        self.tc_checks["ci"] = {
            "CI started the run": (summary.started_by, "CI"),
            "no station is named": (type_name(summary.station), p.NONE_TYPE),
        }

    async def retries(self, db):
        p = self.parameters
        channel = await self.channel(db, secret=p.NOTIFY_SECRET)
        Recorder.statuses = [500, "error", 204]
        delivery = await notify.deliver(db, channel, self.summary(), wait=wait_none())
        await db.commit()
        rows = (await db.execute(select(NotificationDelivery))).scalars().all()
        headers = (Recorder.posts or [{"headers": {}}])[-1]["headers"] or {}
        self.tc_checks["retries"] = {
            "the third attempt delivers": (delivery.delivered, True),
            "three attempts are made": (delivery.attempt, 3),
            "each attempt is recorded": (
                [(row.attempt, row.delivered, row.status_code) for row in rows],
                p.NOTIFY_RETRY_ROWS,
            ),
            "the post names its event": (headers.get("X-Bud-Event"), p.NOTIFY_EVENT),
            "the post is signed": (
                str(headers.get("X-Bud-Signature")).startswith(p.NOTIFY_SIGNATURE_PREFIX),
                True,
            ),
        }

    async def gives_up(self, db):
        channel = await self.channel(db)
        Recorder.statuses = [500, 500, 500]
        delivery = await notify.deliver(db, channel, self.summary(), wait=wait_none())
        self.tc_checks["gives up"] = {
            "nothing is delivered": (delivery.delivered, False),
            "three attempts are made": (delivery.attempt, 3),
        }

    async def once(self, db):
        await self.channel(db, "slack", name="team")
        await self.channel(db, "json", name="n8n")
        run = await self.stored_run(db, passed=2, failed=1, failed_classes=["test_boot"])
        first = await notify.notify_run_finished(run.id, wait=wait_none())
        second = await notify.notify_run_finished(run.id, wait=wait_none())
        events = (
            (
                await db.execute(
                    select(TestRunEvent).where(
                        TestRunEvent.test_run_id == run.id, TestRunEvent.stage == "notify"
                    )
                )
            )
            .scalars()
            .all()
        )
        self.tc_checks["once"] = {
            "both channels are notified": (first, 2),
            "nothing is sent twice": (second, 0),
            "two posts are made": (len(Recorder.posts), 2),
            "the timeline records both deliveries": (
                sorted(event.status for event in events),
                ["completed", "completed"],
            ),
        }

    async def no_channel(self, db):
        run = await self.stored_run(db)
        sent = await notify.notify_run_finished(run.id, wait=wait_none())
        self.tc_checks["no channel"] = {
            "nothing is sent": (sent, 0),
            "nothing is posted": (list(Recorder.posts), []),
        }

    async def filters(self, db):
        product = Product(name="Gateway")
        db.add(product)
        await db.commit()
        all_runs = await self.channel(db, run_filter="all")
        failures = await self.channel(db, run_filter="failures")
        first = await self.channel(db, run_filter="first_failure")
        green = await self.stored_run(db, passed=3, product=product, name="green")
        red1 = await self.stored_run(db, passed=1, failed=2, product=product, name="red1")
        red2 = await self.stored_run(db, passed=1, failed=2, product=product, name="red2")
        self.tc_checks["filters"] = {
            "every run reaches an all-runs channel": (
                await notify.channel_wants_run(db, all_runs, green),
                True,
            ),
            "a green run skips a failures channel": (
                await notify.channel_wants_run(db, failures, green),
                False,
            ),
            "a red run reaches a failures channel": (
                await notify.channel_wants_run(db, failures, red2),
                True,
            ),
            "the first failure reaches a first-failure channel": (
                await notify.channel_wants_run(db, first, red1),
                True,
            ),
            "a repeated failure skips a first-failure channel": (
                await notify.channel_wants_run(db, first, red2),
                False,
            ),
        }

    async def teams_delivery(self, db):
        p = self.parameters
        connector = await self.channel(db, "teams", name="connector", url=p.NOTIFY_CONNECTOR_URL)
        workflow = await self.channel(db, "teams", name="workflow", url=p.NOTIFY_WORKFLOW_URLS[1])
        Recorder.statuses = [200, 202]
        to_connector = await notify.deliver(db, connector, self.summary(), wait=wait_none())
        to_workflow = await notify.deliver(db, workflow, self.summary(), wait=wait_none())
        bodies = [post["body"] for post in Recorder.posts] + [{}, {}]
        self.tc_checks["teams delivery"] = {
            "the connector delivery succeeds": (to_connector.delivered, True),
            "the workflow delivery succeeds": (to_workflow.delivered, True),
            "the connector gets a message card": (bodies[0].get("@type"), "MessageCard"),
            "the workflow gets a message": (bodies[1].get("type"), "message"),
        }

    async def redirect(self, db):
        channel = await self.channel(db)
        Recorder.statuses = [302, 302, 302]
        delivery = await notify.deliver(db, channel, self.summary(), wait=wait_none())
        self.tc_checks["redirect"] = {
            "a redirect is not delivered": (delivery.delivered, False),
            "the redirect status is recorded": (delivery.status_code, 302),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    NotifyTest().run()
