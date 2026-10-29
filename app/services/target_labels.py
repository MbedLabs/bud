"""Names for the objects that audit events and access requests refer to by id.

Ids are collected first and resolved with one query per kind. A kind listed in ``KINDS``
answers the object's name when it exists and ``deleted`` when it is deleted; any
other kind, and an id that is not a positive integer within the database's integer range,
answers nothing. Stored rows are never changed.
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AccessGroup,
    Artifact,
    NotificationChannel,
    Policy,
    Product,
    Runner,
    RunnerApiKey,
    TestResult,
    TestRun,
    User,
)


@dataclass(frozen=True)
class Kind:
    """A model whose rows are named by ``name`` and looked up by integer id."""

    model: Any
    name: Callable[[Any], str]


KINDS: dict[str, Kind] = {
    "run": Kind(TestRun, lambda row: row.name),
    "product": Kind(Product, lambda row: row.name),
    "station": Kind(Runner, lambda row: row.account),
    "user": Kind(User, lambda row: row.full_name),
    "group": Kind(AccessGroup, lambda row: row.name),
    "policy": Kind(Policy, lambda row: row.name),
    "enrolment_key": Kind(RunnerApiKey, lambda row: row.label),
    "channel": Kind(NotificationChannel, lambda row: row.name),
    "artifact": Kind(Artifact, lambda row: row.original_filename),
    "result": Kind(TestResult, lambda row: f"{row.test_class}.{row.test_method}"),
}

TARGET_KINDS: dict[str, str] = {
    "test_run": "run",
    "run": "run",
    "target_run": "run",
    "test-run": "run",
    "publish-to-bloom": "run",
    "product": "product",
    "station": "station",
    "runner": "station",
    "user": "user",
    "group": "group",
    "policy": "policy",
    "enrolment_key": "enrolment_key",
    "key": "enrolment_key",
    "notification_channel": "channel",
    "channel": "channel",
    "artifact": "artifact",
    "result": "result",
}

CREATED_KINDS: dict[str, str] = {
    "/api/users": "user",
    "/api/groups": "group",
    "/api/groups/{group_id}/duplicate": "group",
    "/api/groups/{group_id}/members": "group",
    "/api/policies": "policy",
    "/api/policies/{policy_id}/duplicate": "policy",
    "/api/products": "product",
    "/api/test-runs": "run",
    "/api/uploads": "artifact",
    "/api/runners/api-keys": "enrolment_key",
    "/api/settings/notifications/channels": "channel",
}

MAX_ID = 2**31 - 1
ID_PATTERN = re.compile(r"[0-9]{1,10}")


@dataclass(frozen=True)
class Label:
    """The object's name, or ``deleted`` when no object has that id any more."""

    name: Optional[str] = None
    deleted: bool = False


class LabelResolver:
    """Collects ``(kind, id)`` pairs, loads their names, then answers each pair."""

    def __init__(self) -> None:
        self._wanted: dict[str, set[int]] = {}
        self._names: dict[str, dict[int, str]] = {}

    @staticmethod
    def _key(kind: Optional[str], ref: Any) -> Optional[tuple[str, int]]:
        if kind not in KINDS or ref is None or isinstance(ref, bool):
            return None
        text = str(ref)
        if not ID_PATTERN.fullmatch(text) or int(text) > MAX_ID:
            return None
        return kind, int(text)

    def want(self, kind: Optional[str], ref: Any) -> None:
        """Remember that the name of ``kind`` ``ref`` is needed."""
        key = self._key(kind, ref)
        if key is not None:
            self._wanted.setdefault(key[0], set()).add(key[1])

    async def load(self, db: AsyncSession) -> None:
        """Read the names of every remembered id, one query per kind."""
        for kind, ids in self._wanted.items():
            spec = KINDS[kind]
            rows = (await db.execute(select(spec.model).where(spec.model.id.in_(ids)))).scalars()
            self._names[kind] = {row.id: spec.name(row) for row in rows}

    def get(self, kind: Optional[str], ref: Any) -> Label:
        """The name of ``kind`` ``ref``, ``deleted`` when it is gone, or an empty label."""
        key = self._key(kind, ref)
        if key is None or key[0] not in self._names:
            return Label()
        name = self._names[key[0]].get(key[1])
        return Label(name=name) if name is not None else Label(deleted=True)


def target_kind(target_type: Optional[str]) -> Optional[str]:
    """The kind of an audit target or access request type, or None when it has no name."""
    return TARGET_KINDS.get(target_type or "")


def created_kind(route: Any) -> Optional[str]:
    """The kind of the object a ``201`` answer of this route template created."""
    return CREATED_KINDS.get(route) if isinstance(route, str) else None
