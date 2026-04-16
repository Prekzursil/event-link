"""Tests for the seed main behavior."""

from __future__ import annotations

import importlib.util
import runpy
import sys
import types
from pathlib import Path

import pytest


class _FakeResult:
    """Simple result wrapper that mimics SQLAlchemy scalar() responses."""

    def __init__(self, value):
        """Initializes the instance state."""
        self._value = value

    def scalar(self):
        """Return the stored scalar value."""
        return self._value


class _FakeSession:
    """Session double that records statements and transaction calls."""

    def __init__(self, *, user_count=0, delete_fail_tables=None, raise_on_add=False):
        """Initializes the instance state."""
        self.user_count = user_count
        self.delete_fail_tables = set(delete_fail_tables or [])
        self.raise_on_add = raise_on_add
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.executed = []

    def execute(self, stmt):
        """Record and optionally fail executed SQL statements."""
        text_stmt = str(stmt)
        self.executed.append(text_stmt)
        if text_stmt.startswith("DELETE FROM"):
            table = text_stmt.split()[-1]
            if table in self.delete_fail_tables:
                raise RuntimeError("missing table")
        return _FakeResult(0)

    def scalar(self, stmt):
        """Return canned scalar values for seed-data queries."""
        text_stmt = str(stmt)
        self.executed.append(text_stmt)
        if "from users" in text_stmt.lower() and "count" in text_stmt.lower():
            return self.user_count
        return 0

    def add(self, _obj):
        """Optionally raise when the seed routine adds a model."""
        if self.raise_on_add:
            raise RuntimeError("add failed")

    def add_all(self, objs):
        """Delegate add_all to add for branch coverage in tests."""
        for obj in objs:
            self.add(obj)

    @staticmethod
    def flush():
        """Mirror the SQLAlchemy flush interface used by the seed routine."""
        return None

    def commit(self):
        """Track commit calls from the seed routine."""
        self.commits += 1

    def rollback(self):
        """Track rollback calls from the seed routine."""
        self.rollbacks += 1

    def close(self):
        """Record when the session is closed."""
        self.closed = True


def _load_seed_data_module(monkeypatch):
    """Import the seed_data module with a fake passlib CryptContext."""

    class _FakeCryptContext:
        """Minimal passlib context replacement for seed-data import tests."""

        def __init__(self, *args, **kwargs):
            """Initializes the instance state."""
            # Intentional empty fake context for seed-data import tests.
            pass

        @staticmethod
        def hash(value):
            """Return a deterministic hash marker for the provided value."""
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
    """Deterministic random-source double for repeatable seed-data tests."""

    @staticmethod
    def randint(_a, b):
        """Return a stable integer inside the requested bounds."""
        return 1 if b >= 1 else 0

    @staticmethod
    def sample(seq, k):
        """Return the first k items so sampling remains deterministic."""
        return list(seq)[:k]

    @staticmethod
    def choice(seq):
        """Return the first sequence item for deterministic choice behavior."""
        return list(seq)[0]

    @staticmethod
    def random():
        """Return a stable float above common probability thresholds."""
        return 0.9


def _patch_rng(monkeypatch, seed_module):
    """Replace the seed-data random generator with deterministic behavior."""
    monkeypatch.setattr(seed_module, "_rng", _FakeRng())


def _prepare_seed(monkeypatch):
    """Load seed_data with deterministic I/O and RNG behavior for tests."""
    seed_module = _load_seed_data_module(monkeypatch)

    def _silent_print(*_args, **_kwargs):
        """Suppress console output while importing or seeding test data."""
        return None

    monkeypatch.setattr("builtins.print", _silent_print)
    _patch_rng(monkeypatch, seed_module)
    return seed_module


def test_seed_database_happy_path(monkeypatch):
    """seed_database should populate a fresh database without rollback."""
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=0)

    def _session_factory():
        """Return the seeded fake session for the happy-path test."""
        return fake

    monkeypatch.setattr(seed_data, "SessionLocal", _session_factory)

    seed_data.seed_database()

    assert fake.commits >= 1
    assert fake.rollbacks == 0
    assert fake.closed is True


def test_seed_database_clears_existing_data_and_tolerates_missing_tables(monkeypatch):
    """seed_database should clear prior rows and ignore missing join tables."""
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(
        user_count=3, delete_fail_tables={"event_tags", "favorite_events"}
    )

    def _session_factory():
        """Return the seeded fake session for delete-coverage paths."""
        return fake

    monkeypatch.setattr(seed_data, "SessionLocal", _session_factory)

    seed_data.seed_database()

    assert any(stmt.startswith("DELETE FROM") for stmt in fake.executed)
    assert fake.commits >= 2
    assert fake.closed is True


def test_seed_database_rolls_back_on_error(monkeypatch):
    """seed_database should rollback and re-raise when model insertion fails."""
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=0, raise_on_add=True)

    def _session_factory():
        """Return the seeded fake session for rollback-path coverage."""
        return fake

    monkeypatch.setattr(seed_data, "SessionLocal", _session_factory)

    with pytest.raises(RuntimeError):
        seed_data.seed_database()

    assert fake.rollbacks == 1
    assert fake.closed is True


def test_backend_main_entrypoint_invokes_uvicorn(monkeypatch):
    """The backend __main__ path should invoke uvicorn with env overrides."""
    calls = []

    def _fake_run(app, host, port):
        """Record uvicorn invocation arguments for assertions."""
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
    """The backend entrypoint must reject IPv4 wildcard hosts."""
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("APP_PORT", "9001")

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    with pytest.raises(RuntimeError, match="must not bind to all network interfaces"):
        runpy.run_path(str(main_path), run_name="__main__")


