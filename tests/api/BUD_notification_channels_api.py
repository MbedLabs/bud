"""
* @file     ${tests/api/BUD_notification_channels_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Notification channels are administrator-only, keep URL and secret write-only and encrypted,
*           and send a test message.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with its own encryption key.
"""

from unittest import mock

import httpx
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import NotificationChannel
from app.services import notify
from tests.api.notification_channels_api import NotificationChannelsApiBase


class AcceptingClient:
    """An httpx.AsyncClient stand-in that accepts every post and records its URL."""

    posted = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content=None, headers=None):
        """Record the URL and answer 200."""
        AcceptingClient.posted.append(url)
        return httpx.Response(200, text="ok")


class NotificationChannelsApiTest(NotificationChannelsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.key = mock.patch.object(
            settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode()
        )
        self.key.start()
        self.bud.bud_start_app()
        self.tc_created = self.add()
        self.tc_listed = self.bud.bud_request(p.GET, p.CHANNELS_PATH)
        channel_id = self.tc_created.json().get("id")
        self.tc_stored = self.bud.bud_find_in_app(NotificationChannel, id=channel_id)[0]
        self.bud.bud_start_app()
        channel_id = self.add().json()["id"]
        self.tc_url_before = self.stored_url(channel_id)
        self.tc_patched = self.bud.bud_request(
            p.PATCH, p.CHANNEL_PATH.format(channel_id), json=p.CHANNEL_PATCH
        )
        self.tc_url_after = self.stored_url(channel_id)
        self.bud.bud_start_app()
        self.tc_invalid = {
            case: self.add(**change).status_code for case, change in p.CHANNEL_INVALID.items()
        }
        self.tc_valid = self.add().status_code
        self.tc_duplicate = self.add().status_code
        self.bud.bud_start_app()
        channel_id = self.add().json()["id"]
        self.tc_deleted = self.bud.bud_request(
            p.DELETE, p.CHANNEL_PATH.format(channel_id)
        ).status_code
        self.tc_deleted_again = self.bud.bud_request(
            p.DELETE, p.CHANNEL_PATH.format(channel_id)
        ).status_code
        self.tc_missing = self.bud.bud_request(
            p.PATCH, p.CHANNEL_PATH.format(p.CHANNEL_MISSING_ID), json={}
        ).status_code
        self.bud.bud_start_app()
        AcceptingClient.posted = []
        with mock.patch.object(notify.httpx, "AsyncClient", AcceptingClient):
            channel_id = self.add().json()["id"]
            self.tc_test = self.bud.bud_request(p.POST, p.CHANNEL_TEST_PATH.format(channel_id))
        self.tc_posted = list(AcceptingClient.posted)
        self.bud.bud_start_app(signed_in=False)
        self.tc_signed_out = self.bud.bud_request(p.GET, p.CHANNELS_PATH).status_code

    def add(self, **changes):
        """Add a channel with the given changes to the example channel."""
        return self.bud.bud_request(
            self.parameters.POST,
            self.parameters.CHANNELS_PATH,
            json={**self.parameters.CHANNEL, **changes},
        )

    def stored_url(self, channel_id):
        """The stored encrypted URL of a channel."""
        return self.bud.bud_find_in_app(NotificationChannel, id=channel_id)[0].url_encrypted

    def tearDownClass(self):
        self.key.stop()
        super().tearDownClass()


if __name__ == "__main__":
    NotificationChannelsApiTest().run()
