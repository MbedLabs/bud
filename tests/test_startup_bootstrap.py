from __future__ import annotations

import pytest

from app import main as main_module


@pytest.mark.asyncio
async def test_lifespan_skips_legacy_bootstrap_when_startup_repair_disabled(monkeypatch):
    calls: list[str] = []

    async def fake_create_tables():
        calls.append("create_tables")

    async def fake_migrate_user_columns():
        calls.append("migrate_user_columns")

    async def fake_migrate_user_roles_to_viewer():
        calls.append("migrate_user_roles_to_viewer")

    async def fake_migrate_execution_columns():
        calls.append("migrate_execution_columns")

    async def fake_seed_admin_user():
        calls.append("seed_admin_user")

    monkeypatch.setattr(main_module.app_settings, "RUN_STARTUP_DATA_REPAIR", False)
    monkeypatch.setattr(main_module.db, "create_tables", fake_create_tables)
    monkeypatch.setattr(main_module, "migrate_user_columns", fake_migrate_user_columns)
    monkeypatch.setattr(
        main_module, "migrate_user_roles_to_viewer", fake_migrate_user_roles_to_viewer
    )
    monkeypatch.setattr(main_module, "migrate_execution_columns", fake_migrate_execution_columns)
    monkeypatch.setattr(main_module, "seed_admin_user", fake_seed_admin_user)

    async with main_module.lifespan(main_module.app):
        pass

    assert calls == []


@pytest.mark.asyncio
async def test_lifespan_runs_legacy_bootstrap_when_startup_repair_enabled(monkeypatch):
    calls: list[str] = []

    async def fake_create_tables():
        calls.append("create_tables")

    async def fake_migrate_user_columns():
        calls.append("migrate_user_columns")

    async def fake_migrate_user_roles_to_viewer():
        calls.append("migrate_user_roles_to_viewer")

    async def fake_migrate_execution_columns():
        calls.append("migrate_execution_columns")

    async def fake_seed_admin_user():
        calls.append("seed_admin_user")

    monkeypatch.setattr(main_module.app_settings, "RUN_STARTUP_DATA_REPAIR", True)
    monkeypatch.setattr(main_module.db, "create_tables", fake_create_tables)
    monkeypatch.setattr(main_module, "migrate_user_columns", fake_migrate_user_columns)
    monkeypatch.setattr(
        main_module, "migrate_user_roles_to_viewer", fake_migrate_user_roles_to_viewer
    )
    monkeypatch.setattr(main_module, "migrate_execution_columns", fake_migrate_execution_columns)
    monkeypatch.setattr(main_module, "seed_admin_user", fake_seed_admin_user)

    async with main_module.lifespan(main_module.app):
        pass

    assert calls == [
        "create_tables",
        "migrate_user_columns",
        "migrate_user_roles_to_viewer",
        "migrate_execution_columns",
        "seed_admin_user",
    ]
