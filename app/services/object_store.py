"""Where run artifacts live: the local directory, or an S3-compatible bucket.

``STORAGE_BACKEND=local`` keeps every file in the local directory, as before. With
``s3`` each file is put in the bucket under ``S3_PREFIX`` plus its storage name (the
name already generated for the local file, so moving an instance is a copy, not a
rename). With ``STORAGE_LOCAL_MIRROR`` the local file is kept as well, and a read
falls back to it, with a warning naming the key, when the bucket does not answer.
boto3 is synchronous, so every call runs in a worker thread.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class StoredObject:
    name: str
    size_bytes: int
    last_modified: datetime


def s3_enabled() -> bool:
    return settings.STORAGE_BACKEND == "s3"


def keeps_local_copy() -> bool:
    """True when the local directory holds the files: local storage, or the mirror."""
    return not s3_enabled() or settings.STORAGE_LOCAL_MIRROR


def object_key(name: str) -> str:
    prefix = settings.S3_PREFIX.strip("/")
    return f"{prefix}/{name}" if prefix else name


def _name_of(key: str) -> str:
    prefix = settings.S3_PREFIX.strip("/")
    return key[len(prefix) + 1 :] if prefix and key.startswith(prefix + "/") else key


@lru_cache(maxsize=1)
def client() -> Any:
    """One S3 client with a bounded connection pool; credentials fall back to the
    ambient AWS chain when no key pair is configured."""
    import boto3
    from botocore.config import Config

    options: dict[str, Any] = {
        "config": Config(max_pool_connections=10, retries={"max_attempts": 3, "mode": "standard"})
    }
    if settings.S3_ENDPOINT_URL:
        options["endpoint_url"] = settings.S3_ENDPOINT_URL
    if settings.S3_REGION:
        options["region_name"] = settings.S3_REGION
    if settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY:
        options["aws_access_key_id"] = settings.S3_ACCESS_KEY_ID
        options["aws_secret_access_key"] = settings.S3_SECRET_ACCESS_KEY
    return boto3.client("s3", **options)


async def put_file(path: Path, name: str, content_type: str) -> None:
    """Upload a local file; large files go up in parts."""
    await asyncio.to_thread(
        client().upload_file,
        str(path),
        settings.S3_BUCKET,
        object_key(name),
        ExtraArgs={"ContentType": content_type},
    )


async def fetch(name: str) -> Any:
    """Open an object for reading; raises when the bucket or the object is missing."""
    response = await asyncio.to_thread(
        client().get_object, Bucket=settings.S3_BUCKET, Key=object_key(name)
    )
    return response["Body"]


def iter_body(body: Any) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks(CHUNK_BYTES)
    finally:
        body.close()


async def delete(name: str) -> None:
    await asyncio.to_thread(client().delete_object, Bucket=settings.S3_BUCKET, Key=object_key(name))


def _list() -> list[StoredObject]:
    prefix = settings.S3_PREFIX.strip("/")
    paginator = client().get_paginator("list_objects_v2")
    found: list[StoredObject] = []
    for page in paginator.paginate(
        Bucket=settings.S3_BUCKET, Prefix=(prefix + "/") if prefix else ""
    ):
        for item in page.get("Contents", []) or []:
            found.append(
                StoredObject(
                    name=_name_of(item["Key"]),
                    size_bytes=int(item.get("Size", 0)),
                    last_modified=item["LastModified"],
                )
            )
    return found


async def list_objects() -> list[StoredObject]:
    """Every object under this instance's prefix."""
    return await asyncio.to_thread(_list)


async def size_of(name: str) -> int | None:
    """The object's size, or None when it does not exist."""

    def head() -> int | None:
        try:
            return int(
                client().head_object(Bucket=settings.S3_BUCKET, Key=object_key(name))[
                    "ContentLength"
                ]
            )
        except client().exceptions.ClientError:
            return None

    return await asyncio.to_thread(head)


async def bucket_answers() -> bool:
    try:
        await asyncio.to_thread(client().head_bucket, Bucket=settings.S3_BUCKET)
        return True
    except Exception as exc:
        logger.warning("Object storage bucket %s did not answer: %s", settings.S3_BUCKET, exc)
        return False
