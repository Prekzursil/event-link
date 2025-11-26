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


@pytest.fixture()
def helpers(client):
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

    def make_organizer(email="org@test.ro", password="organizer123") -> None:
        db = SessionLocal()
        organizer = models.User(
            email=email,
            password_hash=auth.get_password_hash(password),
            role=models.UserRole.organizator,
        )
        db.add(organizer)
        db.commit()
        db.close()

    def future_time(days=1) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def auth_header(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return {
        "client": client,
        "register_student": register_student,
        "login": login,
        "make_organizer": make_organizer,
        "future_time": future_time,
        "auth_header": auth_header,
    }


def test_student_registration_and_duplicate_email(helpers):
    client = helpers["client"]
    client.post(
        "/register",
        json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
    )
    duplicate = client.post(
        "/register",
        json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
    )
    assert duplicate.status_code == 400
    assert "deja folosit" in duplicate.json().get("detail", "")


def test_login_failure(helpers):
    client = helpers["client"]
    helpers["register_student"]("login@test.ro")
    bad = client.post("/login", json={"email": "login@test.ro", "password": "wrong"})
    assert bad.status_code == 401
    assert "incorect" in bad.json().get("detail", "")


def test_event_creation_and_capacity_enforced(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    start_time = helpers["future_time"]()
    payload = {
        "title": "Test Event",
        "description": "Descriere",
        "category": "Test",
        "start_time": start_time,
        "end_time": None,
        "location": "Online",
        "max_seats": 1,
        "tags": ["test"],
    }
    create_resp = client.post(
        "/api/events",
        json=payload,
        headers=helpers["auth_header"](organizer_token),
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    student1_token = helpers["register_student"]("s1@test.ro")
    reg1 = client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student1_token),
    )
    assert reg1.status_code == 201

    student2_token = helpers["register_student"]("s2@test.ro")
    reg2 = client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student2_token),
    )
    assert reg2.status_code == 409
    assert "plin" in reg2.json().get("detail", "")


def test_student_cannot_create_event(helpers):
    client = helpers["client"]
    student_token = helpers["register_student"]("stud@test.ro")
    payload = {
        "title": "Invalid",
        "description": "Desc",
        "category": "Test",
        "start_time": helpers["future_time"](),
        "end_time": None,
        "location": "Online",
        "max_seats": 10,
        "tags": [],
    }
    resp = client.post("/api/events", json=payload, headers=helpers["auth_header"](student_token))
    assert resp.status_code == 403


