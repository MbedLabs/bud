"""Storage maintenance: ``python -m app.storage migrate --to s3``.

Copies every file in the local upload directory into the configured bucket under the
same storage name, then checks each object's size against the local file. Files
already in the bucket with the right size are skipped, so the command is safe to run
again. The local directory is left untouched; it stays the mirror.
"""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import sys
from pathlib import Path

from app.core.config import settings
from app.services import object_store


async def migrate_to_s3() -> tuple[int, int, list[str]]:
    """Copy the local files to the bucket; returns copied, skipped and mismatches."""
    root = Path(settings.UPLOAD_DIR).resolve()
    copied = skipped = 0
    mismatched: list[str] = []
    for path in sorted(p for p in root.iterdir() if p.is_file() and not p.name.startswith(".")):
        local_size = path.stat().st_size
        if await object_store.size_of(path.name) == local_size:
            skipped += 1
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        await object_store.put_file(path, path.name, content_type)
        if await object_store.size_of(path.name) != local_size:
            mismatched.append(path.name)
        else:
            copied += 1
    return copied, skipped, mismatched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.storage")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate", help="copy the local upload files to S3")
    migrate.add_argument("--to", choices=["s3"], required=True)
    parser.parse_args(argv)
    if not settings.S3_BUCKET:
        print("S3_BUCKET is not set; configure the bucket first.", file=sys.stderr)
        return 2
    copied, skipped, mismatched = asyncio.run(migrate_to_s3())
    print(f"copied {copied}, already there {skipped}, size mismatches {len(mismatched)}")
    for name in mismatched:
        print(f"size mismatch: {name}", file=sys.stderr)
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
