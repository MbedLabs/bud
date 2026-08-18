"""What Bud knows can be run, and on which bench.

Bud does not read the test workspace - the benches do. What Bud has is the
record of what has already executed: every result carries the class that ran and
the file it came from, and the run it belongs to names the bench. That is enough
to answer the only question a custom run needs answered, which is "where can
this test case run", and it is answered from evidence rather than from a
declaration someone has to keep up to date.

The consequence is worth stating plainly: a test case Bud has never seen cannot
be selected. There is no way to guess which bench holds it, and queueing it
against the wrong one would fail on the bench, minutes later, for a reason the
reader could not have predicted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePath
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Runner, TestResult, TestRun


@dataclass
class CatalogEntry:
    """One test case, and everywhere it has been seen to run."""

    test_path: str
    test_class: str
    suite: str
    runner_accounts: list[str] = field(default_factory=list)
    method_count: int = 0
    last_run_at: Optional[datetime] = None
    last_passed: Optional[bool] = None
    last_run_id: Optional[int] = None


def derive_test_path(test_case_file: Optional[str], test_class: Optional[str]) -> Optional[str]:
    """The importable `module.Class` path for a result, or None if it has none.

    `test_case_file` is `inspect.getsourcefile()` on the bench, so an absolute
    path in the bench's own workspace. The runner's loader takes `module.Class`
    and imports the module with the workspace on `sys.path`, so the module is
    the file's stem - which is the same shape as the entries in the pre-declared
    lists the runner already resolves.

    A result recorded without the file (an older upload, or a runner that did
    not report it) yields None: the class name alone is not importable, and
    guessing a module from it would produce a run that fails on the bench.
    """
    if not test_class:
        return None
    if not test_case_file:
        return None
    stem = PurePath(test_case_file).stem
    if not stem or stem == test_class:
        return None
    return f"{stem}.{test_class}"


async def build_catalog(
    db: AsyncSession,
    *,
    runner_account: Optional[str] = None,
    suite: Optional[str] = None,
) -> list[CatalogEntry]:
    """Every test case Bud has a record of, newest evidence winning.

    One query over results joined to their run, folded in Python: the fold needs
    the derived module path, which is a string operation on a JSON field and not
    something to express in SQL across two dialects.
    """
    query = (
        select(
            TestResult.test_class,
            TestResult.test_method,
            TestResult.test_metadata,
            TestResult.passed,
            TestResult.created_at,
            TestRun.id.label("run_id"),
            TestRun.name.label("suite"),
            Runner.account.label("runner_account"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .outerjoin(Runner, TestRun.runner_id == Runner.id)
        .order_by(TestResult.created_at)
    )
    if runner_account:
        query = query.where(Runner.account == runner_account)
    if suite:
        query = query.where(TestRun.name == suite)

    entries: dict[str, CatalogEntry] = {}
    methods: dict[str, set[str]] = {}

    for row in (await db.execute(query)).all():
        metadata = row.test_metadata or {}
        test_class = metadata.get("test_case_class") or row.test_class
        test_path = derive_test_path(metadata.get("test_case_file"), test_class)
        if test_path is None:
            continue

        entry = entries.get(test_path)
        if entry is None:
            entry = CatalogEntry(test_path=test_path, test_class=test_class, suite=row.suite)
            entries[test_path] = entry
            methods[test_path] = set()

        # Ordered oldest first, so the last row seen is the most recent - the
        # suite and outcome a reader would expect to see against it.
        entry.suite = row.suite
        entry.last_run_at = row.created_at
        entry.last_passed = row.passed
        entry.last_run_id = row.run_id
        if row.runner_account and row.runner_account not in entry.runner_accounts:
            entry.runner_accounts.append(row.runner_account)
        methods[test_path].add(row.test_method)

    for test_path, entry in entries.items():
        entry.method_count = len(methods[test_path])

    return sorted(entries.values(), key=lambda e: (e.suite.lower(), e.test_path.lower()))


@dataclass
class Assignment:
    """A selection resolved to the bench that will run it."""

    runner_account: str
    runner_id: int
    test_paths: list[str]


@dataclass
class Unassigned:
    test_path: str
    reason: str


@dataclass
class Plan:
    assignments: list[Assignment]
    unassigned: list[Unassigned]


def plan_custom_run(
    catalog: list[CatalogEntry],
    requested: list[str],
    *,
    runner_ids: dict[str, int],
    pinned_runner: Optional[str] = None,
) -> Plan:
    """Work out which bench runs what, before anything is written.

    A test case runs where it has run before. A selection that spans two benches
    is therefore two runs, not one refusal - the alternative is telling someone
    who picked five sensible tests that they may not have them, which is a worse
    answer than "this became two runs, here they are".

    Pinning a runner narrows it to one bench and reports whatever that bench has
    never run, rather than quietly moving those tests somewhere else.
    """
    known = {entry.test_path: entry for entry in catalog}
    grouped: dict[str, list[str]] = {}
    unassigned: list[Unassigned] = []
    undecided: list[tuple[str, list[str]]] = []

    for test_path in requested:
        entry = known.get(test_path)
        if entry is None:
            unassigned.append(
                Unassigned(
                    test_path=test_path,
                    reason="Bud has no record of this test case running anywhere.",
                )
            )
            continue

        available = [account for account in entry.runner_accounts if account in runner_ids]
        if not available:
            unassigned.append(
                Unassigned(
                    test_path=test_path,
                    reason="The Test Station this ran on is no longer registered.",
                )
            )
            continue

        if pinned_runner:
            if pinned_runner not in available:
                unassigned.append(
                    Unassigned(
                        test_path=test_path,
                        reason=f"Has not run on {pinned_runner}; it has run on "
                        f"{', '.join(available)}.",
                    )
                )
                continue
            grouped.setdefault(pinned_runner, []).append(test_path)
            continue

        if len(available) == 1:
            # Forced: there is one bench that has ever run this.
            grouped.setdefault(available[0], []).append(test_path)
        else:
            undecided.append((test_path, available))

    # Placed second, and deliberately: a test case that could run on either
    # bench should follow the ones that had no choice, rather than splitting the
    # selection into two runs for no reason. Only when nothing is forced does the
    # most recent bench win - it is the one whose workspace most likely still
    # holds the case.
    for test_path, available in undecided:
        already_used = [account for account in available if account in grouped]
        chosen = already_used[-1] if already_used else available[-1]
        grouped.setdefault(chosen, []).append(test_path)

    assignments = [
        Assignment(runner_account=account, runner_id=runner_ids[account], test_paths=paths)
        for account, paths in sorted(grouped.items())
    ]
    return Plan(assignments=assignments, unassigned=unassigned)
