from datetime import datetime, timedelta, timezone


def test_postgres_end_to_end_flow(helpers):
    client = helpers["client"]

    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    event_payload = {
        "title": "Integration Event",
        "description": "Desc",
        "category": "Tech",
        "start_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": ["Tech"],
        "status": "published",
    }
    created = client.post(
        "/api/events",
        json=event_payload,
        headers=helpers["auth_header"](organizer_token),
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    student_token = helpers["register_student"]("student@test.ro")
    registered = client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))
    assert registered.status_code == 201

    participants = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](organizer_token),
    )
    assert participants.status_code == 200
    assert participants.json()["total"] == 1

