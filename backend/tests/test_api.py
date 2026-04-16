"""Tests for the api behavior."""

from app import models
from api_test_support import (
    DEFAULT_ORG_CODE,
)


def test_event_creation_and_capacity_enforced(helpers):
    """Verifies event creation and capacity enforced behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    start_time = helpers["future_time"]()
    payload = {
        "title": "Test Event",
        "description": "Descriere",
        "category": "Test",
        "start_time": start_time,
        "end_time": None,
        "city": "București",
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
    """Verifies student cannot create event behavior."""
    client = helpers["client"]
    student_token = helpers["register_student"]("stud@test.ro")
    payload = {
        "title": "Invalid",
        "description": "Desc",
        "category": "Test",
        "start_time": helpers["future_time"](),
        "end_time": None,
        "city": "București",
        "location": "Online",
        "max_seats": 10,
        "tags": [],
    }
    resp = client.post(
        "/api/events", json=payload, headers=helpers["auth_header"](student_token)
    )
    assert resp.status_code == 403


def test_edit_forbidden_for_non_owner(helpers):
    """Verifies edit forbidden for non owner behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("o1@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("o2@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("o1@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("o2@test.ro", "other-fixture-A1")

    create_resp = client.post(
        "/api/events",
        json={
            "title": "Owner Event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
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


def test_reregister_after_unregister_restores_registration(helpers):
    """Verifies reregister after unregister restores registration behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("rereg-org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("rereg-org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "ReReg",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 1,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("rereg-stud@test.ro")

    first = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert first.status_code == 201
    unregister = client.delete(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert unregister.status_code == 204

    second = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert second.status_code == 201

    regs = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event["id"])
        .all()
    )
    assert len(regs) == 1
    assert regs[0].deleted_at is None


def test_event_validation_rules(helpers):
    """Verifies event validation rules behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    bad_payload = {
        "title": "aa",
        "description": "Desc",
        "category": "C",
        "start_time": helpers["future_time"](days=1),
        "city": "București",
        "location": "L",
        "max_seats": -1,
        "tags": [],
        "cover_url": "https://example.com/" + "a" * 600,
    }
    resp = client.post(
        "/api/events", json=bad_payload, headers=helpers["auth_header"](organizer_token)
    )
    assert resp.status_code == 422


def test_duplicate_registration_blocked(helpers):
    """Verifies duplicate registration blocked behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Dup",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    first = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert second.status_code == 400
    assert "înscris" in second.json().get("detail", "").lower()


def test_resend_registration_email_requires_registration(helpers):
    """Verifies resend registration email requires registration behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Resend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    not_registered = client.post(
        f"/api/events/{event['id']}/register/resend",
        headers=helpers["auth_header"](student_token),
    )
    assert not_registered.status_code == 400

    client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    ok = client.post(
        f"/api/events/{event['id']}/register/resend",
        headers=helpers["auth_header"](student_token),
    )
    assert ok.status_code == 200


def test_unregister_restores_spot(helpers):
    """Verifies unregister restores spot behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Unregister Test",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 1,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    reg = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert reg.status_code == 201

    unregister = client.delete(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert unregister.status_code == 204

    other_token = helpers["register_student"]("stud2@test.ro")
    reg2 = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](other_token),
    )
    assert reg2.status_code == 201


def test_mark_attendance_requires_owner(helpers):
    """Verifies mark attendance requires owner behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("other@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("other@test.ro", "other-fixture-A1")
    event = client.post(
        "/api/events",
        json={
            "title": "Attend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )

    forbidden = client.put(
        f"/api/organizer/events/{event['id']}/participants/1",
        params={"attended": True},
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden.status_code == 403

    student = (
        helpers["db"]
        .query(models.User)
        .filter(models.User.email == "stud@test.ro")
        .first()
    )
    student_id = student.id  # type: ignore
    ok = client.put(
        f"/api/organizer/events/{event['id']}/participants/{student_id}",
        params={"attended": True},
        headers=helpers["auth_header"](owner_token),
    )
    assert ok.status_code == 204
