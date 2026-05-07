import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models import TestResult
from app.services.run_events import record_test_run_event

logger = logging.getLogger(__name__)


def _coalesce_results_by_tc_id(results: list[TestResult], test_run_id: int) -> list[dict]:
    grouped: dict[str, dict] = {}

    for res in results:
        tc_id = None
        if res.test_metadata and isinstance(res.test_metadata, dict):
            tc_id = res.test_metadata.get("tc_id")

        if not tc_id:
            continue

        executed_at = (
            res.created_at.isoformat() if res.created_at else datetime.utcnow().isoformat()
        )
        entry = grouped.setdefault(
            tc_id,
            {
                "tc_id": tc_id,
                "status": "Passed",
                "comment": "Automated sync from Bud",
                "executed_at": executed_at,
                "bud_run_id": test_run_id,
            },
        )

        # Preserve the latest execution timestamp seen for the TC.
        if executed_at > entry["executed_at"]:
            entry["executed_at"] = executed_at

        # Any failing method makes the overall TC execution fail.
        if not res.passed:
            entry["status"] = "Failed"
            if res.error_message:
                entry["comment"] = res.error_message

    return list(grouped.values())


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
                await record_test_run_event(
                    db,
                    test_run_id=test_run_id,
                    stage="bloom_sync",
                    status="skipped",
                    title="Bloom sync skipped",
                    message="Bloom URL or access token is not configured in Bud settings.",
                )
                await db.commit()
                return

            bloom_url = url_setting.value.rstrip("/")
            bloom_token = token_setting.value

            # 2. Get all results for this run that carry a tc_id in their metadata
            results_query = await db.execute(
                select(TestResult).where(TestResult.test_run_id == test_run_id)
            )
            results = results_query.scalars().all()

            payload_results = _coalesce_results_by_tc_id(results, test_run_id)

            if not payload_results:
                logger.info(
                    f"Bloom sync skipped for run {test_run_id}: No results with valid tc_id found."
                )
                await record_test_run_event(
                    db,
                    test_run_id=test_run_id,
                    stage="bloom_sync",
                    status="skipped",
                    title="Bloom sync skipped",
                    message="No result metadata included a Bloom tc_id to match.",
                )
                await db.commit()
                return

            # 3. Push to Bloom's campaign-agnostic sync endpoint
            await record_test_run_event(
                db,
                test_run_id=test_run_id,
                stage="bloom_sync",
                status="running",
                title="Bloom sync requested",
                message=f"Sending {len(payload_results)} aggregated test case result row(s) to Bloom.",
                event_metadata={"bloom_url": bloom_url, "result_count": len(payload_results)},
            )
            await db.commit()

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
                    await record_test_run_event(
                        db,
                        test_run_id=test_run_id,
                        stage="bloom_sync",
                        status="completed" if not data.get("not_found") else "warning",
                        title="Bloom sync completed",
                        message=(
                            f"Bloom updated {data.get('updated', 0)} test case execution record(s)."
                            + (
                                f" Unmatched tc_id values: {', '.join(data.get('not_found', []))}."
                                if data.get("not_found")
                                else ""
                            )
                        ),
                        event_metadata=data,
                    )
                    await db.commit()
                else:
                    logger.error(
                        f"Failed to sync to Bloom: {response.status_code} - {response.text}"
                    )
                    await record_test_run_event(
                        db,
                        test_run_id=test_run_id,
                        stage="bloom_sync",
                        status="failed",
                        title="Bloom sync failed",
                        message=f"Bloom returned HTTP {response.status_code}.",
                        event_metadata={"response": response.text[:500]},
                    )
                    await db.commit()

        except Exception as e:
            logger.exception(f"Error during Bloom sync for run {test_run_id}: {e}")
            try:
                await record_test_run_event(
                    db,
                    test_run_id=test_run_id,
                    stage="bloom_sync",
                    status="failed",
                    title="Bloom sync failed",
                    message=str(e),
                )
                await db.commit()
            except Exception:
                logger.exception("Failed to persist Bloom sync failure event.")
