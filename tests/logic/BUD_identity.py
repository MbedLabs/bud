"""
* @file     ${tests/logic/BUD_identity.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The product name and identity are fixed: no environment variable or .env entry changes them.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests settings, emails, the API, a started app, templates, notifications,
*           reports and the web app manifest.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import fitz

from app import main
from app.core import config, identity
from app.services import mail_service, notify, report_pdf, run_reports
from tests.logic.identity import IdentityBase


class IdentityTest(IdentityBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_name, self.tc_full = identity.BUD_PRODUCT_NAME, identity.BUD_PRODUCT_IDENTITY
        with mock.patch.dict(os.environ, {p.IDENTITY_OLD_SETTING: p.IDENTITY_OVERRIDE}):
            self.tc_env_has_name = hasattr(config.Settings(_env_file=None), p.IDENTITY_OLD_SETTING)
            self.tc_invite = (
                self.mails(lambda: mail_service.send_invite_email(**p.IDENTITY_INVITE)) or [{}]
            )[0]
        dotenv = self.bud.bud_work_folder() / ".env"
        dotenv.write_text(p.IDENTITY_DOTENV, encoding="utf-8")
        cleared = {
            key: os.environ.pop(key) for key in p.IDENTITY_DOTENV_CLEARED if key in os.environ
        }
        try:
            settings = config.Settings(_env_file=dotenv)
        finally:
            os.environ.update(cleared)
        self.tc_dotenv_uploads = settings.UPLOADS_PER_15_MINUTES
        self.tc_dotenv_has_name = hasattr(settings, p.IDENTITY_OLD_SETTING)
        self.tc_requests = self.mails(
            lambda: (
                mail_service.send_access_request_email(**p.IDENTITY_ACCESS_REQUEST),
                mail_service.send_report_request_email(**p.IDENTITY_REPORT_REQUEST),
            )
        )
        self.tc_api_title = main.app.title
        self.bud.bud_start_app(signed_in=False)
        self.tc_root_message = (
            self.bud.bud_request(p.GET, p.IDENTITY_ROOT_PATH).json().get("message")
        )
        self.tc_process = subprocess.run(
            [sys.executable, "-c", p.IDENTITY_PROCESS_SCRIPT],
            cwd=Path(main.__file__).resolve().parents[1],
            env={
                **os.environ,
                p.IDENTITY_OLD_SETTING: p.IDENTITY_OVERRIDE,
                "BUD_DOTENV_DISABLED": "1",
            },
            capture_output=True,
            text=True,
            timeout=p.IDENTITY_PROCESS_TIMEOUT,
        )
        self.tc_html_templates = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(mail_service.TEMPLATE_DIR.glob("*.html"))
        }
        self.tc_spelled = [
            path.name
            for path in sorted(mail_service.TEMPLATE_DIR.iterdir())
            if re.search(p.IDENTITY_SPELLED_NAME, path.read_text(encoding="utf-8"))
        ]
        self.tc_open_in, self.tc_sample = notify.OPEN_IN_BUD, notify.sample_summary().name
        document = fitz.open(
            stream=report_pdf.render_report(self.pdf_request()), filetype=p.PDF_FORMAT
        )
        self.tc_pdf_author, self.tc_pdf_text = document.metadata["author"], document[0].get_text()
        document.close()
        db = self.bud.bud_open_session()
        self.tc_summary_title = self.bud.bud_await(run_reports.build_summary_report(db, [])).title
        manifest = json.loads(self.bud.bud_read_repository_file(p.IDENTITY_MANIFEST))
        self.tc_manifest_names = (manifest.get("name"), manifest.get("short_name"))

    @staticmethod
    def mails(send):
        """The emails send passes to mail_service.send_email."""
        sent = []
        with mock.patch.object(mail_service, "send_email", lambda **mail: sent.append(mail)):
            send()
        return sent

    def pdf_request(self):
        """A one-run report."""
        return report_pdf.ReportRequest(
            title=self.parameters.IDENTITY_PDF_TITLE,
            subtitle=self.parameters.IDENTITY_PDF_SUBTITLE,
            filters=[],
            overall=report_pdf.Outcome(passed=1),
            run=report_pdf.RunDetail(**self.parameters.IDENTITY_PDF_RUN),
            app_version=self.parameters.IDENTITY_PDF_VERSION,
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    IdentityTest().run()
