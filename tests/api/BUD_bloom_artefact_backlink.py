"""
* @file     ${tests/api/BUD_bloom_artefact_backlink.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Bud keeps the Bloom suite a sync reached as the run's backlink.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests the suite choice, two syncs against a stood-in Bloom and the run endpoint.
"""

from unittest import mock

from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import SystemSetting, TestResult, TestRun
from app.services import bloom_sync
from app.services.integration_secrets import encrypt_integration_secret
from tests.api.bloom_artefact_backlink import BloomArtefactBacklinkBase


class BloomReply:
    """A Bloom answer with status 200 and the given body."""

    status_code = 200
    text = ""

    def __init__(self, body):
        self.body = body

    def json(self):
        """The answer's body."""
        return self.body


class BloomArtefactBacklinkTest(BloomArtefactBacklinkBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        cases = {**p.BLOOM_REFERENCE_CASES, **p.BLOOM_NO_REFERENCE_CASES}
        self.tc_references = {
            case: bloom_sync._suite_reference(body, synced)
            for case, (body, synced) in cases.items()
        }
        self.key = mock.patch.object(
            settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode()
        )
        self.key.start()
        self.tc_named_run = self.sync(p.BLOOM_NAMED_REPLY, p.BLOOM_NAMED_RUN)
        self.tc_unnamed_run = self.sync(p.BLOOM_UNNAMED_REPLY, p.BLOOM_UNNAMED_RUN)
        self.bud.bud_start_app()
        run = self.bud.bud_add_to_app(
            TestRun(
                name=p.BLOOM_EXPOSED_RUN,
                test_case_list=p.BLOOM_RUN_CASES,
                status=p.BLOOM_RUN_COMPLETED,
                **p.BLOOM_BACKLINK,
            )
        )
        self.tc_exposed = self.bud.bud_request(p.GET, p.TEST_RUN_PATH.format(run.id))

    def sync(self, reply, run_name):
        """Sync one run's result to a stood-in Bloom that answers with reply; return the run."""
        p = self.parameters
        self.bud.bud_start_app()
        run = self.bud.bud_add_to_app(
            TestRun(name=run_name, test_case_list=p.BLOOM_RUN_CASES, status=p.BLOOM_RUN_COMPLETED)
        )
        self.bud.bud_add_to_app(SystemSetting(key=p.BLOOM_URL_SETTING, value=p.BLOOM_URL))
        self.bud.bud_add_to_app(
            SystemSetting(
                key=p.BLOOM_TOKEN_SETTING, value=encrypt_integration_secret(p.BLOOM_CACHED_TOKEN)
            )
        )
        self.bud.bud_add_to_app(TestResult(test_run_id=run.id, **p.BLOOM_RESULT))

        async def answer(bloom_url, bloom_token, payload_results):
            return BloomReply(reply)

        with mock.patch.object(bloom_sync, "_post_to_bloom_with_retry", answer):
            self.bud.bud_await(bloom_sync.sync_results_to_bloom(run.id))
        return self.bud.bud_find_in_app(TestRun, id=run.id)[0]

    def tearDownClass(self):
        self.key.stop()
        super().tearDownClass()


if __name__ == "__main__":
    BloomArtefactBacklinkTest().run()
