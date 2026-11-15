"""
* @file     ${tests/api/BUD_bloom_sync.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A run's results reach Bloom as one row per test case, and each sync leaves its events.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the Bloom sync service on a fresh app database, with Bloom's answer faked.
"""

from types import SimpleNamespace
from unittest import mock

from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.models import SystemSetting, TestResult, TestRun, TestRunEvent
from app.services import bloom_sync
from app.services.integration_secrets import encrypt_integration_secret
from tests.api.bloom_sync import BloomSyncBase


async def rows_of(results):
    """The results as an async iterable."""
    for result in results:
        yield result


def result(passed=True, error=None, metadata=None):
    """A result as the coalescing reads it."""
    return SimpleNamespace(
        passed=passed, error_message=error, created_at=None, test_metadata=metadata
    )


class Answer:
    """Bloom's faked answer."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self.text = body.get("detail", "")
        self.body = body

    def json(self):
        return self.body


class BloomSyncTest(BloomSyncBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        self.tc_checks["coalesce"] = self.bud.bud_await(self.coalesce())
        self.tc_checks["tally"] = self.bud.bud_await(self.tally())
        self.tc_checks["missing settings"] = self.scenario(self.missing_settings)
        self.tc_checks["refused"] = self.scenario(self.refused)
        self.tc_checks["left out"] = self.scenario(self.left_out)

    def scenario(self, steps):
        """Run one scenario on a fresh app database with a fresh encryption key."""
        self.bud.bud_start_app()
        with mock.patch.object(
            settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode()
        ):
            return self.bud.bud_await(steps(self.bud.bud_open_session(on_app=True)))

    async def coalesce(self):
        """Two methods of one test case, one of them failing, and one passing test case."""
        p = self.parameters
        rows = await bloom_sync._coalesce_results_by_tc_id(
            rows_of(
                [
                    result(metadata={"tc_id": "PRJ-TC-001"}),
                    result(False, p.BLOOM_SYNC_FAILURE, {"tc_id": "PRJ-TC-001"}),
                    result(metadata={"tc_id": "PRJ-TC-035"}),
                ]
            ),
            p.BLOOM_SYNC_RUN_ID,
        )
        payload = sorted(rows, key=lambda row: row["tc_id"])
        times = [row.get("executed_at") for row in payload] + [None, None]
        expected = [
            {
                "bud_run_id": p.BLOOM_SYNC_RUN_ID,
                "comment": p.BLOOM_SYNC_FAILURE,
                "executed_at": times[0],
                "status": "Failed",
                "tc_id": "PRJ-TC-001",
            },
            {
                "bud_run_id": p.BLOOM_SYNC_RUN_ID,
                "comment": p.BLOOM_SYNC_COMMENT.format(p.BLOOM_SYNC_RUN_ID, times[1]),
                "executed_at": times[1],
                "status": "Passed",
                "tc_id": "PRJ-TC-035",
            },
        ]
        return {"rows": (payload, expected)}

    async def tally(self):
        """Results without a tc_id, a skipped result and one tagged result."""
        p = self.parameters
        counts = {}
        rows = await bloom_sync._coalesce_results_by_tc_id(
            rows_of(
                [
                    result(),
                    result(metadata={}),
                    result(
                        error="not on this bench", metadata={"tc_id": "PRJ-TC-002", "skipped": True}
                    ),
                    result(metadata={"tc_id": "PRJ-TC-003"}),
                ]
            ),
            p.BLOOM_SYNC_TALLY_RUN_ID,
            counts,
        )
        return {
            "rows sent": ([row["tc_id"] for row in rows], ["PRJ-TC-003"]),
            "tally": (counts, p.BLOOM_SYNC_TALLY),
            "left out text": (bloom_sync._left_out(counts), p.BLOOM_SYNC_LEFT_OUT),
            "nothing left out": (bloom_sync._left_out({"unidentified": 0, "skipped": 0}), ""),
        }

    @staticmethod
    async def events(db, run_id):
        """The events of one run, in order."""
        db.expire_all()
        found = await db.execute(
            select(TestRunEvent)
            .where(TestRunEvent.test_run_id == run_id)
            .order_by(TestRunEvent.sequence)
        )
        return found.scalars().all()

    async def configure(self, db, token):
        """Store Bloom's address and encrypted token."""
        db.add_all(
            [
                SystemSetting(key="bloom_url", value=self.parameters.BLOOM_SYNC_URL),
                SystemSetting(key="bloom_token_encrypted", value=encrypt_integration_secret(token)),
            ]
        )

    @staticmethod
    def first(events, index):
        """One event, or an empty one when it is missing."""
        if len(events) > index:
            return events[index]
        return SimpleNamespace(
            stage=None, status=None, title=None, message=None, event_metadata=None
        )

    async def missing_settings(self, db):
        """A sync while Bloom is not configured."""
        p = self.parameters
        run = TestRun(name="sync-missing-config", test_case_list="Bud.Tests", status="Completed")
        db.add(run)
        await db.commit()
        run_id = run.id
        await bloom_sync.sync_results_to_bloom(run_id)
        events = await self.events(db, run_id)
        event = self.first(events, 0)
        return {
            "event count": (len(events), 1),
            "stage": (event.stage, p.BLOOM_SYNC_STAGE),
            "status": (event.status, p.BLOOM_SYNC_SKIPPED[0]),
            "title": (event.title, p.BLOOM_SYNC_SKIPPED[1]),
            "says not configured": (
                p.BLOOM_SYNC_NOT_CONFIGURED in (event.message or "").lower(),
                True,
            ),
        }

    async def refused(self, db):
        """A sync Bloom refuses with HTTP 401."""
        p = self.parameters
        calls = []

        async def post(bloom_url, bloom_token, payload_results):
            calls.append((bloom_url, bloom_token, payload_results))
            return Answer(401, {"detail": "unauthorized"})

        run = TestRun(name="sync-401", test_case_list="Bud.Tests", status="Completed")
        db.add(run)
        await db.flush()
        await self.configure(db, p.BLOOM_SYNC_TOKEN)
        db.add(
            TestResult(
                test_run_id=run.id,
                test_class="VoltageTest",
                test_method="bud_check",
                passed=True,
                test_metadata={"tc_id": "PRJ-TC-001"},
            )
        )
        await db.commit()
        run_id = run.id
        with mock.patch.object(bloom_sync, "_post_to_bloom_with_retry", post):
            await bloom_sync.sync_results_to_bloom(run_id)
        url, token, sent = (calls or [(None, None, [])])[0]
        sent_row = (sent or [{}])[0]
        events = await self.events(db, run_id)
        requested, failed = self.first(events, 0), self.first(events, 1)
        return {
            "Bloom address": (url, p.BLOOM_SYNC_URL),
            "Bloom token": (token, p.BLOOM_SYNC_TOKEN),
            "rows sent": (
                sent,
                [
                    {
                        "tc_id": "PRJ-TC-001",
                        "status": "Passed",
                        "comment": sent_row.get("comment"),
                        "executed_at": sent_row.get("executed_at"),
                        "bud_run_id": run_id,
                    }
                ],
            ),
            "event count": (len(events), 2),
            "requested status": (requested.status, p.BLOOM_SYNC_REQUESTED[0]),
            "requested title": (requested.title, p.BLOOM_SYNC_REQUESTED[1]),
            "failed status": (failed.status, p.BLOOM_SYNC_FAILED[0]),
            "failed title": (failed.title, p.BLOOM_SYNC_FAILED[1]),
            "failed message": (failed.message, p.BLOOM_SYNC_FAILED[2]),
            "failed metadata": (failed.event_metadata, p.BLOOM_SYNC_FAILED_METADATA),
        }

    async def left_out(self, db):
        """Syncs of a run without any tc_id and of a run with one untagged result."""
        p = self.parameters

        async def post(bloom_url, bloom_token, payload_results):
            return Answer(200, {"updated": 1})

        await self.configure(db, "token")
        untagged = TestRun(name="untagged", test_case_list="Robot", status="Completed")
        mixed = TestRun(name="mixed", test_case_list="Robot", status="Completed")
        db.add_all([untagged, mixed])
        await db.flush()
        db.add_all(
            [
                TestResult(
                    test_run_id=untagged.id, test_class="Bench", test_method="a", passed=True
                ),
                TestResult(
                    test_run_id=mixed.id,
                    test_class="Bench",
                    test_method="b",
                    passed=True,
                    test_metadata={"tc_id": "PRJ-TC-001"},
                ),
                TestResult(test_run_id=mixed.id, test_class="Bench", test_method="c", passed=True),
            ]
        )
        await db.commit()
        untagged_id, mixed_id = untagged.id, mixed.id
        with mock.patch.object(bloom_sync, "_post_to_bloom_with_retry", post):
            await bloom_sync.sync_results_to_bloom(untagged_id)
            await bloom_sync.sync_results_to_bloom(mixed_id)
        skipped = (await self.events(db, untagged_id) or [self.first([], 0)])[-1].message
        completed = (await self.events(db, mixed_id) or [self.first([], 0)])[-1].message
        return {
            "untagged run message": (skipped, p.BLOOM_SYNC_UNTAGGED),
            "mixed run message": (completed, p.BLOOM_SYNC_MIXED),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    BloomSyncTest().run()
