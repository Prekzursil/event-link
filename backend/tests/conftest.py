import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("EMAIL_ENABLED", "false")

from app import auth, models
from app import api as api_module
from app.api import app
from app.database import Base, engine, get_db, SessionLocal


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
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
    def _override_get_db():
        yield db_session

    api_module._RATE_LIMIT_STORE.clear()
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

    def make_admin(email: str = "admin@test.ro", password: str = "admin123") -> None:
        admin = models.User(
            email=email,
            password_hash=auth.get_password_hash(password),
            role=models.UserRole.admin,
        )
        db_session.add(admin)
        db_session.commit()

    def future_time(days: int = 1) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def auth_header(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "db": db_session,
        "register_student": register_student,
        "login": login,
        "make_organizer": make_organizer,
        "make_admin": make_admin,
        "future_time": future_time,
        "auth_header": auth_header,
    }
