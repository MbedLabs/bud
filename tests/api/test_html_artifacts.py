"""Robot Framework's log.html and report.html upload as artifacts and only ever download."""

import pytest


@pytest.mark.asyncio
async def test_an_html_report_is_accepted_and_served_as_a_download(client):
    uploaded = client.post(
        "/api/uploads",
        files={"file": ("log.html", b"<html><script>alert(1)</script></html>", "text/html")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["content_type"] == "text/html"

    downloaded = client.get(f"/api/uploads/{uploaded.json()['id']}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert 'filename="log.html"' in downloaded.headers["content-disposition"]
    assert downloaded.headers["content-security-policy"] == "sandbox"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
