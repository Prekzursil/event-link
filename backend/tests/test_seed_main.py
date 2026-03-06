from __future__ import annotations

import importlib.util
import runpy
import sys
import types
from pathlib import Path

import pytest


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeSession:
    def __init__(self, *, user_count=0, delete_fail_tables=None, raise_on_add=False):
        self.user_count = user_count
        self.delete_fail_tables = set(delete_fail_tables or [])
        self.raise_on_add = raise_on_add
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.executed = []

    def execute(self, stmt):
        text_stmt = str(stmt)
        self.executed.append(text_stmt)
        if text_stmt.startswith("DELETE FROM"):
            table = text_stmt.split()[-1]
            if table in self.delete_fail_tables:
                raise RuntimeError("missing table")
        return _FakeResult(0)

    def scalar(self, stmt):
        text_stmt = str(stmt)
        self.executed.append(text_stmt)
        if "from users" in text_stmt.lower() and "count" in text_stmt.lower():
            return self.user_count
        return 0

    def add(self, _obj):
        if self.raise_on_add:
            raise RuntimeError("add failed")

    def add_all(self, objs):
        for obj in objs:
            self.add(obj)

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _load_seed_data_module(monkeypatch):
    class _FakeCryptContext:
        def __init__(self, *args, **kwargs):
            # Intentional empty fake context for seed-data import tests.
            return None

        def hash(self, value):
            return f"hash:{value}"

    fake_passlib = types.ModuleType("passlib")
    fake_context = types.ModuleType("passlib.context")
    fake_context.CryptContext = _FakeCryptContext

    monkeypatch.setitem(sys.modules, "passlib", fake_passlib)
    monkeypatch.setitem(sys.modules, "passlib.context", fake_context)

    seed_path = Path(__file__).resolve().parents[1] / "seed_data.py"
    spec = importlib.util.spec_from_file_location("seed_data", seed_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeRng:
    @staticmethod
    def randint(_a, b):
        return 1 if b >= 1 else 0

    @staticmethod
    def sample(seq, k):
        return list(seq)[:k]

    @staticmethod
    def choice(seq):
        return list(seq)[0]

    @staticmethod
    def random():
        return 0.9


def _patch_rng(monkeypatch, seed_module):
    monkeypatch.setattr(seed_module, "_rng", _FakeRng())


def _prepare_seed(monkeypatch):
    seed_module = _load_seed_data_module(monkeypatch)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)
    _patch_rng(monkeypatch, seed_module)
    return seed_module


def test_seed_database_happy_path(monkeypatch):
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=0)
    monkeypatch.setattr(seed_data, "SessionLocal", lambda: fake)

    seed_data.seed_database()

    assert fake.commits >= 1
    assert fake.rollbacks == 0
    assert fake.closed is True


def test_seed_database_clears_existing_data_and_tolerates_missing_tables(monkeypatch):
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=3, delete_fail_tables={"event_tags", "favorite_events"})
    monkeypatch.setattr(seed_data, "SessionLocal", lambda: fake)

    seed_data.seed_database()

    assert any(stmt.startswith("DELETE FROM") for stmt in fake.executed)
    assert fake.commits >= 2
    assert fake.closed is True


def test_seed_database_rolls_back_on_error(monkeypatch):
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=0, raise_on_add=True)
    monkeypatch.setattr(seed_data, "SessionLocal", lambda: fake)

    with pytest.raises(RuntimeError):
        seed_data.seed_database()

    assert fake.rollbacks == 1
    assert fake.closed is True


def test_backend_main_entrypoint_invokes_uvicorn(monkeypatch):
    calls = []

    def _fake_run(app, host, port):
        calls.append((app, host, port))

    monkeypatch.setenv("APP_HOST", "")
    monkeypatch.setenv("APP_PORT", "9001")
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _fake_run)

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    runpy.run_path(str(main_path), run_name="__main__")

    assert calls and calls[0][1] == "127.0.0.1"
    assert calls[0][2] == 9001



def test_backend_main_entrypoint_rejects_wildcard_host(monkeypatch):
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "9001")

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    with pytest.raises(RuntimeError, match="must not bind to all network interfaces"):
        runpy.run_path(str(main_path), run_name="__main__")


def test_backend_main_entrypoint_rejects_ipv6_wildcard_host(monkeypatch):
    monkeypatch.setenv("APP_HOST", "[::]")
    monkeypatch.setenv("APP_PORT", "9001")

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    with pytest.raises(RuntimeError, match="must not bind to all network interfaces"):
        runpy.run_path(str(main_path), run_name="__main__")


def test_seed_data_module_main_guard_executes(monkeypatch):
    class _FakeCryptContext:
        def __init__(self, *args, **kwargs):
            # Intentional empty fake context for module __main__ path coverage.
            return None

        def hash(self, value):
            return f"hash:{value}"

    fake_passlib = types.ModuleType("passlib")
    fake_context = types.ModuleType("passlib.context")
    fake_context.CryptContext = _FakeCryptContext
    monkeypatch.setitem(sys.modules, "passlib", fake_passlib)
    monkeypatch.setitem(sys.modules, "passlib.context", fake_context)

    import app.database as db_module
    import secrets

    fake = _FakeSession(user_count=0)
    monkeypatch.setattr(db_module, "SessionLocal", lambda: fake)
    monkeypatch.setattr(secrets, "SystemRandom", lambda: _FakeRng())
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)

    seed_path = Path(__file__).resolve().parents[1] / "seed_data.py"
    runpy.run_path(str(seed_path), run_name="__main__")

    assert fake.closed is True


def test_fake_session_add_all_executes_add_path():
    fake = _FakeSession(user_count=0)
    fake.add_all([object(), object()])
    assert fake.commits == 0


def test_fake_helpers_cover_scalar_and_host_allow_path(monkeypatch):
    assert _FakeResult(5).scalar() == 5
    fake = _FakeSession(user_count=7)
    assert fake.scalar("SELECT count(*) FROM users") == 7
    assert fake.scalar("SELECT 1") == 0

    calls = []

    def _fake_run(app, host, port):
        calls.append((app, host, port))

    monkeypatch.setenv("APP_HOST", "dev.local")
    monkeypatch.setenv("APP_PORT", "9002")
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    runpy.run_path(str(main_path), run_name="__main__")

    assert calls and calls[0][1] == "dev.local"
    assert calls[0][2] == 9002
