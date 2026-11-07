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

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import tests.parameters as params
from app.api import test_runs
from app.api.auth import get_current_active_entity
from app.db.database import Base, get_db
from app.models import Runner, TestResult, TestRun
from app.models.user import User, UserRole


class BudInterface:

    def setUp(self):
        self.parameters = params
        self.loop = asyncio.new_event_loop()
        self.engine = create_async_engine(self.parameters.DATABASE)
        self._run(self._create_tables())
        self.maker = async_sessionmaker(self.engine, expire_on_commit=False)

    def tearDown(self):
        self._run(self.engine.dispose())
        self.loop.close()

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
