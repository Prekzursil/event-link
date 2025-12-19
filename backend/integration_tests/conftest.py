import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text


if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
    pytest.skip(
        "Integration tests are disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
        allow_module_level=True,
    )

if not os.environ.get("DATABASE_URL"):
    pytest.skip("DATABASE_URL must be set for integration tests.", allow_module_level=True)

os.environ.setdefault("SECRET_KEY", "integration-test-secret")
os.environ.setdefault("EMAIL_ENABLED", "false")

from app import auth, models  # noqa: E402
from app.api import app  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402


def _run_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    _run_migrations()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        tables = [t.name for t in Base.metadata.sorted_tables]
        if tables:
            db.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
            db.commit()
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def helpers(client, db_session):
    def register_student(email: str) -> str:
        resp = client.post(
            "/register",
            json={"email": email, "password": "password123", "confirm_password": "password123"},
        )
        assert resp.status_code == 200
        return resp.json()["access_token"]

    def login(email: str, password: str) -> str:
        resp = client.post("/login", json={"email": email, "password": password})
        assert resp.status_code == 200
        return resp.json()["access_token"]

    def make_organizer(email: str = "org@test.ro", password: str = "organizer123") -> None:
        organizer = models.User(
            email=email,
            password_hash=auth.get_password_hash(password),
            role=models.UserRole.organizator,
        )
        db_session.add(organizer)
        db_session.commit()

    def auth_header(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "db": db_session,
        "register_student": register_student,
        "login": login,
        "make_organizer": make_organizer,
        "auth_header": auth_header,
    }

