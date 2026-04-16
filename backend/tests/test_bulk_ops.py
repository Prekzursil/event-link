"""Tests for the bulk ops behavior."""
def test_organizer_bulk_update_status(helpers):
    """Verifies organizer bulk update status behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Evt 1"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Evt 2"},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [e1["id"], e2["id"]], "status": "draft"},
        headers=helpers["auth_header"](organizer_token),
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    updated = client.get("/api/organizer/events", headers=helpers["auth_header"](organizer_token)).json()
    by_id = {e["id"]: e for e in updated}
    assert by_id[e1["id"]]["status"] == "draft"
    assert by_id[e2["id"]]["status"] == "draft"


def test_organizer_bulk_update_tags(helpers):
    """Verifies organizer bulk update tags behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Evt 1"},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [e1["id"]], "tags": ["AI", "Tech"]},
        headers=helpers["auth_header"](organizer_token),
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1

    updated = client.get(f"/api/events/{e1['id']}", headers=helpers["auth_header"](organizer_token)).json()
    tag_names = sorted(t["name"] for t in updated["tags"])
    assert tag_names == ["AI", "Tech"]


def test_organizer_bulk_ops_forbidden_for_other_organizer(helpers):
    """Verifies organizer bulk ops forbidden for other organizer behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    owner_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("other@test.ro", "other-fixture-A1")
    other_token = helpers["login"]("other@test.ro", "other-fixture-A1")

    event = client.post(
        "/api/events",
        json={
            "title": "Evt 1",
            "description": "Desc",
            "category": "Tech",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()

    resp = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [event["id"]], "status": "draft"},
        headers=helpers["auth_header"](other_token),
    )
    assert resp.status_code == 403

    resp = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [event["id"]], "tags": ["AI"]},
        headers=helpers["auth_header"](other_token),
    )
    assert resp.status_code == 403


def test_organizer_email_participants(helpers):
    """Verifies organizer email participants behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    organizer_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")

    event = client.post(
        "/api/events",
        json={
            "title": "Evt 1",
            "description": "Desc",
            "category": "Tech",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("s1@test.ro")
    register = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert register.status_code == 201

    resp = client.post(
        f"/api/organizer/events/{event['id']}/participants/email",
        json={"subject": "Hello", "message": "Test message"},
        headers=helpers["auth_header"](organizer_token),
    )
    assert resp.status_code == 200
    assert resp.json()["recipients"] == 1