def test_edit_forbidden_for_non_owner(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("o1@test.ro", "pass1")
    helpers["make_organizer"]("o2@test.ro", "pass2")
    owner_token = helpers["login"]("o1@test.ro", "pass1")
    other_token = helpers["login"]("o2@test.ro", "pass2")

    create_resp = client.post(
        "/api/events",
        json={
            "title": "Owner Event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    )
    event_id = create_resp.json()["id"]

    update = client.put(
        f"/api/events/{event_id}",
        json={"title": "Hack"},
        headers=helpers["auth_header"](other_token),
    )
    assert update.status_code == 403


def test_delete_cascades_registrations(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    create_resp = client.post(
        "/api/events",
        json={
            "title": "Delete Me",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    )
    event_id = create_resp.json()["id"]

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))

    delete_resp = client.delete(f"/api/events/{event_id}", headers=helpers["auth_header"](organizer_token))
    assert delete_resp.status_code == 204

    db = SessionLocal()
    remaining_regs = db.query(models.Registration).count()
    db.close()
    assert remaining_regs == 0


def test_events_list_filters_and_order(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python Workshop", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Party Night", "category": "Social", "start_time": helpers["future_time"](days=3)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**base_payload, "title": "Old Event", "start_time": helpers["future_time"](days=-1)},
        headers=helpers["auth_header"](organizer_token),
    )

    events = client.get("/api/events").json()
    assert [e1["id"], e2["id"]] == [e["id"] for e in events["items"]]
    assert events["total"] == 2

    search = client.get("/api/events", params={"search": "python"}).json()
    assert search["total"] == 1
    assert search["items"][0]["title"] == "Python Workshop"

    category = client.get("/api/events", params={"category": "social"}).json()
    assert category["total"] == 1
    assert category["items"][0]["title"] == "Party Night"

    start_filter = client.get(
        "/api/events", params={"start_date": datetime.now(timezone.utc).date().isoformat()}
    ).json()
    assert len(start_filter["items"]) >= 2

    end_filter = client.get(
        "/api/events", params={"end_date": datetime.now(timezone.utc).date().isoformat()}
    ).json()
    assert end_filter["total"] == 0

    paging = client.get("/api/events", params={"page_size": 1, "page": 1}).json()
    assert paging["page_size"] == 1
    assert len(paging["items"]) == 1
    assert paging["total"] == 2


def test_event_validation_rules(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    bad_payload = {
        "title": "aa",
        "description": "Desc",
        "category": "C",
        "start_time": helpers["future_time"](days=1),
        "location": "L",
        "max_seats": -1,
        "tags": [],
        "cover_url": "http://example.com/" + "a" * 600,
    }
    resp = client.post("/api/events", json=bad_payload, headers=helpers["auth_header"](organizer_token))
    assert resp.status_code == 422


def test_recommendations_skip_full_and_past(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 1,
        "tags": ["python"],
    }
    full_event = client.post(
        "/api/events",
        json={**tag_payload, "title": "Full Event", "start_time": helpers["future_time"](days=1)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**tag_payload, "title": "Past Event", "start_time": helpers["future_time"](days=-1)},
        headers=helpers["auth_header"](organizer_token),
    )

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{full_event['id']}/register", headers=helpers["auth_header"](student_token))

    rec = client.get("/api/recommendations", headers=helpers["auth_header"](student_token)).json()
    titles = [e["title"] for e in rec]
    assert "Full Event" not in titles
    assert "Past Event" not in titles


def test_my_events_and_registration_state(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    e1 = client.post(
        "/api/events",
        json={
            "title": "Early",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={
            "title": "Late",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=5),
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{e2['id']}/register", headers=helpers["auth_header"](student_token))
    client.post(f"/api/events/{e1['id']}/register", headers=helpers["auth_header"](student_token))

    my_events = client.get("/api/me/events", headers=helpers["auth_header"](student_token)).json()
    assert [e1["id"], e2["id"]] == [e["id"] for e in my_events]

    detail = client.get(f"/api/events/{e1['id']}", headers=helpers["auth_header"](student_token)).json()
    assert detail["is_registered"]
    assert detail["seats_taken"] == 1


def test_recommended_uses_tags_and_excludes_registered(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 10,
    }
    python_event = client.post(
        "/api/events",
        json={**tag_payload, "title": "Python 1", "start_time": helpers["future_time"](days=2), "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    another_python = client.post(
        "/api/events",
        json={**tag_payload, "title": "Python 2", "start_time": helpers["future_time"](days=3), "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{python_event['id']}/register", headers=helpers["auth_header"](student_token))

    rec_resp = client.get("/api/recommendations", headers=helpers["auth_header"](student_token))
    assert rec_resp.status_code == 200
    rec = rec_resp.json()
    rec_ids = [e["id"] for e in rec]
    assert another_python["id"] in rec_ids
    assert python_event["id"] not in rec_ids


def test_duplicate_registration_blocked(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Dup",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    first = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert first.status_code == 201
    second = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert second.status_code == 400
    assert "înscris" in second.json().get("detail", "").lower()


def test_resend_registration_email_requires_registration(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Resend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    not_registered = client.post(
        f"/api/events/{event['id']}/register/resend", headers=helpers["auth_header"](student_token)
    )
    assert not_registered.status_code == 400

    client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    ok = client.post(f"/api/events/{event['id']}/register/resend", headers=helpers["auth_header"](student_token))
    assert ok.status_code == 200


def test_unregister_restores_spot(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Unregister Test",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "location": "Loc",
            "max_seats": 1,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    reg = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert reg.status_code == 201

    unregister = client.delete(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert unregister.status_code == 204

    other_token = helpers["register_student"]("stud2@test.ro")
    reg2 = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](other_token))
    assert reg2.status_code == 201


def test_mark_attendance_requires_owner(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "ownerpass")
    helpers["make_organizer"]("other@test.ro", "otherpass")
    owner_token = helpers["login"]("owner@test.ro", "ownerpass")
    other_token = helpers["login"]("other@test.ro", "otherpass")
    event = client.post(
        "/api/events",
        json={
            "title": "Attend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))

    forbidden = client.put(
        f"/api/organizer/events/{event['id']}/participants/1",
        params={"attended": True},
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden.status_code == 403

    db = SessionLocal()
    student = db.query(models.User).filter(models.User.email == "stud@test.ro").first()
    db.close()
    student_id = student.id  # type: ignore
    ok = client.put(
        f"/api/organizer/events/{event['id']}/participants/{student_id}",
        params={"attended": True},
        headers=helpers["auth_header"](owner_token),
    )
    assert ok.status_code == 204


def test_health_endpoint(helpers):
    client = helpers["client"]
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert body.get("database") == "ok"


def test_event_ics_and_calendar_feed(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    token = helpers["login"]("org@test.ro", "organizer123")
    start_time = helpers["future_time"]()
    payload = {
        "title": "ICS Event",
        "description": "Desc",
        "category": "Cat",
        "start_time": start_time,
        "end_time": None,
        "location": "Loc",
        "max_seats": 5,
        "tags": [],
    }
    create_resp = client.post(
        "/api/events",
        json=payload,
        headers=helpers["auth_header"](token),
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    ics_resp = client.get(f"/api/events/{event_id}/ics")
    assert ics_resp.status_code == 200
    assert "BEGIN:VCALENDAR" in ics_resp.text

    student_token = helpers["register_student"]("ics@test.ro")
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))
    feed_resp = client.get("/api/me/calendar", headers=helpers["auth_header"](student_token))
    assert feed_resp.status_code == 200
    assert "ICS Event" in feed_resp.text


def test_upgrade_to_organizer_requires_code(helpers):
    client = helpers["client"]
    student_token = helpers["register_student"]("code@test.ro")
    bad = client.post("/organizer/upgrade", json={"invite_code": "wrong"}, headers=helpers["auth_header"](student_token))
    assert bad.status_code == 403


def test_password_reset_flow(helpers):
    client = helpers["client"]
    helpers["register_student"]("reset@test.ro")
    req = client.post("/password/forgot", json={"email": "reset@test.ro"})
    assert req.status_code == 200
    db = SessionLocal()
    token_row = db.query(models.PasswordResetToken).filter(models.PasswordResetToken.used == False).first()
    token = token_row.token  # type: ignore
    db.close()

    reset = client.post(
        "/password/reset",
        json={"token": token, "new_password": "newpass123", "confirm_password": "newpass123"},
    )
    assert reset.status_code == 200

    login_ok = client.post("/login", json={"email": "reset@test.ro", "password": "newpass123"})
    assert login_ok.status_code == 200


def test_participants_pagination(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Paginated",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "location": "Loc",
            "max_seats": 50,
            "tags": [],
        },
        headers=helpers["auth_header"](org_token),
    ).json()
    for idx in range(5):
        token = helpers["register_student"](f"p{idx}@test.ro")
        client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](token))

    resp = client.get(
        f"/api/organizer/events/{event['id']}/participants",
        params={"page": 2, "page_size": 2, "sort_by": "email", "sort_dir": "desc"},
        headers=helpers["auth_header"](org_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["participants"]) == 2
    emails = [p["email"] for p in body["participants"]]
    assert emails == sorted(emails, reverse=True)
