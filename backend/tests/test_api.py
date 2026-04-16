"""Tests for the api behavior."""

from datetime import datetime, timezone

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


def test_events_list_filters_and_order(helpers):
    """Verifies events list filters and order behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    e1 = client.post(
        "/api/events",
        json={
            **base_payload,
            "title": "Python Workshop",
            "start_time": helpers["future_time"](days=2),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={
            **base_payload,
            "title": "Party Night",
            "category": "Social",
            "start_time": helpers["future_time"](days=3),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={
            **base_payload,
            "title": "Old Event",
            "start_time": helpers["future_time"](days=-1),
        },
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
        "/api/events",
        params={"start_date": datetime.now(timezone.utc).date().isoformat()},
    ).json()
    assert len(start_filter["items"]) >= 2

    end_filter = client.get(
        "/api/events",
        params={"end_date": datetime.now(timezone.utc).date().isoformat()},
    ).json()
    assert end_filter["total"] == 0

    paging = client.get("/api/events", params={"page_size": 1, "page": 1}).json()
    assert paging["page_size"] == 1
    assert len(paging["items"]) == 1
    assert paging["total"] == 2


def test_events_list_filters_by_city(helpers):
    """Verifies events list filters by city behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    c1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Cluj Event", "city": "Cluj-Napoca"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**base_payload, "title": "Buc Event", "city": "București"},
        headers=helpers["auth_header"](organizer_token),
    )

    filtered = client.get("/api/events", params={"city": "cluj"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == c1["id"]


def test_events_list_filters_by_tags_without_duplicates(helpers):
    """Verifies events list filters by tags without duplicates behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python + AI", "tags": ["python", "ai"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python only", "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.get("/api/events", params=[("tags", "python"), ("tags", "ai")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [e["id"] for e in body["items"]]
    assert ids.count(e1["id"]) == 1
    assert ids.count(e2["id"]) == 1


def test_public_events_filters_by_tags_without_duplicates(helpers):
    """Verifies public events filters by tags without duplicates behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("public-tags-org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("public-tags-org@test.ro", DEFAULT_ORG_CODE)

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Public Python + AI", "tags": ["python", "ai"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Public Python only", "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.get("/api/public/events", params=[("tags", "python"), ("tags", "ai")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [e["id"] for e in body["items"]]
    assert ids.count(e1["id"]) == 1
    assert ids.count(e2["id"]) == 1


def test_public_events_api_exposes_published_only(helpers):
    """Verifies public events api exposes published only behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("public-org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("public-org@test.ro", DEFAULT_ORG_CODE)
    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    published = client.post(
        "/api/events",
        json={**base_payload, "title": "Published"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    draft = client.post(
        "/api/events",
        json={**base_payload, "title": "Draft", "status": "draft"},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    public_list = client.get("/api/public/events")
    assert public_list.status_code == 200
    items = public_list.json()["items"]
    assert any(e["id"] == published["id"] for e in items)
    assert all(e["id"] != draft["id"] for e in items)

    public_detail = client.get(f"/api/public/events/{published['id']}")
    assert public_detail.status_code == 200
    assert public_detail.json()["id"] == published["id"]

    draft_detail = client.get(f"/api/public/events/{draft['id']}")
    assert draft_detail.status_code == 404


def test_public_events_api_is_rate_limited(helpers):
    """Verifies public events api is rate limited behavior."""
    client = helpers["client"]
    from app import api as api_module
    from app.config import settings

    helpers["make_organizer"]("public-limit-org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("public-limit-org@test.ro", DEFAULT_ORG_CODE)

    old_limit = settings.public_api_rate_limit
    old_window = settings.public_api_rate_window_seconds
    settings.public_api_rate_limit = 2
    settings.public_api_rate_window_seconds = 60
    (_s := getattr(api_module, "_RATE_LIMIT_STORE", None)) and _s.clear()
    try:
        client.post(
            "/api/events",
            json={
                "title": "Rate limit",
                "description": "Desc",
                "category": "Tech",
                "start_time": helpers["future_time"](days=2),
                "city": "București",
                "location": "Loc",
                "max_seats": 10,
                "tags": [],
            },
            headers=helpers["auth_header"](organizer_token),
        )

        _response = client.get("/api/public/events")
        assert _response.status_code == 200
        _response = client.get("/api/public/events")
        assert _response.status_code == 200
        limited = client.get("/api/public/events")
        assert limited.status_code == 429
    finally:
        settings.public_api_rate_limit = old_limit
        settings.public_api_rate_window_seconds = old_window
        (_s := getattr(api_module, "_RATE_LIMIT_STORE", None)) and _s.clear()


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
