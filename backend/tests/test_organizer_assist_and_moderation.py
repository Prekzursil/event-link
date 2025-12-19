from app import models


def test_organizer_suggest_endpoint_returns_duplicates_and_category(client, helpers):
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer123")
    headers = helpers["auth_header"](org_token)

    resp = client.post(
        "/api/events",
        headers=headers,
        json={
            "title": "AI Hackathon Cluj",
            "description": "Build cool stuff",
            "category": "Hackathon",
            "start_time": helpers["future_time"](days=10),
            "city": "Cluj",
            "location": "Hall A",
            "max_seats": 50,
            "tags": ["Tech", "AI"],
        },
    )
    assert resp.status_code == 201
    existing_event_id = resp.json()["id"]

    resp = client.post(
        "/api/organizer/events/suggest",
        headers=headers,
        json={
            "title": "AI Hackathon Cluj",
            "description": "hackathon for students",
            "location": "Hall A",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_category"] == "Hackathon"
    assert any(dup["id"] == existing_event_id for dup in data["duplicates"])


def test_event_moderation_flags_are_exposed_in_admin_events(client, helpers):
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer123")
    org_headers = helpers["auth_header"](org_token)

    resp = client.post(
        "/api/events",
        headers=org_headers,
        json={
            "title": "Giveaway",
            "description": "Win free money now! Visit https://bit.ly/scam and send OTP.",
            "category": "Social",
            "start_time": helpers["future_time"](days=10),
            "city": "Cluj",
            "location": "Hall A",
            "max_seats": 10,
            "tags": ["Social"],
        },
    )
    assert resp.status_code == 201
    event_id = resp.json()["id"]

    helpers["make_admin"]("admin@test.ro")
    admin_token = helpers["login"]("admin@test.ro", "admin123")
    admin_headers = helpers["auth_header"](admin_token)

    resp = client.get("/api/admin/events?flagged_only=true", headers=admin_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    flagged = next((item for item in items if item["id"] == event_id), None)
    assert flagged is not None
    assert flagged["moderation_status"] == "flagged"
    assert (flagged.get("moderation_score") or 0) >= 0.5

    resp = client.post(f"/api/admin/events/{event_id}/moderation/review", headers=admin_headers)
    assert resp.status_code == 200

    resp = client.get("/api/admin/events?include_deleted=true", headers=admin_headers)
    reviewed = next((item for item in resp.json()["items"] if item["id"] == event_id), None)
    assert reviewed is not None
    assert reviewed["moderation_status"] == "reviewed"

