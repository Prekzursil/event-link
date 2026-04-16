"""Tests for the postgres smoke behavior."""

from datetime import datetime, timedelta, timezone


def _require(condition: bool, message: str) -> None:
    """Implements the require helper."""
    if not condition:
        raise AssertionError(message)


def test_postgres_end_to_end_flow(helpers):
    """Verifies postgres end to end flow behavior."""
    client = helpers["client"]

    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer-fixture-A1")

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
    _require(
        created.status_code == 201, f"expected 201 when creating event, got {created.status_code}"
    )
    event_id = created.json()["id"]

    student_token = helpers["register_student"]("student@test.ro")
    registered = client.post(
        f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token)
    )
    _require(
        registered.status_code == 201,
        f"expected 201 when registering, got {registered.status_code}",
    )

    participants = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](organizer_token),
    )
    _require(
        participants.status_code == 200,
        f"expected 200 when listing participants, got {participants.status_code}",
    )
    _require(participants.json()["total"] == 1, "expected exactly one participant")
