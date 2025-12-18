def test_create_event_requires_auth(helpers):
    client = helpers["client"]
    payload = {
        "title": "Auth Required",
        "description": "Desc",
        "category": "Test",
        "start_time": helpers["future_time"](),
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    resp = client.post("/api/events", json=payload)
    assert resp.status_code == 401


def test_organizer_routes_reject_students(helpers):
    client = helpers["client"]
    token = helpers["register_student"]("stud@test.ro")
    resp = client.get("/api/organizer/events", headers=helpers["auth_header"](token))
    assert resp.status_code == 403


def test_participants_visible_only_to_owner(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "ownerpass")
    helpers["make_organizer"]("other@test.ro", "otherpass")
    owner_token = helpers["login"]("owner@test.ro", "ownerpass")
    other_token = helpers["login"]("other@test.ro", "otherpass")

    create_resp = client.post(
        "/api/events",
        json={
            "title": "Owner Event",
            "description": "Desc",
            "category": "Tech",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    )
    event_id = create_resp.json()["id"]

    forbidden = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden.status_code == 403

    ok = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](owner_token),
    )
    assert ok.status_code == 200
