"""
* @file     ${tests/api/BUD_bloom_publish_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A run's PDF and JUnit reports reach Bloom on request, as their bytes, for one Bloom project only.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the publish endpoint on a fresh app database per scenario, with Bloom's answer faked.
"""

import base64
from datetime import datetime
from unittest import mock

import httpx
from sqlalchemy import delete

from app.api import test_runs
from app.models import TestResult, TestRun
from app.services.bloom_publish import publishable_artifacts
from tests.api.bloom_publish_api import BloomPublishApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def result(run_id, tc_id, test_class="VoltageTests", message=None):
    """A passed result tagged with a Bloom test case."""
    assertion = {"passed": True, **({"message": message} if message else {})}
    return TestResult(
        test_run_id=run_id,
        test_class=test_class,
        test_method="test_supply" if test_class == "VoltageTests" else "test_case",
        passed=True,
        assertions=[assertion],
        test_metadata={"tc_id": tc_id},
    )


class BloomPublishApiTest(BloomPublishApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_checks = {}
        for scenario in (
            self.chosen,
            self.sent,
            self.as_bytes,
            self.not_configured,
            self.unfinished,
            self.legacy,
            self.bloom_refusal,
            self.unreachable,
            self.missing_run,
            self.finished,
        ):
            self.bud.bud_start_app()
            scenario()
        for case, (tc_ids, message) in p.BLOOM_PUBLISH_IDENTIFIERS.items():
            self.bud.bud_start_app()
            self.identifiers(case, tc_ids, message)

    def publish(self, run_id, post=None):
        """Ask for one run's publication, with Bloom's answer faked when post is given."""
        path = self.parameters.BLOOM_PUBLISH_PATH.format(run_id)
        if post is None:
            return self.bud.bud_request(self.parameters.POST, path)
        with mock.patch.object(test_runs, "post_to_bloom", post):
            return self.bud.bud_request(self.parameters.POST, path)

    def refusal(self, response, status, text):
        """The checks of a refused publication."""
        detail = str(body_of(response).get("detail"))
        return {
            "the publication is refused": (response.status_code, status),
            f"the refusal says {text}": (text in detail, True),
        }

    def chosen(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        chosen = self.bud.bud_await(
            publishable_artifacts(self.bud.bud_open_session(on_app=True), run.id)
        )
        self.tc_checks["chosen"] = {
            "the PDF and JUnit reports are chosen": (
                sorted(artifact.original_filename for artifact in chosen),
                [name.format(run.id) for name in p.BLOOM_PUBLISHED],
            )
        }

    def sent(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        self.bud.bud_configure_bloom()
        sent = {}

        async def post(url, token, payload):
            sent.update(url=url, payload=payload)
            return p.BLOOM_PUBLISH_ANSWER

        response = self.publish(run.id, post)
        payload = sent.get("payload", {})
        self.tc_checks["sent"] = {
            "the publication succeeds": (response.status_code, p.STATUS_OK),
            "the answer names Bloom's document": (
                body_of(response).get("doc_id"),
                p.BLOOM_PUBLISH_ANSWER["doc_id"],
            ),
            "the answer names the published files": (
                sorted(body_of(response).get("published_files") or []),
                [name.format(run.id) for name in p.BLOOM_PUBLISHED],
            ),
            "the payload names the project": (
                payload.get("project_prefix"),
                p.BLOOM_PUBLISH_PREFIX,
            ),
            "the payload names the run": (payload.get("bud_run_id"), run.id),
            "the payload holds two files": (len(payload.get("files") or []), 2),
        }

    def as_bytes(self):
        run = self.bud.bud_add_run_with_reports()
        self.bud.bud_configure_bloom()
        captured = {}

        async def post(url, token, payload):
            captured["files"] = payload["files"]
            return {"document_id": 1, "doc_id": "X-RPT-001", "created": True}

        self.publish(run.id, post)
        junit = next(
            (
                item
                for item in captured.get("files", [])
                if item.get("filename") == "report_junit.xml"
            ),
            {"content_base64": ""},
        )
        self.tc_checks["bytes"] = {
            "the JUnit report travels as its bytes": (
                base64.b64decode(junit["content_base64"]),
                b"<testsuites/>",
            ),
        }

    def not_configured(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        self.tc_checks["not configured"] = self.refusal(
            self.publish(run.id), p.STATUS_CONFLICT, p.BLOOM_PUBLISH_NOT_CONFIGURED
        )

    def unfinished(self):
        p = self.parameters
        self.bud.bud_configure_bloom()
        run = self.bud.bud_add_to_app(
            TestRun(
                name="No reports yet",
                test_case_list="Suite.CASES",
                status="Running",
                created_at=datetime.utcnow(),
            )
        )
        self.bud.bud_add_to_app(result(run.id, p.BLOOM_REPORT_TC_ID))
        response = self.publish(run.id)
        self.tc_checks["unfinished"] = {
            "the publication is refused": (response.status_code, p.STATUS_CONFLICT),
            "the refusal asks for a completed run": (
                p.BLOOM_PUBLISH_COMPLETED in str(body_of(response).get("detail")).lower(),
                True,
            ),
        }

    def legacy(self):
        p = self.parameters
        self.bud.bud_configure_bloom()
        now = datetime.utcnow()
        run = self.bud.bud_add_to_app(
            TestRun(
                name=p.BLOOM_PUBLISH_LEGACY,
                test_case_list="Suite.CASES",
                status="Completed",
                created_at=now,
                completed_at=now,
            )
        )
        self.bud.bud_add_to_app(result(run.id, p.BLOOM_REPORT_TC_ID, message="legacy assertion"))
        post = mock.AsyncMock(
            return_value={"document_id": 1, "doc_id": "PRJ-RPT-001", "created": True}
        )
        response = self.publish(run.id, post)
        payload = post.await_args.args[2] if post.await_args else {}
        self.tc_checks["legacy"] = {
            "the publication succeeds": (response.status_code, p.STATUS_OK),
            "the reports are made and published": (
                sorted(body_of(response).get("published_files") or []),
                [name.format(run.id) for name in p.BLOOM_PUBLISH_LEGACY_FILES],
            ),
            "the payload names the project": (
                payload.get("project_prefix"),
                p.BLOOM_PUBLISH_PREFIX,
            ),
        }

    def identifiers(self, case, tc_ids, message):
        p = self.parameters
        self.bud.bud_configure_bloom()
        run = self.bud.bud_add_run_with_reports(name="Bad identifiers")
        session = self.bud.bud_open_session(on_app=True)

        async def remove_results():
            await session.execute(delete(TestResult).where(TestResult.test_run_id == run.id))
            await session.commit()

        self.bud.bud_await(remove_results())
        for index, tc_id in enumerate(tc_ids):
            self.bud.bud_add_to_app(result(run.id, tc_id, test_class=f"Case{index}"))
        self.tc_checks[case] = self.refusal(self.publish(run.id), p.STATUS_CONFLICT, message)

    def bloom_refusal(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        self.bud.bud_configure_bloom()
        failure = httpx.HTTPStatusError(
            "404",
            request=httpx.Request("POST", p.BLOOM_REPORT_URL),
            response=httpx.Response(404, text=p.BLOOM_PUBLISH_REFUSAL),
        )
        response = self.publish(run.id, mock.AsyncMock(side_effect=failure))
        self.tc_checks["bloom refusal"] = self.refusal(
            response, p.STATUS_BAD_GATEWAY, p.BLOOM_PUBLISH_REFUSAL
        )

    def unreachable(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        self.bud.bud_configure_bloom()
        response = self.publish(run.id, mock.AsyncMock(side_effect=httpx.ConnectError("refused")))
        self.tc_checks["unreachable"] = self.refusal(
            response, p.STATUS_BAD_GATEWAY, p.BLOOM_PUBLISH_UNREACHABLE
        )

    def missing_run(self):
        p = self.parameters
        self.tc_checks["missing run"] = {
            "a missing run is not found": (
                self.publish(p.BLOOM_PUBLISH_MISSING_RUN).status_code,
                p.STATUS_NOT_FOUND,
            )
        }

    def finished(self):
        p = self.parameters
        self.bud.bud_configure_bloom()
        station = self.bud.bud_add_test_station(with_run=False)
        run = self.bud.bud_add_to_app(
            TestRun(
                runner_id=station.id,
                name="Autopublish check",
                test_case_list="Suite.CASES",
                status="Running",
                created_at=datetime.utcnow(),
            )
        )
        post = mock.AsyncMock()
        with mock.patch.object(test_runs, "post_to_bloom", post):
            completed = self.bud.bud_station_request(
                p.PATCH, p.TEST_RUNS_PATH + f"/{run.id}", json={"status": "Completed"}
            )
        self.tc_checks["finished"] = {
            "the station completes the run": (completed.status_code, p.STATUS_OK),
            "nothing is posted to Bloom": (post.call_count, 0),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    BloomPublishApiTest().run()
