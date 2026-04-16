"""Tests for the api branch closure extra behavior."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from app import schemas

from api_branch_extra_helpers import ScalarDb, api, auth_header, event_payload, models


def _serializer_edge_event():
    """Implements the serializer edge event helper."""
    return models.Event(
        id=1,
        title="Edge",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=7,
        status="published",
    )


def _assert_serializer_defaults(event) -> None:
    """Asserts that serializer defaults holds."""
    serialized = api._serialize_event(event, seats_taken=0)
    public_serialized = api._serialize_public_event(event, seats_taken=0)
    admin_serialized = api._serialize_admin_event(event, seats_taken=0)
    assert serialized.owner_name is None
    assert public_serialized.organizer_name is None
    assert admin_serialized.owner_name is None
    assert admin_serialized.owner_email == "unknown@example.com"


def _assert_create_event_accepts_missing_start_time(monkeypatch) -> None:
    """Asserts that create event accepts missing start time holds."""
    monkeypatch.setattr(api, "_attach_tags", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "_compute_moderation", lambda **_kwargs: (0.0, [], "clean"))
    monkeypatch.setattr(api, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        api,
        "_serialize_event",
        lambda event, seats_taken=0, recommendation_reason=None: SimpleNamespace(
            id=event.id, start_time=event.start_time
        ),
    )

    class _CreateDb:
        """Create Db value object used in the surrounding module."""
        @staticmethod
        def add(_obj):
            """Implements the add helper."""
            return None

        @staticmethod
        def commit():
            """Implements the commit helper."""
            return None

        @staticmethod
        def refresh(obj):
            """Implements the refresh helper."""
            obj.id = 77

    created = api.create_event(
        SimpleNamespace(
            title="Unit Create",
            description="desc",
            category="Edu",
            start_time=None,
            end_time=None,
            city="Cluj",
            location="Hall",
            max_seats=10,
            cover_url=None,
            tags=[],
            status="published",
            publish_at=None,
        ),
        db=_CreateDb(),
        current_user=SimpleNamespace(id=7),
    )
    assert created.id == 77
    assert created.start_time is None


def test_serializers_cache_fresh_and_create_event_optional_start_time(monkeypatch):
    """Verifies serializers cache fresh and create event optional start time behavior."""
    event = _serializer_edge_event()
    _assert_serializer_defaults(event)

    now = datetime.now(timezone.utc)
    assert api._recommendations_cache_is_fresh(db=ScalarDb(now), user_id=1, now=now) is True
    assert api._recommendations_cache_is_fresh(db=ScalarDb(now.replace(tzinfo=None)), user_id=1, now=now) is True
    _assert_create_event_accepts_missing_start_time(monkeypatch)


def test_events_and_public_events_include_past_and_optional_detail_user(helpers):
    """Verifies events and public events include past and optional detail user behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("include-past-org@test.ro", "organizer-fixture-A1")
    organizer = db.query(models.User).filter(models.User.email == "include-past-org@test.ro").first()
    assert organizer is not None

    future_event = models.Event(
        title="Future Visible",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(organizer.id),
        status="published",
    )
    past_event = models.Event(
        title="Past Visible",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(organizer.id),
        status="published",
    )
    db.add_all([future_event, past_event])
    db.commit()
    db.refresh(future_event)
    db.refresh(past_event)

    events_resp = client.get("/api/events", params={"include_past": "true"})
    assert events_resp.status_code == 200
    event_ids = {int(item["id"]) for item in events_resp.json()["items"]}
    assert int(past_event.id) in event_ids
    assert int(future_event.id) in event_ids

    public_resp = client.get("/api/public/events", params={"include_past": "true"})
    assert public_resp.status_code == 200
    public_ids = {int(item["id"]) for item in public_resp.json()["items"]}
    assert int(past_event.id) in public_ids

    detail_resp = client.get(f"/api/events/{int(future_event.id)}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["is_registered"] is False
    assert detail_resp.json()["is_favorite"] is False


def _create_explicit_language_event(client, auth_headers, start_time: str, title: str) -> int:
    """Implements the create explicit language event helper."""
    response = client.post(
        "/api/events",
        json=event_payload(start_time, title=title),
        headers=auth_headers,
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _seed_explicit_language_student(helpers, event_ids: tuple[int, int]) -> str:
    """Implements the seed explicit language student helper."""
    db = helpers["db"]
    student_token = helpers["register_student"]("explicit-lang@test.ro")
    student = db.query(models.User).filter(models.User.email == "explicit-lang@test.ro").first()
    assert student is not None
    student.language_preference = "en"
    student.city = "Cluj"
    db.add(student)
    db.add_all(
        [
            models.UserRecommendation(
                user_id=int(student.id),
                event_id=event_ids[1],
                rank=1,
                score=0.9,
                reason="explicit-cache",
                model_version="v1",
                generated_at=datetime.now(timezone.utc),
            ),
            models.UserRecommendation(
                user_id=int(student.id),
                event_id=event_ids[0],
                rank=2,
                score=0.8,
                reason="fallback-cache",
                model_version="v1",
                generated_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()
    return student_token


def _explicit_language_context(helpers):
    """Implements the explicit language context helper."""
    client = helpers["client"]
    helpers["make_organizer"]("lang-owner@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("lang-owner@test.ro", "organizer-fixture-A1")
    auth_headers = helpers["auth_header"](organizer_token)
    event_ids = (
        _create_explicit_language_event(
            client,
            auth_headers,
            helpers["future_time"](days=2),
            "Explicit Language First",
        ),
        _create_explicit_language_event(
            client,
            auth_headers,
            helpers["future_time"](days=3),
            "Explicit Language Second",
        ),
    )
    register_id = _create_explicit_language_event(
        client,
        auth_headers,
        helpers["future_time"](days=4),
        "Register Language",
    )
    student_token = _seed_explicit_language_student(helpers, event_ids)
    return client, student_token, event_ids[0], event_ids[1], register_id


def _assert_explicit_language_reads_cached_reason(client, student_token: str, event_id: int) -> None:
    """Asserts that explicit language reads cached reason holds."""
    sorted_resp = client.get(
        "/api/events",
        params={"sort": "recommended", "include_past": "true"},
        headers={**auth_header(student_token), "Accept-Language": "ro"},
    )
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["items"][0]["id"] == event_id
    assert sorted_resp.json()["items"][0]["recommendation_reason"].startswith("explicit-cache")

    detail_resp = client.get(
        f"/api/events/{event_id}",
        headers={**auth_header(student_token), "Accept-Language": "ro"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["recommendation_reason"].startswith("explicit-cache")

    recommendations_resp = client.get(
        "/api/recommendations",
        headers={**auth_header(student_token), "Accept-Language": "ro"},
    )
    assert recommendations_resp.status_code == 200


def _assert_registration_email_uses_profile_language(
    client, student_token: str, event_id: int, langs: list[str]
) -> None:
    """Asserts that registration email uses profile language holds."""
    register_resp = client.post(
        f"/api/events/{event_id}/register",
        headers={**auth_header(student_token), "Accept-Language": "ro"},
    )
    assert register_resp.status_code == 201
    resend_resp = client.post(
        f"/api/events/{event_id}/register/resend",
        headers={**auth_header(student_token), "Accept-Language": "ro"},
    )
    assert resend_resp.status_code == 200
    assert langs == ["en", "en"]


def test_explicit_language_paths_for_lists_detail_recommendations_and_registration(helpers, monkeypatch):
    """Verifies explicit language paths for lists detail recommendations and registration behavior."""
    client, student_token, _first_id, second_id, register_id = _explicit_language_context(helpers)
    langs: list[str] = []
    monkeypatch.setattr(
        api,
        "render_registration_email",
        lambda event, user, *, lang: langs.append(lang) or ("subject", "body", "<p>body</p>"),
    )
    _assert_explicit_language_reads_cached_reason(client, student_token, second_id)
    _assert_registration_email_uses_profile_language(client, student_token, register_id, langs)


def test_update_notifications_supports_partial_payloads(helpers):
    """Verifies update notifications supports partial payloads behavior."""
    client = helpers["client"]
    student_token = helpers["register_student"]("partial-notifications@test.ro")
    partial_digest = client.put(
        "/api/me/notifications",
        headers=helpers["auth_header"](student_token),
        json={"email_digest_enabled": True},
    )
    assert partial_digest.status_code == 200
    assert partial_digest.json()["email_digest_enabled"] is True
    assert partial_digest.json()["email_filling_fast_enabled"] is False

    partial_filling_fast = client.put(
        "/api/me/notifications",
        headers=helpers["auth_header"](student_token),
        json={"email_filling_fast_enabled": True},
    )
    assert partial_filling_fast.status_code == 200
    assert partial_filling_fast.json()["email_digest_enabled"] is True
    assert partial_filling_fast.json()["email_filling_fast_enabled"] is True


def test_delete_account_reuses_single_placeholder_owner(helpers):
    """Verifies delete account reuses single placeholder owner behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("delete-owner-a@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("delete-owner-b@test.ro", "other-fixture-A1")
    token_a = helpers["login"]("delete-owner-a@test.ro", "owner-fixture-A1")
    token_b = helpers["login"]("delete-owner-b@test.ro", "other-fixture-A1")

    for idx, token in enumerate((token_a, token_b), start=1):
        created = client.post(
            "/api/events",
            json=event_payload(helpers["future_time"](days=idx + 2), title=f"Delete Event {idx}"),
            headers=auth_header(token),
        )
        assert created.status_code == 201
        deleted = client.request(
            "DELETE",
            "/api/me",
            json={"password": "owner-fixture-A1" if idx == 1 else "other-fixture-A1"},
            headers=auth_header(token),
        )
        assert deleted.status_code == 200

    placeholders = db.query(models.User).filter(models.User.email == "deleted-organizer@eventlink.invalid").all()
    assert len(placeholders) == 1


def _seed_restore_and_clone_context(helpers):
    """Implements the seed restore and clone context helper."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_admin"]("restore-admin@test.ro", "admin-fixture-A1")
    helpers["make_organizer"]("restore-plain-owner@test.ro", "restore-fixture-A1")
    admin_token = helpers["login"]("restore-admin@test.ro", "admin-fixture-A1")
    owner_token = helpers["login"]("restore-plain-owner@test.ro", "restore-fixture-A1")
    restore_owner = db.query(models.User).filter(models.User.email == "restore-plain-owner@test.ro").first()
    assert restore_owner is not None

    restore_event = models.Event(
        title="Restore Plain",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=5),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(restore_owner.id),
        status="published",
        deleted_at=datetime.now(timezone.utc),
        deleted_by_user_id=None,
    )
    future_clone = models.Event(
        title="Clone Future",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=8),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(restore_owner.id),
        status="published",
    )
    db.add_all([restore_event, future_clone])
    db.commit()
    db.refresh(restore_event)
    db.refresh(future_clone)
    return client, admin_token, owner_token, restore_event, future_clone


def _assert_restore_and_clone_paths(
    client, helpers, admin_token: str, owner_token: str, restore_event, future_clone
) -> None:
    """Asserts that restore and clone paths holds."""
    restore_resp = client.post(
        f"/api/events/{int(restore_event.id)}/restore", headers=helpers["auth_header"](admin_token)
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored_registrations"] == 0

    clone_resp = client.post(f"/api/events/{int(future_clone.id)}/clone", headers=helpers["auth_header"](owner_token))
    assert clone_resp.status_code == 200
    assert clone_resp.json()["title"].startswith("Copie -")


def _assert_suggest_paths(client, helpers, owner_token: str) -> None:
    """Asserts that suggest paths holds."""
    suggest_with_city = client.post(
        "/api/organizer/events/suggest",
        json={"title": "Covered Duplicate Title", "description": "desc", "city": "Iasi", "location": "Hall"},
        headers=helpers["auth_header"](owner_token),
    )
    assert suggest_with_city.status_code == 200
    assert suggest_with_city.json()["suggested_city"] == "Iasi"

    suggest_without_tokens = client.post(
        "/api/organizer/events/suggest",
        json={"title": "!!!", "description": "desc", "city": "Cluj", "location": "Hall"},
        headers=helpers["auth_header"](owner_token),
    )
    assert suggest_without_tokens.status_code == 200
    assert suggest_without_tokens.json()["duplicates"] == []


def test_restore_clone_and_suggest_cover_plain_organizer_paths(helpers):
    """Verifies restore clone and suggest cover plain organizer paths behavior."""
    client, admin_token, owner_token, restore_event, future_clone = _seed_restore_and_clone_context(helpers)
    _assert_restore_and_clone_paths(client, helpers, admin_token, owner_token, restore_event, future_clone)
    _assert_suggest_paths(client, helpers, owner_token)


def test_forgot_password_uses_stored_language_preference(helpers, monkeypatch):
    """Verifies forgot password uses stored language preference behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["register_student"]("partial-notifications@test.ro")
    existing_user = db.query(models.User).filter(models.User.email == "partial-notifications@test.ro").first()
    assert existing_user is not None
    existing_user.language_preference = "en"
    db.add(existing_user)
    db.commit()

    forgot_langs: list[str] = []
    monkeypatch.setattr(api.settings, "allowed_origins", ["https://frontend.test"], raising=False)
    monkeypatch.setattr(
        api,
        "render_password_reset_email",
        lambda user, link, *, lang: forgot_langs.append(lang) or ("subject", link, "<p>html</p>"),
    )
    missing_user_resp = client.post("/password/forgot", json={"email": "ghost-user@test.ro"})
    assert missing_user_resp.status_code == 200

    forgot_resp = client.post(
        "/password/forgot",
        json={"email": "partial-notifications@test.ro"},
        headers={"Accept-Language": "ro"},
    )
    assert forgot_resp.status_code == 200
    assert forgot_langs == ["en"]


def test_update_event_allows_blank_cover_url_without_content_recompute(helpers):
    """Verifies update event allows blank cover url without content recompute behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("blank-cover-org@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("blank-cover-org@test.ro", "organizer-fixture-A1")
    created = client.post(
        "/api/events",
        json=event_payload(
            helpers["future_time"](days=3),
            title="Blank Cover Event",
            cover_url="https://example.com/cover.png",
        ),
        headers=auth_header(organizer_token),
    )
    assert created.status_code == 201

    updated = client.put(
        f"/api/events/{created.json()['id']}",
        json={"cover_url": "", "max_seats": 11},
        headers=auth_header(organizer_token),
    )
    assert updated.status_code == 200
    assert updated.json()["cover_url"] == ""
    assert updated.json()["max_seats"] == 11


def test_organizer_suggest_event_skips_date_filter_when_normalized_start_is_none(helpers, monkeypatch):
    """Verifies organizer suggest event skips date filter when normalized start is none behavior."""
    db = helpers["db"]
    helpers["make_organizer"]("suggest-direct@test.ro", "organizer-fixture-A1")
    organizer = db.query(models.User).filter(models.User.email == "suggest-direct@test.ro").first()
    assert organizer is not None

    monkeypatch.setattr(api, "_normalize_dt", lambda _value: None)
    result = api.organizer_suggest_event(
        payload=schemas.EventSuggestRequest.model_construct(
            title="Direct Suggest Coverage",
            description="desc",
            city="Cluj",
            location="Hall",
            start_time=datetime.now(timezone.utc),
        ),
        db=db,
        current_user=organizer,
    )

    assert result.suggested_city == "Cluj"


def test_recommendation_reason_map_empty_and_invalid_dwell_seconds_do_not_query_db():
    """Verifies recommendation reason map empty and invalid dwell seconds do not query db behavior."""
    class _NoQueryDb:
        """No Query Db value object used in the surrounding module."""
        @staticmethod
        def query(*_args, **_kwargs):
            """Implements the query helper."""
            raise AssertionError("query should not run")

    assert api._recommendation_reason_map(db=_NoQueryDb(), user_id=1, event_ids=[]) == {}
    assert api._event_learning_delta(interaction_type="dwell", meta={"seconds": "slow"}) == pytest.approx(0.0)
    with pytest.raises(AssertionError, match="query should not run"):
        _NoQueryDb().query()