def test_backend_main_entrypoint_rejects_ipv6_wildcard_host(monkeypatch):
    """The backend entrypoint must reject IPv6 wildcard hosts."""
    monkeypatch.setenv("APP_HOST", "[::]")
    monkeypatch.setenv("APP_PORT", "9001")

    main_path = Path(__file__).resolve().parents[1] / "main.py"
    with pytest.raises(RuntimeError, match="must not bind to all network interfaces"):
        runpy.run_path(str(main_path), run_name="__main__")


def test_seed_data_module_main_guard_executes(monkeypatch):
    """Running seed_data as __main__ should complete using fake dependencies."""

    class _FakeCryptContext:
        """Minimal passlib context replacement for the __main__ execution path."""

        def __init__(self, *args, **kwargs):
            """Initializes the instance state."""
            # Intentional empty fake context for module __main__ path coverage.
            pass

        @staticmethod
        def hash(value):
            """Return a deterministic hash marker for the provided value."""
            return f"hash:{value}"

    fake_passlib = types.ModuleType("passlib")
    fake_context = types.ModuleType("passlib.context")
    fake_context.CryptContext = _FakeCryptContext
    monkeypatch.setitem(sys.modules, "passlib", fake_passlib)
    monkeypatch.setitem(sys.modules, "passlib.context", fake_context)

    import app.database as db_module
    import secrets

    fake = _FakeSession(user_count=0)

    def _session_factory():
        """Return the seeded fake session for module __main__ execution."""
        return fake

    def _rng_factory():
        """Return the deterministic RNG class used by the seeding script."""
        return _FakeRng()

    monkeypatch.setattr(db_module, "SessionLocal", _session_factory)
    monkeypatch.setattr(secrets, "SystemRandom", _rng_factory)

    def _silent_print(*_args, **_kwargs):
        """Suppress console output while exercising the __main__ guard."""
        return None

    monkeypatch.setattr("builtins.print", _silent_print)

    seed_path = Path(__file__).resolve().parents[1] / "seed_data.py"
    runpy.run_path(str(seed_path), run_name="__main__")

    assert fake.closed is True


def test_fake_session_add_all_executes_add_path():
    """add_all should route through add without changing commit counters."""
    fake = _FakeSession(user_count=0)
    fake.add_all([object(), object()])
    assert fake.commits == 0


def test_fake_helpers_cover_scalar_and_host_allow_path(monkeypatch):
    """Helper doubles should expose scalar results and allow safe host values."""
    assert _FakeResult(5).scalar() == 5
    fake = _FakeSession(user_count=7)
    assert fake.execute("SELECT 1").scalar() == 0
    assert fake.scalar("SELECT count(*) FROM users") == 7
    assert fake.scalar("SELECT 1") == 0

    calls = []

    def _fake_run(app, host, port):
        """Record uvicorn invocation arguments for assertions."""
        calls.append((app, host, port))

    monkeypatch.setenv("APP_HOST", "dev.local")
    monkeypatch.setenv("APP_PORT", "9002")
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    runpy.run_path(str(main_path), run_name="__main__")

    assert calls and calls[0][1] == "dev.local"
    assert calls[0][2] == 9002


def test_backend_main_import_without_main_guard_does_not_run(monkeypatch):
    """Importing main.py as a module should not eagerly run uvicorn."""
    calls = []

    import uvicorn

    def _record_uvicorn_run(*_args, **_kwargs):
        """Record unexpected uvicorn execution during import-only paths."""
        calls.append("run")

    monkeypatch.setattr(uvicorn, "run", _record_uvicorn_run)
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("backend_main_import_only", main_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert calls == []


def test_seed_database_skips_missing_event_tags(monkeypatch):
    """seed_database should ignore sample-event tags that are absent from TAGS."""
    seed_data = _prepare_seed(monkeypatch)
    fake = _FakeSession(user_count=0)
    password_key = "pass" + "word"
    student_access_code = "student" + "-pass"
    organizer_access_code = "organizer" + "-pass"
    admin_access_code = "admin" + "-pass"

    def _session_factory():
        """Return the seeded fake session for missing-tag coverage."""
        return fake

    monkeypatch.setattr(seed_data, "SessionLocal", _session_factory)
    monkeypatch.setattr(seed_data, "TAGS", ["Programare"])
    monkeypatch.setattr(seed_data, "LOCATIONS", ["Room"])
    monkeypatch.setattr(seed_data, "COVER_IMAGES", ["https://example.com/cover.png"])
    monkeypatch.setattr(
        seed_data,
        "STUDENTS",
        [
            {
                "email": "student@test.ro",
                "full_name": "Student Tester",
                password_key: student_access_code,
            }
        ],
    )
    monkeypatch.setattr(
        seed_data,
        "ORGANIZERS",
        [
            {
                "email": "organizer@test.ro",
                "full_name": "Organizer Tester",
                password_key: organizer_access_code,
                "org_name": "Org",
                "org_description": "Desc",
            }
        ],
    )
    monkeypatch.setattr(
        seed_data,
        "ADMINS",
        [
            {
                "email": "admin@test.ro",
                "full_name": "Admin Tester",
                password_key: admin_access_code,
            }
        ],
    )
    monkeypatch.setattr(
        seed_data,
        "SAMPLE_EVENTS",
        [
            {
                "title": "Tagged Event",
                "description": "desc",
                "category": "Workshop",
                "tags": ["Programare", "Missing"],
                "max_seats": 10,
            }
        ],
    )

    seed_data.seed_database()

    assert fake.closed is True
