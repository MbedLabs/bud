"""
* @file     ${tests/api/BUD_setup_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The first-run setup creates one active administrator, once, and needs no mail.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with no one signed in.
"""

from unittest import mock

from app.api import setup
from app.models.user import User
from app.services.mail_service import MailConfigurationError
from tests.api.setup_api import SetupApiBase


class SetupApiTest(SetupApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.empty_app()
        self.tc_empty = self.bud.bud_request(p.GET, p.SETUP_STATUS_PATH)
        self.bud.bud_start_app(signed_in=False)
        self.tc_seeded = self.bud.bud_request(p.GET, p.SETUP_STATUS_PATH)
        self.empty_app()
        self.tc_created = self.bud.bud_request(p.POST, p.SETUP_PATH, json=p.SETUP_OWNER)
        self.tc_admin = (self.bud.bud_find_in_app(User, email=p.SETUP_OWNER["email"]) or [None])[0]
        self.tc_after_setup = self.status()
        self.tc_second = self.bud.bud_request(
            p.POST, p.SETUP_PATH, json={**p.SETUP_OWNER, "email": p.SETUP_SECOND_EMAIL}
        )
        self.tc_users = len(self.bud.bud_find_in_app(User))
        self.empty_app()
        self.tc_short = self.bud.bud_request(
            p.POST, p.SETUP_PATH, json={**p.SETUP_OWNER, "password": p.SETUP_SHORT_PASSWORD}
        )
        self.empty_app()
        with mock.patch.object(setup, "send_admin_welcome_email", return_value=None):
            self.tc_quiet_body = self.bud.bud_request(
                p.POST, p.SETUP_PATH, json=p.SETUP_OWNER
            ).json()
        self.tc_after_quiet = self.status()
        self.empty_app()
        with mock.patch.object(setup, "send_admin_welcome_email", self.mail_unavailable):
            self.tc_no_mail = self.bud.bud_request(p.POST, p.SETUP_PATH, json=p.SETUP_OWNER)
        self.tc_after_no_mail = self.status()
        self.empty_app()
        self.tc_sent = {}
        with mock.patch.object(
            setup, "send_admin_welcome_email", lambda **values: self.tc_sent.update(values)
        ):
            self.bud.bud_request(p.POST, p.SETUP_PATH, json=p.SETUP_OWNER)

    def empty_app(self):
        """Start the app with no one signed in and remove every user."""
        self.bud.bud_start_app(signed_in=False)
        self.bud.bud_delete_in_app(User)

    def status(self):
        """The setup status the app reports."""
        return self.bud.bud_request(self.parameters.GET, self.parameters.SETUP_STATUS_PATH).json()

    @staticmethod
    def mail_unavailable(**values):
        """A welcome email that raises MailConfigurationError for disabled SMTP."""
        raise MailConfigurationError("SMTP is disabled")

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    SetupApiTest().run()
