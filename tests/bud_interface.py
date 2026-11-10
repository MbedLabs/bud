"""
* @file     ${tests/bud_interface.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Interface of Bud's tests: test database, records and app calls.
* @author   Amine El Omari
* @date     2026-11-07
* @version  1.0.0
* @note     Calls run on the interface's own loop against an in-memory database.
"""

import asyncio
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import tests.parameters as params
from app import audit, main
from app.api import test_runs, uploads
from app.api.auth import get_current_active_entity, get_current_user
from app.api.results import get_uploader_entity
from app.core.access import seed_default_access
from app.core.config import settings
from app.db import database as db_module
from app.db.database import Base, get_db
from app.models import AuditEvent, Runner, TestResult, TestRun
from app.models.user import User, UserRole


class BudInterface:

    def setUp(self):
        self.parameters = params
        self.loop = asyncio.new_event_loop()
        self.engine = create_async_engine(self.parameters.DATABASE)
        self._run(self._create_tables())
        self.maker = async_sessionmaker(self.engine, expire_on_commit=False)

    def tearDown(self):
        self.bud_stop_app()
        self._run(self.engine.dispose())
        self.loop.close()

    def bud_start_app(self, signed_in=True):
        """Serve the whole app on a new file-backed SQLite database with the default access seeded
        and its uploads in the same work folder, signed in as an administrator unless signed_in
        is False."""
        self.bud_stop_app()
        folder = (
            Path(os.environ[self.parameters.WORK_DIR_SETTING])
            / self.parameters.APP_DATABASE_FOLDER
            / uuid.uuid4().hex
        )
        folder.mkdir(parents=True)
        settings.UPLOAD_DIR = str(folder / self.parameters.APP_UPLOAD_FOLDER)
        uploads._UPLOAD_ROOT = None
        self.app_engine = create_async_engine(
            f"sqlite+aiosqlite:///{folder / self.parameters.APP_DATABASE_FILE}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        self.app_maker = async_sessionmaker(
            self.app_engine, class_=AsyncSession, expire_on_commit=False
        )
        db_module.engine = self.app_engine
        db_module.async_session_maker = self.app_maker
        self._run(self._create_app_tables())
        self.admin = self._admin()
        main.app.dependency_overrides[get_db] = self._serve_app_session
        if signed_in:
            for dependency in (get_current_user, get_current_active_entity, get_uploader_entity):
                main.app.dependency_overrides[dependency] = self._current_admin
        self.client = TestClient(main.app)
        self.client.__enter__()
        return self.client

    def bud_stop_app(self):
        """Close the app client, clear its overrides and dispose of its database."""
        client = getattr(self, "client", None)
        if client is not None:
            client.__exit__(None, None, None)
            self.client = None
            main.app.dependency_overrides.clear()
        engine = getattr(self, "app_engine", None)
        if engine is not None:
            self._run(engine.dispose())
            self.app_engine = None

    def bud_request(self, method, path, **kwargs):
        """Send one request to the app started by bud_start_app."""
        return self.client.request(method, path, **kwargs)

    def bud_start_log_capture(self, level):
        """Collect every log record from level up until bud_stop_log_capture."""
        self.log_capture = logging.handlers.BufferingHandler(self.parameters.LOG_CAPTURE_CAPACITY)
        self.log_capture.setLevel(level)
        root = logging.getLogger()
        self.log_level = root.level
        root.setLevel(level)
        root.addHandler(self.log_capture)

    def bud_stop_log_capture(self):
        """Stop collecting log records and return the collected ones."""
        root = logging.getLogger()
        root.removeHandler(self.log_capture)
        root.setLevel(self.log_level)
        return list(self.log_capture.buffer)

    def bud_add_to_app(self, row):
        """Store one row in the started app's database and return it as stored."""
        return self._run(self._add_to_app(row))

    def bud_find_in_app(self, model, **where):
        """The rows of a model in the started app's database whose columns equal the given values."""
        return self._run(self._find_in_app(model, where))

    def bud_add_test_station(self):
        """The station the tests act as, with a running test run of its own."""
        station = Runner(
            account=self.parameters.TEST_STATION_ACCOUNT,
            password_hash=self.parameters.TEST_STATION_PASSWORD_HASH,
            token=self.parameters.TEST_STATION_TOKEN,
            socket_port=self.parameters.TEST_STATION_PORT,
        )
        self.station = self._run(self._add_to_app(station))
        run = TestRun(
            name=self.parameters.TEST_STATION_RUN,
            test_case_list=self.parameters.EMPTY_TEST_LIST,
            status=self.parameters.RUN_RUNNING,
            runner_id=self.station.id,
        )
        self.station_run = self._run(self._add_to_app(run))
        return self.station

    def bud_station_request(self, method, url, **kwargs):
        """Send one request signed in as the test station, then sign the client back in."""
        dependencies = (get_current_active_entity, get_uploader_entity)
        previous = {
            dependency: main.app.dependency_overrides.get(dependency) for dependency in dependencies
        }

        async def current_station():
            return self.station

        for dependency in dependencies:
            main.app.dependency_overrides[dependency] = current_station
        try:
            return self.client.request(method, url, **kwargs)
        finally:
            for dependency, override in previous.items():
                if override is None:
                    main.app.dependency_overrides.pop(dependency, None)
                else:
                    main.app.dependency_overrides[dependency] = override

    def bud_station_upload(self, name, content, content_type, **data):
        """Upload one file as the test station to its own run."""
        form = {"run_id": str(self.station_run.id), **data}
        return self.bud_station_request(
            "POST",
            self.parameters.UPLOADS_PATH,
            files={"file": (name, content, content_type)},
            data=form,
        )

    def _admin(self):
        return User(
            id=self.parameters.TEST_ADMIN_ID,
            email=self.parameters.TEST_ADMIN_EMAIL,
            full_name=self.parameters.TEST_ADMIN_NAME,
            hashed_password=self.parameters.TEST_ADMIN_PASSWORD_HASH,
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )

    async def _current_admin(self):
        return self.admin

    async def _create_app_tables(self):
        async with self.app_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.app_maker() as session:
            await seed_default_access(session)
            await session.commit()

    async def _add_to_app(self, row):
        async with self.app_maker() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    async def _find_in_app(self, model, where):
        async with self.app_maker() as session:
            query = select(model).filter_by(**where)
            return list((await session.execute(query)).scalars())

    async def _serve_app_session(self):
        async with self.app_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def bud_read_repository_file(self, relative_path):
        """The text of one file of the repository, by its path from the repository root."""
        return (Path(__file__).resolve().parents[1] / relative_path).read_text()

    def bud_add_audit_event(self, action, age):
        """Record one audit event of a user, the given age ago."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return self._run(
            self._add(
                AuditEvent(
                    actor_type=self.parameters.AUDIT_ACTOR_USER, action=action, occurred_at=now - age
                )
            )
        )

    def bud_prune_audit(self, older_than_days):
        """Run the audit prune command's work on the interface's database."""
        with mock.patch.object(audit, "async_session_maker", self.maker):
            return self._run(audit.prune(older_than_days))

    def bud_audit_actions(self):
        """The actions of the audit events left, in the order they were recorded."""
        return self._run(self._audit_actions())

    def bud_add_station(self, account):
        return self._run(
            self._add(
                Runner(
                    account=account,
                    password_hash=self.parameters.STATION_PASSWORD_HASH,
                    token=self.parameters.STATION_TOKEN,
                )
            )
        )

    def bud_add_run(self, suite, station_id, created_at, test_classes, outcomes):
        return self._run(self._add_run(suite, station_id, created_at, test_classes, outcomes))

    def bud_start_api(self):
        admin = User(
            id=self.parameters.ADMIN_ID,
            email=self.parameters.ADMIN_EMAIL,
            full_name=self.parameters.ADMIN_EMAIL,
            hashed_password=self.parameters.ADMIN_EMAIL,
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )

        async def current_admin():
            return admin

        app = FastAPI()
        app.include_router(test_runs.router, prefix=self.parameters.TEST_RUNS_PREFIX)
        app.dependency_overrides[get_db] = self._serve_session
        app.dependency_overrides[get_current_active_entity] = current_admin
        self.api = app

    def bud_get_stats(self, **filters):
        return self._run(self._get(self.parameters.STATS_PATH, filters))

    def _run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    async def _create_tables(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def _audit_actions(self):
        async with self.maker() as db:
            events = await db.execute(select(AuditEvent).order_by(AuditEvent.id))
            return [event.action for event in events.scalars()]

    async def _add(self, row):
        async with self.maker() as db:
            db.add(row)
            await db.commit()
            return row.id

    async def _add_run(self, suite, station_id, created_at, test_classes, outcomes):
        counts = {
            outcome: outcomes.count(outcome)
            for outcome in (self.parameters.PASSED, self.parameters.FAILED, self.parameters.SKIPPED)
        }
        async with self.maker() as db:
            run = TestRun(
                name=suite,
                test_case_list=suite,
                status=self.parameters.RUN_COMPLETED,
                total_tests=len(outcomes),
                passed_tests=counts[self.parameters.PASSED],
                failed_tests=counts[self.parameters.FAILED],
                skipped_tests=counts[self.parameters.SKIPPED],
                created_at=created_at,
                runner_id=station_id,
            )
            db.add(run)
            await db.flush()
            for test_class, outcome in zip(test_classes, outcomes):
                for method in range(self.parameters.METHODS_PER_CLASS):
                    db.add(self._result(run.id, test_class, method, outcome))
            await db.commit()
            return run.id

    def _result(self, run_id, test_class, method, outcome):
        failing_method = outcome == self.parameters.FAILED and method == 0
        skipped = outcome == self.parameters.SKIPPED
        return TestResult(
            test_run_id=run_id,
            test_class=test_class,
            test_method=f"bud_step_{method}",
            passed=not (failing_method or skipped),
            test_metadata={"skipped": True} if skipped else {},
        )

    async def _serve_session(self):
        async with self.maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _get(self, path, query):
        transport = httpx.ASGITransport(app=self.api)
        async with httpx.AsyncClient(
            transport=transport, base_url=self.parameters.API_BASE
        ) as client:
            return await client.get(self.parameters.TEST_RUNS_PREFIX + path, params=query)
