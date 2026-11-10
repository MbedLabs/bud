"""
* @file     ${tests/sec/BUD_integration_settings_security.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Bloom integration credentials are write-only and encrypted at rest.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with its own encryption key.
"""

from unittest import mock

from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import SystemSetting
from tests.sec.integration_settings_security import IntegrationSettingsSecurityBase


class IntegrationSettingsSecurityTest(IntegrationSettingsSecurityBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.key = mock.patch.object(
            settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode()
        )
        self.key.start()
        self.bud.bud_start_app()
        self.tc_saved = self.save(p.BLOOM_URL, p.BLOOM_TOKEN)
        self.tc_stored = self.bud.bud_find_in_app(SystemSetting, key=p.BLOOM_TOKEN_SETTING)
        self.tc_read = self.bud.bud_request(p.GET, p.PLM_PATH)
        self.bud.bud_start_app()
        self.save(p.BLOOM_URL, p.BLOOM_KEPT_TOKEN)
        self.tc_new_origin_before = self.stored_token()
        self.tc_new_origin = self.save(p.BLOOM_OTHER_ORIGIN, p.BLOOM_MASKED_TOKEN)
        self.tc_new_origin_after = self.stored_token()
        self.bud.bud_start_app()
        self.save(p.BLOOM_URL, p.BLOOM_KEPT_TOKEN)
        self.tc_same_origin_before = self.stored_token()
        self.tc_same_origin = self.save(p.BLOOM_SAME_ORIGIN, p.BLOOM_MASKED_TOKEN)
        self.tc_same_origin_after = self.stored_token()
        self.bud.bud_start_app()
        self.tc_bad_port = self.bud.bud_request(
            p.POST, p.PLM_PATH, json={"bloom_url": p.BLOOM_INVALID_PORT}
        )
        self.bud.bud_start_app()
        self.tc_generic_read = self.bud.bud_request(
            p.GET, p.SETTING_PATH.format(p.BLOOM_TOKEN_SETTING)
        )
        self.tc_generic_write = self.bud.bud_request(
            p.PUT, p.SETTING_PATH.format(p.BLOOM_TOKEN_SETTING), json={"value": p.BLOOM_PLAINTEXT}
        )

    def save(self, url, token):
        """Save the PLM integration with a Bloom URL and token."""
        return self.bud.bud_request(
            self.parameters.POST,
            self.parameters.PLM_PATH,
            json={"bloom_url": url, "bloom_token": token},
        )

    def stored_token(self):
        """The stored encrypted Bloom token."""
        return self.bud.bud_find_in_app(SystemSetting, key=self.parameters.BLOOM_TOKEN_SETTING)[
            0
        ].value

    def tearDownClass(self):
        self.key.stop()
        super().tearDownClass()


if __name__ == "__main__":
    IntegrationSettingsSecurityTest().run()
