"""Tests for event listing filters, sorting, public-listing, and rate limiting."""

from datetime import datetime, timezone

from api_test_support import (
    DEFAULT_ORG_CODE,
)


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
    _store = getattr(api_module, "_RATE_LIMIT_STORE", None)
    if _store is not None:
        _store.clear()
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
        _store = getattr(api_module, "_RATE_LIMIT_STORE", None)
        if _store is not None:
            _store.clear()
