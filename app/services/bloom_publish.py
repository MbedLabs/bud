"""Publishing a run's report into Bloom, when someone asks for it.

Deliberately not automatic. A suite that runs nightly would otherwise put a
Report document into the PLM every night, and a project holding a year of
identical reports is harder to read than one holding none.
"""

from __future__ import annotations

import base64
import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Artifact, SystemSetting, TestResult, TestRun
from app.services.integration_secrets import decrypt_integration_secret

logger = logging.getLogger(__name__)

PUBLISHABLE_SUFFIXES = (".pdf", ".xml")
CANONICAL_TC_ID = re.compile(r"^(?P<prefix>[A-Z]{3})-TC-\d{3}$")


class BloomNotConfigured(RuntimeError):
    """Bud has no Bloom URL or token stored."""


class BloomProjectNotIdentifiable(ValueError):
    """A run's test-case IDs do not identify exactly one Bloom project."""


async def bloom_credentials(db: AsyncSession) -> tuple[str, str]:
    url_setting = await db.get(SystemSetting, "bloom_url")
    token_setting = await db.get(SystemSetting, "bloom_token_encrypted")
    if not (url_setting and token_setting and url_setting.value and token_setting.value):
        raise BloomNotConfigured("Bloom URL or access token is not configured in Bud settings.")
    return url_setting.value.rstrip("/"), decrypt_integration_secret(token_setting.value)


async def publishable_artifacts(db: AsyncSession, run_id: int) -> list[Artifact]:
    """The report documents of a run: its PDFs and its JUnit XML.

    Screenshots, captures and logs stay in Bud. They are evidence for whoever
    is debugging the run, not the record the PLM keeps.
    """
    rows = (
        await db.scalars(
            select(Artifact)
            .where(Artifact.test_run_id == run_id)
            .order_by(Artifact.created_at, Artifact.id)
        )
    ).all()
    return [a for a in rows if a.original_filename.lower().endswith(PUBLISHABLE_SUFFIXES)]


async def tc_ids_for_run(db: AsyncSession, run_id: int) -> list[str]:
    rows = (
        await db.scalars(select(TestResult.test_metadata).where(TestResult.test_run_id == run_id))
    ).all()
    found = {
        row["tc_id"]
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("tc_id"), str) and row["tc_id"]
    }
    return sorted(found)


def project_prefix_for_tc_ids(tc_ids: list[str]) -> str:
    """Infer one Bloom project from canonical ``AAA-TC-NNN`` identifiers."""
    if not tc_ids:
        raise BloomProjectNotIdentifiable(
            "This run has no canonical Bloom test-case IDs, so its project cannot be inferred."
        )

    matches = [(tc_id, CANONICAL_TC_ID.fullmatch(tc_id)) for tc_id in tc_ids]
    invalid = [tc_id for tc_id, match in matches if match is None]
    if invalid:
        raise BloomProjectNotIdentifiable(
            f"{invalid[0]} is not a canonical Bloom test-case ID (expected AAA-TC-NNN)."
        )

    prefixes = {match.group("prefix") for _, match in matches if match is not None}
    if len(prefixes) != 1:
        raise BloomProjectNotIdentifiable(
            "This run contains test cases from multiple Bloom projects and cannot be published "
            "as one report."
        )
    return prefixes.pop()


def build_payload(
    run: TestRun,
    project_prefix: str,
    files: list[tuple[str, str, bytes]],
    tc_ids: list[str],
    run_url: str | None,
) -> dict:
    return {
        "project_prefix": project_prefix,
        "bud_run_id": run.id,
        "run_name": run.name,
        "status": run.status,
        "total_tests": run.total_tests,
        "passed_tests": run.passed_tests,
        "failed_tests": run.failed_tests,
        "executed_at": (run.completed_at or run.created_at).isoformat(),
        "run_url": run_url,
        "tc_ids": tc_ids,
        "files": [
            {
                "filename": name,
                "content_type": content_type,
                "content_base64": base64.b64encode(payload).decode(),
            }
            for name, content_type, payload in files
        ],
    }


async def post_to_bloom(bloom_url: str, bloom_token: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{bloom_url}/api/bud/test-reports",
            json=payload,
            headers={"Authorization": f"Bearer {bloom_token}"},
        )
        response.raise_for_status()
        return response.json()
