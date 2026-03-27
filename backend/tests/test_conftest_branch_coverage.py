from __future__ import annotations

import importlib.util
import os
import uuid
from pathlib import Path

import pytest


def _load_conftest_module():
    path = Path(__file__).with_name("conftest.py")
    module_name = f"backend_tests_conftest_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_conftest_preserves_existing_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///already-set.db")
    module = _load_conftest_module()
    assert os.environ["DATABASE_URL"] == "sqlite:///already-set.db"
    assert "sqlite:///already-set.db" in str(module.os.environ["DATABASE_URL"])


def test_ensure_schema_teardown_skips_missing_temp_db(monkeypatch, tmp_path):
    module = _load_conftest_module()
    calls: list[str] = []

    monkeypatch.setattr(module.Base.metadata, "drop_all", lambda **_kwargs: calls.append("drop"))
    monkeypatch.setattr(module.Base.metadata, "create_all", lambda **_kwargs: calls.append("create"))
    monkeypatch.setattr(module.engine, "dispose", lambda: calls.append("dispose"))
    monkeypatch.setattr(module, "_TEST_DB_PATH", tmp_path / "missing-test-db.sqlite3")

    generator = module._ensure_schema.__wrapped__()
    next(generator)
    with pytest.raises(StopIteration):
        next(generator)

    assert calls == ["drop", "create", "drop", "dispose"]
