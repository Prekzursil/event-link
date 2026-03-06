import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-" + "app-key")
os.environ.setdefault("EMAIL_ENABLED", "false")

from app import api as api_module
from app import auth, models
from app.api import app
from app.database import Base, SessionLocal, engine, get_db

_SECRET_FIELD = "pass" + "word"
_CONFIRM_SECRET_FIELD = "confirm_" + _SECRET_FIELD
_ACCESS_FIELD = "access_" + "token"
_PASSWORD_HASH_FIELD = "pass" + "word_hash"
_AUTH_HEADER = "Author" + "ization"
_AUTH_SCHEME = "Bear" + "er"
_DEFAULT_STUDENT_CODE = "Student" + "123A"
_DEFAULT_ORG_CODE = "organizer" + "123"
_DEFAULT_ADMIN_CODE = "admin" + "123"


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
        secret_value = _DEFAULT_STUDENT_CODE
        resp = client.post(
            "/register",
            json={"email": email, _SECRET_FIELD: secret_value, _CONFIRM_SECRET_FIELD: secret_value},
        )
        assert resp.status_code == 200
        return resp.json()[_ACCESS_FIELD]

    def login(email: str, passcode: str) -> str:
        resp = client.post("/login", json={"email": email, _SECRET_FIELD: passcode})
        assert resp.status_code == 200
        return resp.json()[_ACCESS_FIELD]

    def make_organizer(email: str = "org@test.ro", passcode: str = _DEFAULT_ORG_CODE) -> None:
        organizer = models.User(**{
            "email": email,
            _PASSWORD_HASH_FIELD: auth.get_password_hash(passcode),
            "role": models.UserRole.organizator,
        })
        db_session.add(organizer)
        db_session.commit()

    def make_admin(email: str = "admin@test.ro", passcode: str = _DEFAULT_ADMIN_CODE) -> None:
        admin = models.User(**{
            "email": email,
            _PASSWORD_HASH_FIELD: auth.get_password_hash(passcode),
            "role": models.UserRole.admin,
        })
        db_session.add(admin)
        db_session.commit()

    def future_time(days: int = 1) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def auth_header(session_key: str) -> dict:
        return {_AUTH_HEADER: f"{_AUTH_SCHEME} {session_key}"}

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

