"""Shared pytest fixtures for this test scope."""
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"event-link-pytest-{os.getpid()}.db"
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"

os.environ.setdefault("SECRET_KEY", "test-signing-key-material-123456")
os.environ.setdefault("EMAIL_ENABLED", "false")

from app import api as api_module  # noqa: E402
from app import auth, models  # noqa: E402
from app.api import app  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from fixture_helpers import build_test_helpers  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Ensures schema is satisfied."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink(missing_ok=True)


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

    api_module._RATE_LIMIT_STORE.clear()
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
    )
