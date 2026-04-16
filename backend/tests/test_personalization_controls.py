"""Tests for the personalization controls behavior."""

from datetime import datetime, timezone

from app import models


def _create_event(client, auth_header, payload):
    """Implements the create event helper."""
    response = client.post("/api/events", headers=auth_header, json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _user_id_by_email(db, email: str) -> int:
    """Implements the user id by email helper."""
    user = db.query(models.User).filter(models.User.email == email).first()
    assert user is not None
    return int(user.id)


def test_personalization_hide_tag_excludes_events(client, helpers):
    """Verifies personalization hide tag excludes events behavior."""
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

    organizer_header = helpers["auth_header"](org_token)
    rock_event_id = _create_event(
        client,
        organizer_header,
        {
            "title": "Rock concert",
            "description": "Live music",
            "category": "Music",
            "start_time": helpers["future_time"](days=10),
            "city": "Cluj-Napoca",
            "location": "Club",
            "max_seats": 100,
            "tags": ["Rock"],
        },
    )
    tech_event_id = _create_event(
        client,
        organizer_header,
        {
            "title": "Tech meetup",
            "description": "Talks",
            "category": "Education",
            "start_time": helpers["future_time"](days=11),
            "city": "Cluj-Napoca",
            "location": "Hub",
            "max_seats": 50,
            "tags": ["Tech"],
        },
    )

    student_token = helpers["register_student"]("student@test.ro")
    tags = client.get("/api/tags").json()["items"]
    rock_tag_id = next(
        (tag["id"] for tag in tags if tag["name"].lower() == "rock"), None
    )
    assert rock_tag_id is not None, "expected a 'rock' tag in /api/tags"

    resp = client.post(
        f"/api/me/personalization/hidden-tags/{rock_tag_id}",
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 201

    resp = client.get("/api/events", headers=helpers["auth_header"](student_token))
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert rock_event_id not in ids
    assert tech_event_id in ids


def test_personalization_blocked_organizer_excludes_events(client, helpers):
    """Verifies personalization blocked organizer excludes events behavior."""
    helpers["make_organizer"]("org1@test.ro")
    helpers["make_organizer"]("org2@test.ro")
    org1_token = helpers["login"]("org1@test.ro", "organizer-fixture-A1")
    org2_token = helpers["login"]("org2@test.ro", "organizer-fixture-A1")

    org1_event_id = _create_event(
        client,
        helpers["auth_header"](org1_token),
        {
            "title": "Org1 event",
            "description": "x",
            "category": "Education",
            "start_time": helpers["future_time"](days=10),
            "city": "București",
            "location": "Hall A",
            "max_seats": 10,
            "tags": ["General"],
        },
    )
    org2_event_id = _create_event(
        client,
        helpers["auth_header"](org2_token),
        {
            "title": "Org2 event",
            "description": "y",
            "category": "Education",
            "start_time": helpers["future_time"](days=11),
            "city": "București",
            "location": "Hall B",
            "max_seats": 10,
            "tags": ["General"],
        },
    )

    student_token = helpers["register_student"]("student2@test.ro")
    resp = client.post(
        f"/api/me/personalization/blocked-organizers/{_user_id_by_email(helpers['db'], 'org2@test.ro')}",
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 201

    ids = [
        item["id"]
        for item in client.get(
            "/api/events", headers=helpers["auth_header"](student_token)
        ).json()["items"]
    ]
    assert org2_event_id not in ids
    assert org1_event_id in ids


def test_personalization_settings_endpoint_lists_hidden_and_blocked(client, helpers):
    """Verifies personalization settings endpoint lists hidden and blocked behavior."""
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

    resp = client.post(
        "/api/events",
        headers=helpers["auth_header"](org_token),
        json={
            "title": "Event",
            "description": "x",
            "category": "Education",
            "start_time": helpers["future_time"](days=10),
            "city": "Iași",
            "location": "Hall A",
            "max_seats": 10,
            "tags": ["Tech"],
        },
    )
    assert resp.status_code == 201

    student_token = helpers["register_student"]("student3@test.ro")
    tags = client.get("/api/tags").json()["items"]
    tech_tag_id = next(
        (tag["id"] for tag in tags if tag["name"].lower() == "tech"), None
    )
    assert tech_tag_id is not None, "expected a 'tech' tag in /api/tags"

    resp = client.post(
        f"/api/me/personalization/hidden-tags/{tech_tag_id}",
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 201

    db = helpers["db"]
    org = db.query(models.User).filter(models.User.email == "org@test.ro").first()
    assert org is not None
    resp = client.post(
        f"/api/me/personalization/blocked-organizers/{org.id}",
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 201

    resp = client.get(
        "/api/me/personalization", headers=helpers["auth_header"](student_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(tag["name"].lower() == "tech" for tag in data["hidden_tags"])
    assert any(org_item["id"] == org.id for org_item in data["blocked_organizers"])


def test_event_detail_includes_recommendation_reason_for_student(client, helpers):
    """Verifies event detail includes recommendation reason for student behavior."""
    helpers["make_organizer"]("org@test.ro")
    org_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

    event_id = _create_event(
        client,
        helpers["auth_header"](org_token),
        {
            "title": "Event",
            "description": "x",
            "category": "Education",
            "start_time": helpers["future_time"](days=10),
            "city": "Cluj",
            "location": "Hall A",
            "max_seats": 10,
            "tags": ["Rock"],
        },
    )

    student_token = helpers["register_student"]("student4@test.ro")
    db = helpers["db"]
    student = (
        db.query(models.User).filter(models.User.email == "student4@test.ro").first()
    )
    assert student is not None
    student.city = "Cluj"
    db.add(student)
    db.commit()

    db.add(
        models.UserRecommendation(
            user_id=student.id,
            event_id=event_id,
            score=1.0,
            rank=1,
            model_version="test",
            generated_at=datetime.now(timezone.utc),
            reason="Your interests: Rock",
        )
    )
    db.commit()

    resp = client.get(
        f"/api/events/{event_id}",
        headers={
            **helpers["auth_header"](student_token),
            "Accept-Language": "en",
        },
    )
    assert resp.status_code == 200
    assert "Your interests: Rock" in (resp.json().get("recommendation_reason") or "")


def test_admin_personalization_metrics_uses_interactions(client, helpers):
    """Verifies admin personalization metrics uses interactions behavior."""
    helpers["make_admin"]("admin@test.ro")
    admin_token = helpers["login"]("admin@test.ro", "admin-fixture-A1")

    db = helpers["db"]
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            models.EventInteraction(
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list"},
            ),
            models.EventInteraction(
                interaction_type="click",
                occurred_at=now,
                meta={"source": "events_list"},
            ),
            models.EventInteraction(
                interaction_type="register",
                occurred_at=now,
                meta={"source": "event_detail"},
            ),
        ]
    )
    db.commit()

    resp = client.get(
        "/api/admin/personalization/metrics?days=7",
        headers=helpers["auth_header"](admin_token),
    )
    assert resp.status_code == 200
    totals = resp.json()["totals"]
    assert totals["impressions"] == 1
    assert totals["clicks"] == 1
    assert totals["registrations"] == 1
