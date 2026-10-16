"""Company logo: admin customer-logo storage, retrieval, and PDF rendering."""

import base64
import io

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile

from app.api.company_logo import (
    delete_company_logo,
    get_company_logo,
    load_report_logo,
    set_company_logo,
)
from app.db.database import Base
from app.services.report_pdf import Breakdown, Outcome, ReportRequest, render_report

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()


def _upload(data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        io.BytesIO(data), filename="logo.png", headers=Headers({"content-type": content_type})
    )


async def test_set_get_delete_and_load(session):
    out = await set_company_logo(file=_upload(PNG, "image/png"), db=session, _admin=None)
    assert out["content_type"] == "image/png"
    resp = await get_company_logo(db=session, _entity=None)
    assert resp.body == PNG
    assert await load_report_logo(session) == PNG
    await delete_company_logo(db=session, _admin=None)
    with pytest.raises(HTTPException) as exc:
        await get_company_logo(db=session, _entity=None)
    assert exc.value.status_code == 404
    assert await load_report_logo(session) is None


async def test_non_image_rejected(session):
    with pytest.raises(HTTPException) as exc:
        await set_company_logo(file=_upload(b"nope", "text/plain"), db=session, _admin=None)
    assert exc.value.status_code == 415


def _request() -> ReportRequest:
    return ReportRequest(
        title="Bud Test Report",
        subtitle="Test outcomes",
        filters=[("Window", "Last 7 days")],
        overall=Outcome(passed=9, failed=1, skipped=2),
        breakdowns=[Breakdown("Per suite", "Suite", [("smoke", Outcome(9, 1, 2))])],
        app_version="1.0.0",
    )


def test_report_renders_with_and_without_company_logo():
    import fitz

    without = render_report(_request())
    withlogo = render_report(_request(), PNG)
    assert without.startswith(b"%PDF-")
    assert withlogo.startswith(b"%PDF-")
    # The company logo must actually land on the page, not be silently dropped:
    # exactly one more embedded image than the un-branded report.
    n_without = len(fitz.open(stream=without, filetype="pdf")[0].get_images())
    n_with = len(fitz.open(stream=withlogo, filetype="pdf")[0].get_images())
    assert n_with == n_without + 1
