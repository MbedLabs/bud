import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models import SystemSetting, TestResult, TestRun

logger = logging.getLogger(__name__)


async def sync_results_to_bloom(test_run_id: int):
    """
    Background task to sync test results from Bud to Bloom ALM.
    """
    async with async_session_maker() as db:
        try:
            # 1. Get Bloom Configuration from SystemSettings
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

            # 2. Get the Test Run and its associated Campaign ID (if linked)
            result = await db.execute(select(TestRun).where(TestRun.id == test_run_id))
            test_run = result.scalar_one_or_none()

            if not test_run or not test_run.product_composition_id:
                logger.info(
                    f"Bloom sync skipped for run {test_run_id}: Run not found or not linked to a Bloom Campaign (product_composition_id)."
                )
                return

            campaign_id = test_run.product_composition_id

            # 3. Get all results for this run that have a work_package_id (mapping to Bloom tc_id)
            # Actually, the runner usually sends tc_id in metadata or work_package_id.
            # In Bud, 'work_package_id' is used as the link to Bloom's TC ID (e.g., "PRJ-TC-001").
            results_query = await db.execute(
                select(TestResult).where(TestResult.test_run_id == test_run_id)
            )
            results = results_query.scalars().all()

            payload_results = []
            for res in results:
                # We need a TC ID to sync. We'll check work_package_id first, then metadata
                tc_id = None
                if res.work_package_id:
                    # If it's stored as an int, we might need a mapping,
                    # but if the user provided the string TC ID, it works.
                    tc_id = str(res.work_package_id)
                elif res.test_metadata and "tc_id" in res.test_metadata:
                    tc_id = res.test_metadata["tc_id"]

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

            # 4. Push to Bloom
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{bloom_url}/api/campaigns/{campaign_id}/sync-results",
                    json={"results": payload_results},
                    headers={"Authorization": f"Bearer {bloom_token}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"Successfully synced {data.get('updated')} results to Bloom Campaign {campaign_id} for run {test_run_id}."
                    )
                else:
                    logger.error(
                        f"Failed to sync to Bloom: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            logger.exception(f"Error during Bloom sync for run {test_run_id}: {e}")
