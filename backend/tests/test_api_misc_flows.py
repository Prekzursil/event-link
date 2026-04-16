"""Tests for the api misc flows behavior."""
from app import models
from api_test_support import (
    CONFIRM_SECRET_FIELD,
    DEFAULT_ORG_CODE,
    DEFAULT_STUDENT_CODE,
    NEW_SECRET_FIELD,
    PASSCODE_ROUTE,
    RESET_CODE,
    RESET_KEY_FIELD,
    RESET_RECORD,
    SECRET_FIELD,
)


def test_health_endpoint(helpers):
    """Verifies health endpoint behavior."""
    client = helpers["client"]
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert body.get("database") == "ok"


def test_event_ics_and_calendar_feed(helpers):
    """Verifies event ics and calendar feed behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    payload = {
        "title": "ICS Event",
        "description": "Desc",
        "category": "Cat",
        "start_time": helpers["future_time"](),
        "end_time": None,
        "city": "București",
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
    registered = client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert registered.status_code == 201

    feed_resp = client.get("/api/me/calendar", headers=helpers["auth_header"](student_token))
    assert feed_resp.status_code == 200
    assert "ICS Event" in feed_resp.text


def test_access_code_reset_flow(helpers):
    """Verifies access code reset flow behavior."""
    client = helpers["client"]
    helpers["register_student"]("reset@test.ro")
    req = client.post(f"{PASSCODE_ROUTE}/forgot", json={"email": "reset@test.ro"})
    assert req.status_code == 200

    reset_row = helpers["db"].query(RESET_RECORD).filter(RESET_RECORD.used.is_(False)).first()
    reset_key = getattr(reset_row, RESET_KEY_FIELD)  # type: ignore[name-defined]

    reset = client.post(
        f"{PASSCODE_ROUTE}/reset",
        json={RESET_KEY_FIELD: reset_key, NEW_SECRET_FIELD: RESET_CODE, CONFIRM_SECRET_FIELD: RESET_CODE},
    )
    assert reset.status_code == 200

    login_ok = client.post("/login", json={"email": "reset@test.ro", SECRET_FIELD: RESET_CODE})
    assert login_ok.status_code == 200


def test_participants_pagination(helpers):
    """Verifies participants pagination behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Paginated",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 50,
            "tags": [],
        },
        headers=helpers["auth_header"](org_token),
    ).json()
    for idx in range(5):
        token = helpers["register_student"](f"p{idx}@test.ro")
        registered = client.post(
            f"/api/events/{event['id']}/register",
            headers=helpers["auth_header"](token),
        )
        assert registered.status_code == 201

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
    emails = [participant["email"] for participant in body["participants"]]
    assert emails == sorted(emails, reverse=True)


def test_account_export_and_deletion_student(helpers):
    """Verifies account export and deletion student behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Export Event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": ["export"],
        },
        headers=helpers["auth_header"](org_token),
    ).json()

    student_token = helpers["register_student"]("export@test.ro")
    reg = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert reg.status_code == 201

    export_resp = client.get("/api/me/export", headers=helpers["auth_header"](student_token))
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert payload["user"]["email"] == "export@test.ro"
    assert payload["user"]["role"] == "student"
    assert len(payload["registrations"]) == 1
    assert payload["registrations"][0]["event"]["id"] == event["id"]

    bad_delete = client.request(
        "DELETE",
        "/api/me",
        json={SECRET_FIELD: "wrong"},
        headers=helpers["auth_header"](student_token),
    )
    assert bad_delete.status_code == 400

    ok_delete = client.request(
        "DELETE",
        "/api/me",
        json={SECRET_FIELD: DEFAULT_STUDENT_CODE},
        headers=helpers["auth_header"](student_token),
    )
    assert ok_delete.status_code == 200

    me_after = client.get("/me", headers=helpers["auth_header"](student_token))
    assert me_after.status_code == 401


def test_organizer_account_deletion_reassigns_events(helpers):
    """Verifies organizer account deletion reassigns events behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event = client.post(
        "/api/events",
        json={
            "title": "Orphaned",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](org_token),
    ).json()

    delete_resp = client.request(
        "DELETE",
        "/api/me",
        json={SECRET_FIELD: DEFAULT_ORG_CODE},
        headers=helpers["auth_header"](org_token),
    )
    assert delete_resp.status_code == 200

    placeholder = (
        helpers["db"].query(models.User).filter(models.User.email == "deleted-organizer@eventlink.invalid").first()
    )
    assert placeholder is not None
    event_row = helpers["db"].query(models.Event).filter(models.Event.id == event["id"]).first()
    assert event_row is not None
    assert event_row.owner_id == placeholder.id
