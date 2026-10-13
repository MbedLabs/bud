"""Own-account picture upload, persistence, validation and isolation over HTTP."""

import asyncio
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.auth import router
from app.db.database import Base, get_db
from app.core.security import create_access_token
from app.models import User
from app.models.user import UserRole


@pytest.fixture
def picture_client():
    """An HTTP app using real bearer authentication and an isolated account database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with maker() as db:
            users = [
                User(
                    email=f"picture-{index}@example.com",
                    full_name=f"Picture User {index}",
                    hashed_password="unused",
                    role=UserRole.viewer,
                )
                for index in range(2)
            ]
            db.add_all(users)
            await db.commit()
            return [
                {
                    "Authorization": "Bearer "
                    + create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
                }
                for user in users
            ]

    async def database():
        async with maker() as db:
            yield db
            await db.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api/auth")
    app.dependency_overrides[get_db] = database
    headers = asyncio.run(seed())
    with TestClient(app) as client:
        yield client, headers
    asyncio.run(engine.dispose())


def image_bytes(color="purple"):
    """A raster picture with dimensions and metadata that need normalizing."""
    buffer = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("Author", "Metadata must not be retained")
    Image.new("RGB", (600, 300), color).save(buffer, format="PNG", pnginfo=metadata)
    return buffer.getvalue()


def upload(client, headers, data, mime="image/png"):
    """Submit the same multipart body as the Settings uploader."""
    return client.put(
        "/api/auth/me/picture", headers=headers, files={"file": ("picture.png", data, mime)}
    )


def test_picture_roundtrip_and_replacement_are_account_scoped(picture_client):
    client, (first, second) = picture_client
    assert client.get("/api/auth/me/picture", headers=first).status_code == 404
    result = upload(client, first, image_bytes())
    assert result.status_code == 200, result.text
    assert result.json()["has_profile_picture"] is True
    assert "profile_picture" not in result.json()
    stored = client.get("/api/auth/me/picture", headers=first)
    assert stored.status_code == 200
    assert stored.headers["content-type"] == "image/png"
    assert stored.headers["cache-control"] == "private, no-store"
    with Image.open(io.BytesIO(stored.content)) as image:
        assert image.size == (256, 128)
        assert "Author" not in image.info
    assert client.get("/api/auth/me", headers=first).json()["has_profile_picture"] is True
    assert client.get("/api/auth/me/picture", headers=second).status_code == 404
    assert upload(client, second, image_bytes("green")).status_code == 200
    assert client.get("/api/auth/me/picture", headers=first).content == stored.content
    assert upload(client, first, image_bytes("blue")).status_code == 200
    assert client.get("/api/auth/me/picture", headers=first).content != stored.content


def test_profile_save_keeps_effective_permissions(picture_client):
    client, (first, _) = picture_client
    before = client.get("/api/auth/me", headers=first)
    updated = client.put("/api/auth/me", headers=first, json={"full_name": "Updated name"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Updated name"
    assert before.json()["permissions"]
    assert updated.json()["permissions"] == before.json()["permissions"]


@pytest.mark.parametrize(
    ("data", "mime", "status"),
    [
        (b"broken", "image/png", 422),
        (b"", "image/png", 422),
        (b"<svg/>", "image/svg+xml", 415),
        (b"x" * 2_000_001, "image/png", 413),
    ],
    ids=["malformed", "empty", "svg", "oversized"],
)
def test_rejected_upload_preserves_saved_picture(picture_client, data, mime, status):
    client, (headers, _) = picture_client
    assert upload(client, headers, image_bytes()).status_code == 200
    before = client.get("/api/auth/me/picture", headers=headers).content
    result = upload(client, headers, data, mime)
    assert result.status_code == status, result.text
    assert client.get("/api/auth/me/picture", headers=headers).content == before


def test_picture_requires_authentication(picture_client):
    client, _ = picture_client
    assert client.get("/api/auth/me/picture").status_code == 401
    assert upload(client, {}, image_bytes()).status_code == 401
    assert client.delete("/api/auth/me/picture").status_code == 401


def test_picture_removal_is_account_scoped_repeatable_and_allows_reupload(picture_client):
    client, (first, second) = picture_client
    assert upload(client, first, image_bytes()).status_code == 200
    assert upload(client, second, image_bytes("green")).status_code == 200
    before_first = client.get("/api/auth/me", headers=first).json()
    before_second = client.get("/api/auth/me", headers=second).json()
    second_picture = client.get("/api/auth/me/picture", headers=second).content
    result = client.delete("/api/auth/me/picture", headers=first)
    assert result.status_code == 200, result.text
    assert result.json()["has_profile_picture"] is False
    assert "profile_picture" not in result.json()
    after_first = client.get("/api/auth/me", headers=first).json()
    preserved = set(before_first) - {"has_profile_picture", "profile_picture_url", "updated_at"}
    assert {key: after_first[key] for key in preserved} == {
        key: before_first[key] for key in preserved
    }
    assert client.get("/api/auth/me/picture", headers=first).status_code == 404
    assert client.get("/api/auth/me", headers=second).json() == before_second
    assert client.get("/api/auth/me/picture", headers=second).content == second_picture
    assert client.delete("/api/auth/me/picture", headers=first).status_code == 200
    assert upload(client, first, image_bytes("blue")).status_code == 200
    assert client.get("/api/auth/me/picture", headers=first).status_code == 200


def test_picture_format_must_match_and_dimensions_are_bounded(picture_client):
    client, (headers, _) = picture_client
    result = upload(client, headers, image_bytes(), "image/jpeg")
    assert result.status_code == 415
    oversized = io.BytesIO()
    Image.new("1", (4001, 4000)).save(oversized, format="PNG")
    result = upload(client, headers, oversized.getvalue())
    assert result.status_code == 422
    assert client.get("/api/auth/me/picture", headers=headers).status_code == 404


def test_jpeg_orientation_is_normalized_without_exif(picture_client):
    client, (headers, _) = picture_client
    original = io.BytesIO()
    image = Image.new("RGB", (600, 300), "orange")
    exif = Image.Exif()
    exif[274] = 6
    image.save(original, format="JPEG", exif=exif)
    result = upload(client, headers, original.getvalue(), "image/jpeg")
    assert result.status_code == 200, result.text
    stored = client.get("/api/auth/me/picture", headers=headers)
    with Image.open(io.BytesIO(stored.content)) as picture:
        assert picture.size == (128, 256)
        assert not picture.getexif()
