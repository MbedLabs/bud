import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models import TestResult, TestRun

logger = logging.getLogger(__name__)


async def sync_results_to_bloom(test_run_id: int):
    """
    Background task to sync test results from Bud to Bloom PLM.

    Matches results to Bloom campaign items by tc_id extracted from
    test_metadata (populated by the runner from BloomMetaData on the
    test class). No campaign_id is required on the TestRun.
    """
    async with async_session_maker() as db:
        try:
            # 1. Get Bloom Configuration from SystemSettings
            from app.models import SystemSetting

            url_setting = await db.get(SystemSetting, "bloom_url")
            token_setting = await db.get(SystemSetting, "bloom_token")

            if (
                not url_setting
                or not token_setting
                or not url_setting.value
                or not token_setting.value
            ):
                logger.info(
                    f"Bloom sync skipped for run {test_run_id}: Bloom URL or Token not configured in SystemSettings."
                )
                return

            bloom_url = url_setting.value.rstrip("/")
            bloom_token = token_setting.value

            # 2. Get all results for this run that carry a tc_id in their metadata
            results_query = await db.execute(
                select(TestResult).where(TestResult.test_run_id == test_run_id)
            )
            results = results_query.scalars().all()

            payload_results = []
            for res in results:
                tc_id = None
                if res.test_metadata and isinstance(res.test_metadata, dict):
                    tc_id = res.test_metadata.get("tc_id")

                if not tc_id:
                    continue

                payload_results.append(
                    {
                        "tc_id": tc_id,
                        "status": "Passed" if res.passed else "Failed",
                        "comment": (
                            res.error_message if not res.passed else "Automated sync from Bud"
                        ),
                        "executed_at": (
                            res.created_at.isoformat()
                            if res.created_at
                            else datetime.utcnow().isoformat()
                        ),
                    }
                )

            if not payload_results:
                logger.info(
                    f"Bloom sync skipped for run {test_run_id}: No results with valid tc_id found."
                )
                return

            # 3. Push to Bloom's campaign-agnostic sync endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{bloom_url}/api/campaigns/sync-results",
                    json={"results": payload_results},
                    headers={"Authorization": f"Bearer {bloom_token}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"Successfully synced {data.get('updated')} results to Bloom for run {test_run_id}."
                        + (f" Not found: {data.get('not_found')}" if data.get("not_found") else "")
                    )
                else:
                    logger.error(
                        f"Failed to sync to Bloom: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            logger.exception(f"Error during Bloom sync for run {test_run_id}: {e}")
