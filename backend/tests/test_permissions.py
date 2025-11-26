import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import models, auth
from app.api import app
from app.database import Base, engine, SessionLocal, get_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)
    yield client


def make_organizer(email="org@test.ro", password="organizer123"):
    db = SessionLocal()
    organizer = models.User(email=email, password_hash=auth.get_password_hash(password), role=models.UserRole.organizator)
    db.add(organizer)
    db.commit()
    db.close()


def register_student(client: TestClient, email: str) -> str:
    resp = client.post(
        "/register",
        json={"email": email, "password": "password123", "confirm_password": "password123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def future_time(days=1) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_create_event_requires_auth(client: TestClient):
    payload = {
        "title": "Auth Required",
        "description": "Desc",
        "category": "Test",
        "start_time": future_time(),
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    resp = client.post("/api/events", json=payload)
    assert resp.status_code == 401


def test_organizer_routes_reject_students(client: TestClient):
    token = register_student(client, "stud@test.ro")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/organizer/events", headers=headers)
    assert resp.status_code == 403


def test_participants_visible_only_to_owner(client: TestClient):
    make_organizer("owner@test.ro", "ownerpass")
    make_organizer("other@test.ro", "otherpass")
    owner_token = login(client, "owner@test.ro", "ownerpass")
    other_token = login(client, "other@test.ro", "otherpass")

    create_resp = client.post(
        "/api/events",
        json={
            "title": "Owner Event",
            "description": "Desc",
            "category": "Tech",
            "start_time": future_time(),
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    event_id = create_resp.json()["id"]

    forbidden = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 403

    ok = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ok.status_code == 200
