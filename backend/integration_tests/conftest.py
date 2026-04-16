"""Shared pytest fixtures for this test scope."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "Integration tests are disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
        allow_module_level=True,
    )

if not os.environ.get("DATABASE_URL"):
    pytest.skip("DATABASE_URL must be set for integration tests.", allow_module_level=True)

os.environ.setdefault("SECRET_KEY", "integration-signing-key-material-123456")
os.environ.setdefault("EMAIL_ENABLED", "false")

from app import auth, models  # noqa: E402
from app.api import app  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from fixture_helpers import build_test_helpers  # noqa: E402


def _run_migrations() -> None:
    """Runs the migrations helper path."""
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Ensures schema is satisfied."""
    _run_migrations()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """Implements the db session helper."""
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    """Implements the client helper."""

    def _override_get_db():
        """Implements the override get db helper."""
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def helpers(client, db_session):
    """Implements the helpers helper."""
    return build_test_helpers(
        client=client,
        db_session=db_session,
        auth_module=auth,
        models_module=models,
        include_future_time=False,
    )
