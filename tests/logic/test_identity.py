"""The product name and identity are fixed: no environment variable or .env entry changes them."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")
os.environ.setdefault("RUNNER_API_KEY", "test-runner-api-key")

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.identity import BUD_PRODUCT_IDENTITY, BUD_PRODUCT_NAME
from app.services import mail_service, notify
from app.services.report_pdf import Outcome, ReportRequest, RunDetail, render_report
from app.services.run_reports import build_summary_report

BACKEND_DIR = Path(__file__).resolve().parents[2]
OVERRIDE = "Attempted Override"


def _capture_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(mail_service, "send_email", lambda **kwargs: sent.append(kwargs))
    return sent


def test_the_identity_constants():
    assert BUD_PRODUCT_NAME == "Bud TMP"
    assert BUD_PRODUCT_IDENTITY == "Bud TMP by EmbedLabs"


def test_an_environment_variable_does_not_rename_the_product(monkeypatch):
    monkeypatch.setenv("BUD_APP_NAME", OVERRIDE)

    settings = Settings(_env_file=None)
    sent = _capture_mail(monkeypatch)
    mail_service.send_invite_email(
        to_email="user@example.com", full_name="User", invite_link="https://bud.example/invite"
    )

    assert not hasattr(settings, "BUD_APP_NAME")
    assert sent[0]["subject"] == "You're invited to Bud TMP"
    assert "<title>Bud TMP by EmbedLabs</title>" in sent[0]["html_body"]
    assert "Welcome to Bud TMP by EmbedLabs</h1>" in sent[0]["html_body"]
    assert "You have been invited to join Bud TMP." in sent[0]["text_body"]
    assert OVERRIDE not in sent[0]["html_body"] + sent[0]["text_body"]


def test_a_dotenv_entry_does_not_rename_the_product_or_stop_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("BUD_DOTENV_DISABLED", raising=False)
    monkeypatch.delenv("BUD_UPLOADS_PER_15_MINUTES", raising=False)
    monkeypatch.delenv("UPLOADS_PER_15_MINUTES", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"BUD_APP_NAME={OVERRIDE}\nBUD_UPLOADS_PER_15_MINUTES=7\n", encoding="utf-8")

    settings = Settings(_env_file=dotenv)

    assert settings.UPLOADS_PER_15_MINUTES == 7
    assert not hasattr(settings, "BUD_APP_NAME")


def test_every_email_names_the_product(monkeypatch):
    sent = _capture_mail(monkeypatch)
    mail_service.send_access_request_email(
        to_email="admin@example.com",
        admin_name="Admin",
        requester_name="Reader",
        requester_email="reader@example.com",
        resource="run 7",
        project="",
        requested_at="2026-10-19 08:00:00",
        request_id="req-1",
        review_link="https://bud.example/access",
    )
    mail_service.send_report_request_email(
        to_email="publisher@example.com",
        publisher_name="Publisher",
        requester_name="Reader",
        requester_email="reader@example.com",
        project="PRJ",
        run_id="7",
        review_link="https://bud.example/runs/7",
    )

    assert [mail["subject"] for mail in sent] == [
        "Access requested on Bud TMP: run 7",
        "Report requested on Bud TMP: run #7",
    ]
    for mail in sent:
        assert "<title>Bud TMP by EmbedLabs</title>" in mail["html_body"]
        assert f">{BUD_PRODUCT_IDENTITY}</h1>" in mail["html_body"]
        assert BUD_PRODUCT_NAME in mail["text_body"]
    assert "requested the report for Bud TMP run #7" in sent[1]["text_body"]


def test_the_api_title_and_root_message_are_the_identity():
    from app.main import app

    assert app.title == "Bud TMP by EmbedLabs"
    assert TestClient(app).get("/").json()["message"] == "Bud TMP by EmbedLabs"


def test_the_app_starts_with_the_old_variable_set_and_keeps_its_identity():
    env = {**os.environ, "BUD_APP_NAME": OVERRIDE, "BUD_DOTENV_DISABLED": "1"}
    script = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "print('identity:', app.title)\n"
        "print('identity:', TestClient(app).get('/').json()['message'])\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.startswith("identity: ")]
    assert lines == ["identity: Bud TMP by EmbedLabs", "identity: Bud TMP by EmbedLabs"]


def test_every_html_email_template_titles_itself_with_the_identity():
    templates = sorted(mail_service.TEMPLATE_DIR.glob("*.html"))

    assert len(templates) == 8
    for template in templates:
        assert "<title>${app_identity}</title>" in template.read_text(
            encoding="utf-8"
        ), template.name


def test_no_email_template_spells_the_product_name():
    for template in sorted(mail_service.TEMPLATE_DIR.iterdir()):
        assert re.search(r"\bBud\b", template.read_text(encoding="utf-8")) is None, template.name


def test_notifications_name_the_product():
    assert notify.OPEN_IN_BUD == "Open in Bud TMP"
    assert notify.sample_summary().name == "Bud TMP test message"


def test_the_pdf_report_names_the_product():
    fitz = pytest.importorskip("fitz", reason="pymupdf reads the generated PDF")
    request = ReportRequest(
        title="Run report",
        subtitle="Run 7",
        filters=[],
        overall=Outcome(passed=1),
        run=RunDetail(
            run_id=7, name="smoke", status="Completed", run_url="https://bud.example/runs/7"
        ),
        app_version="1.2.0",
    )

    doc = fitz.open(stream=render_report(request), filetype="pdf")
    text = doc[0].get_text()

    assert doc.metadata["author"] == "Bud TMP by EmbedLabs"
    assert "Bud TMP 1.2.0" in text
    assert "Open in Bud TMP" in text
    assert "Powered by EmbedLabs" in text
    doc.close()


async def test_the_summary_report_title_names_the_product(db_session):
    request = await build_summary_report(db_session, [])

    assert request.title == "Bud TMP Test Report"


def test_the_web_app_manifest_names_the_product():
    manifest = json.loads((BACKEND_DIR / "ui/public/site.webmanifest").read_text(encoding="utf-8"))

    assert (manifest["name"], manifest["short_name"]) == ("Bud TMP by EmbedLabs", "Bud TMP")
