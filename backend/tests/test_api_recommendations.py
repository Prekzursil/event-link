"""Tests for the api recommendations behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import models
from api_test_support import DEFAULT_ORG_CODE


def _ml_cache_context(helpers, *, email: str, generated_at: datetime | None = None):
    """Implements the ml cache context helper."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    payload = {
        "description": "Desc",
        "category": "Cat",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    earlier = client.post(
        "/api/events",
        json={
            **payload,
            "title": "Earlier",
            "start_time": helpers["future_time"](days=2),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    later = client.post(
        "/api/events",
        json={
            **payload,
            "title": "Later",
            "start_time": helpers["future_time"](days=3),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"](email)
    student = db.query(models.User).filter(models.User.email == email).first()
    assert student is not None
    return client, db, student_token, student, earlier, later, generated_at


def _store_ml_cache(
    *,
    db,
    student,
    earlier,
    later,
    first_reason: str,
    second_reason: str,
    generated_at: datetime | None = None,
) -> None:
    """Implements the store ml cache helper."""
    rows = [
        models.UserRecommendation(
            user_id=student.id,
            event_id=later["id"],
            score=0.9,
            rank=1,
            model_version="test",
            reason=first_reason,
            generated_at=generated_at,
        ),
        models.UserRecommendation(
            user_id=student.id,
            event_id=earlier["id"],
            score=0.8,
            rank=2,
            model_version="test",
            reason=second_reason,
            generated_at=generated_at,
        ),
    ]
    db.add_all(rows)
    db.commit()


def test_recommendations_skip_full_and_past(helpers):
    """Verifies recommendations skip full and past behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 1,
        "tags": ["python"],
    }
    full_event = client.post(
        "/api/events",
        json={
            **tag_payload,
            "title": "Full Event",
            "start_time": helpers["future_time"](days=1),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={
            **tag_payload,
            "title": "Past Event",
            "start_time": helpers["future_time"](days=-1),
        },
        headers=helpers["auth_header"](organizer_token),
    )

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(
        f"/api/events/{full_event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )

    rec = client.get(
        "/api/recommendations", headers=helpers["auth_header"](student_token)
    ).json()
    titles = [e["title"] for e in rec]
    assert "Full Event" not in titles
    assert "Past Event" not in titles


def test_recommendations_boosts_user_city(helpers):
    """Verifies recommendations boosts user city behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 20,
        "tags": [],
    }
    local = client.post(
        "/api/events",
        json={
            **base_payload,
            "title": "Local",
            "city": "Cluj-Napoca",
            "start_time": helpers["future_time"](days=2),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    remote = client.post(
        "/api/events",
        json={
            **base_payload,
            "title": "Remote",
            "city": "București",
            "start_time": helpers["future_time"](days=2),
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    for i in range(3):
        tok = helpers["register_student"](f"pop{i}@test.ro")
        client.post(
            f"/api/events/{remote['id']}/register", headers=helpers["auth_header"](tok)
        )

    student_token = helpers["register_student"]("city@test.ro")
    client.put(
        "/api/me/profile",
        json={"city": "Cluj-Napoca"},
        headers=helpers["auth_header"](student_token),
    )

    rec = client.get(
        "/api/recommendations",
        headers={**helpers["auth_header"](student_token), "Accept-Language": "ro"},
    ).json()
    assert len(rec) >= 2
    assert rec[0]["id"] == local["id"]
    assert "În apropiere" in (rec[0].get("recommendation_reason") or "")


def test_my_events_and_registration_state(helpers):
    """Verifies my events and registration state behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    e1 = client.post(
        "/api/events",
        json={
            "title": "Early",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
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
            "city": "București",
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(
        f"/api/events/{e2['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    client.post(
        f"/api/events/{e1['id']}/register",
        headers=helpers["auth_header"](student_token),
    )

    my_events = client.get(
        "/api/me/events", headers=helpers["auth_header"](student_token)
    ).json()
    assert [e1["id"], e2["id"]] == [e["id"] for e in my_events]

    detail = client.get(
        f"/api/events/{e1['id']}", headers=helpers["auth_header"](student_token)
    ).json()
    assert detail["is_registered"]
    assert detail["seats_taken"] == 1


def test_recommended_uses_tags_and_excludes_registered(helpers):
    """Verifies recommended uses tags and excludes registered behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
    }
    python_event = client.post(
        "/api/events",
        json={
            **tag_payload,
            "title": "Python 1",
            "start_time": helpers["future_time"](days=2),
            "tags": ["python"],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    another_python = client.post(
        "/api/events",
        json={
            **tag_payload,
            "title": "Python 2",
            "start_time": helpers["future_time"](days=3),
            "tags": ["python"],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(
        f"/api/events/{python_event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )

    rec_resp = client.get(
        "/api/recommendations", headers=helpers["auth_header"](student_token)
    )
    assert rec_resp.status_code == 200
    rec = rec_resp.json()
    rec_ids = [e["id"] for e in rec]
    assert another_python["id"] in rec_ids
    assert python_event["id"] not in rec_ids


def test_recommendations_use_profile_interest_tags_when_no_history(helpers):
    """Verifies recommendations use profile interest tags when no history behavior."""
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    payload = {
        "description": "Desc",
        "category": "Music",
        "city": "București",
        "location": "Loc",
        "max_seats": 50,
    }
    rock_event = client.post(
        "/api/events",
        json={
            **payload,
            "title": "Rock show",
            "start_time": helpers["future_time"](days=2),
            "tags": ["Rock"],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={
            **payload,
            "title": "Other",
            "start_time": helpers["future_time"](days=3),
            "tags": ["python"],
        },
        headers=helpers["auth_header"](organizer_token),
    )

    student_token = helpers["register_student"]("interest@test.ro")

    tags = client.get("/api/tags").json()["items"]
    rock_tag_id = next((t["id"] for t in tags if t["name"] == "Rock"), None)
    assert rock_tag_id is not None, "expected a 'Rock' tag in /api/tags"

    update = client.put(
        "/api/me/profile",
        json={"interest_tag_ids": [rock_tag_id]},
        headers=helpers["auth_header"](student_token),
    )
    assert update.status_code == 200

    rec = client.get(
        "/api/recommendations",
        headers={**helpers["auth_header"](student_token), "Accept-Language": "ro"},
    ).json()
    assert any(e["id"] == rock_event["id"] for e in rec)
    assert "Interesele tale" in (rec[0].get("recommendation_reason") or "")


def test_recommendations_use_ml_cache_when_present(helpers):
    """Verifies recommendations use ml cache when present behavior."""
    client, db, student_token, student, earlier, later, _generated_at = (
        _ml_cache_context(
            helpers,
            email="mlcache@test.ro",
        )
    )
    _store_ml_cache(
        db=db,
        student=student,
        earlier=earlier,
        later=later,
        first_reason="cache-1",
        second_reason="cache-2",
    )

    rec = client.get(
        "/api/recommendations", headers=helpers["auth_header"](student_token)
    ).json()
    assert len(rec) >= 2
    assert rec[0]["id"] == later["id"]
    assert rec[0].get("recommendation_reason") == "cache-1"


def test_recommendations_ignore_stale_ml_cache(helpers):
    """Verifies recommendations ignore stale ml cache behavior."""
    old = datetime.now(timezone.utc) - timedelta(days=2)
    client, db, student_token, student, earlier, later, _generated_at = (
        _ml_cache_context(
            helpers,
            email="mlstale@test.ro",
            generated_at=old,
        )
    )
    db.add(
        models.UserRecommendation(
            user_id=student.id,
            event_id=later["id"],
            score=0.9,
            rank=1,
            model_version="test",
            reason="cache-1",
            generated_at=old,
        )
    )
    db.commit()

    rec = client.get(
        "/api/recommendations", headers=helpers["auth_header"](student_token)
    ).json()
    assert len(rec) >= 1
    assert rec[0]["id"] == earlier["id"]


def test_analytics_interactions_recorded(helpers):
    """Verifies analytics interactions recorded behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)

    event = client.post(
        "/api/events",
        json={
            "title": "Track",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("track@test.ro")
    resp = client.post(
        "/api/analytics/interactions",
        json={
            "events": [
                {
                    "interaction_type": "impression",
                    "event_id": event["id"],
                    "meta": {"source": "events_list"},
                },
                {
                    "interaction_type": "click",
                    "event_id": event["id"],
                    "meta": {"source": "events_list"},
                },
                {
                    "interaction_type": "search",
                    "meta": {"query": "Track", "city": "București"},
                },
            ]
        },
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 204

    rows = db.query(models.EventInteraction).order_by(models.EventInteraction.id).all()
    assert len(rows) == 3
    assert rows[0].interaction_type == "impression"
    assert rows[0].event_id == event["id"]
    assert rows[2].interaction_type == "search"
    assert rows[2].event_id is None


def test_events_list_sort_recommended_uses_ml_cache(helpers):
    """Verifies events list sort recommended uses ml cache behavior."""
    client, db, student_token, student, earlier, later, _generated_at = (
        _ml_cache_context(
            helpers,
            email="mlsort@test.ro",
            generated_at=datetime.now(timezone.utc),
        )
    )
    _store_ml_cache(
        db=db,
        student=student,
        earlier=earlier,
        later=later,
        first_reason="cache-first",
        second_reason="cache-second",
        generated_at=datetime.now(timezone.utc),
    )

    resp = client.get(
        "/api/events?sort=recommended&page_size=10",
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["id"] == later["id"]
    assert data["items"][0].get("recommendation_reason") == "cache-first"
