from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import Request
import pytest

from app import api, models, schemas


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _event_payload(start_time: str, **overrides):
    payload = {
        "title": "Coverage Event",
        "description": "desc",
        "category": "Edu",
        "start_time": start_time,
        "city": "Cluj",
        "location": "Hall",
        "max_seats": 10,
        "tags": ["alpha"],
    }
    payload.update(overrides)
    return payload


class _ScalarQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *_args, **_kwargs):
        return self

    def scalar(self):
        return self._value


class _ScalarDb:
    def __init__(self, value):
        self._value = value

    def query(self, *_args, **_kwargs):
        return _ScalarQuery(self._value)


def test_serializers_cache_fresh_and_create_event_optional_start_time(monkeypatch):
    event = models.Event(
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

    serialized = api._serialize_event(event, seats_taken=0)
    public_serialized = api._serialize_public_event(event, seats_taken=0)
    admin_serialized = api._serialize_admin_event(event, seats_taken=0)
    assert serialized.owner_name is None
    assert public_serialized.organizer_name is None
    assert admin_serialized.owner_name is None
    assert admin_serialized.owner_email == "unknown@example.com"

    now = datetime.now(timezone.utc)
    assert api._recommendations_cache_is_fresh(db=_ScalarDb(now), user_id=1, now=now) is True
    assert api._recommendations_cache_is_fresh(db=_ScalarDb(now.replace(tzinfo=None)), user_id=1, now=now) is True

    monkeypatch.setattr(api, "_attach_tags", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "_compute_moderation", lambda **_kwargs: (0.0, [], "clean"))
    monkeypatch.setattr(api, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(api, "_serialize_event", lambda event, seats_taken=0, recommendation_reason=None: SimpleNamespace(id=event.id, start_time=event.start_time))

    class _CreateDb:
        def add(self, _obj):
            return None

        def commit(self):
            return None

        def refresh(self, obj):
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


def test_events_and_public_events_include_past_and_optional_detail_user(helpers):
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


def test_explicit_language_paths_for_lists_detail_recommendations_and_registration(helpers, monkeypatch):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("lang-owner@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("lang-owner@test.ro", "organizer-fixture-A1")

    first = client.post(
        "/api/events",
        json=_event_payload(helpers["future_time"](days=2), title="Explicit Language First"),
        headers=helpers["auth_header"](organizer_token),
    )
    second = client.post(
        "/api/events",
        json=_event_payload(helpers["future_time"](days=3), title="Explicit Language Second"),
        headers=helpers["auth_header"](organizer_token),
    )
    register_target = client.post(
        "/api/events",
        json=_event_payload(helpers["future_time"](days=4), title="Register Language"),
        headers=helpers["auth_header"](organizer_token),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert register_target.status_code == 201

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
                event_id=int(second.json()["id"]),
                rank=1,
                score=0.9,
                reason="explicit-cache",
                model_version="v1",
                generated_at=datetime.now(timezone.utc),
            ),
            models.UserRecommendation(
                user_id=int(student.id),
                event_id=int(first.json()["id"]),
                rank=2,
                score=0.8,
                reason="fallback-cache",
                model_version="v1",
                generated_at=datetime.now(timezone.utc),
            ),
        ]
    )
    db.commit()

    langs: list[str] = []
    monkeypatch.setattr(
        api,
        "render_registration_email",
        lambda event, user, *, lang: langs.append(lang) or ("subject", "body", "<p>body</p>"),
    )

    sorted_resp = client.get(
        "/api/events",
        params={"sort": "recommended", "include_past": "true"},
        headers={**_auth_header(student_token), "Accept-Language": "ro"},
    )
    assert sorted_resp.status_code == 200
    assert sorted_resp.json()["items"][0]["id"] == second.json()["id"]
    assert sorted_resp.json()["items"][0]["recommendation_reason"].startswith("explicit-cache")

    detail_resp = client.get(
        f"/api/events/{second.json()['id']}",
        headers={**_auth_header(student_token), "Accept-Language": "ro"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["recommendation_reason"].startswith("explicit-cache")

    recommendations_resp = client.get(
        "/api/recommendations",
        headers={**_auth_header(student_token), "Accept-Language": "ro"},
    )
    assert recommendations_resp.status_code == 200

    register_resp = client.post(
        f"/api/events/{register_target.json()['id']}/register",
        headers={**_auth_header(student_token), "Accept-Language": "ro"},
    )
    assert register_resp.status_code == 201
    resend_resp = client.post(
        f"/api/events/{register_target.json()['id']}/register/resend",
        headers={**helpers["auth_header"](student_token), "Accept-Language": "ro"},
    )
    assert resend_resp.status_code == 200
    assert langs == ["en", "en"]


def test_update_notifications_delete_reuse_placeholder_restore_clone_suggest_and_forgot_password(helpers, monkeypatch):
    client = helpers["client"]
    db = helpers["db"]

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

    helpers["make_organizer"]("delete-owner-a@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("delete-owner-b@test.ro", "other-fixture-A1")
    token_a = helpers["login"]("delete-owner-a@test.ro", "owner-fixture-A1")
    token_b = helpers["login"]("delete-owner-b@test.ro", "other-fixture-A1")

    for idx, token in enumerate((token_a, token_b), start=1):
            created = client.post(
                "/api/events",
                json=_event_payload(helpers["future_time"](days=idx + 2), title=f"Delete Event {idx}"),
                headers=_auth_header(token),
            )
            assert created.status_code == 201
            deleted = client.request(
                "DELETE",
                "/api/me",
                json={"password": "owner-fixture-A1" if idx == 1 else "other-fixture-A1"},
                headers=_auth_header(token),
            )
            assert deleted.status_code == 200

    placeholders = db.query(models.User).filter(models.User.email == "deleted-organizer@eventlink.invalid").all()
    assert len(placeholders) == 1

    helpers["make_admin"]("restore-admin@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("restore-admin@test.ro", "admin-fixture-A1")
    helpers["make_organizer"]("restore-plain-owner@test.ro", "restore-fixture-A1")
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
    db.add(restore_event)
    db.commit()
    db.refresh(restore_event)
    restore_resp = client.post(
        f"/api/events/{int(restore_event.id)}/restore",
        headers=helpers["auth_header"](admin_token),
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["restored_registrations"] == 0

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
    db.add(future_clone)
    db.commit()
    db.refresh(future_clone)
    clone_resp = client.post(
        f"/api/events/{int(future_clone.id)}/clone",
        headers=helpers["auth_header"](helpers["login"]("restore-plain-owner@test.ro", "restore-fixture-A1")),
    )
    assert clone_resp.status_code == 200
    assert clone_resp.json()["title"].startswith("Copie -")

    suggest_with_city = client.post(
        "/api/organizer/events/suggest",
        json={"title": "Covered Duplicate Title", "description": "desc", "city": "Iasi", "location": "Hall"},
        headers=helpers["auth_header"](helpers["login"]("restore-plain-owner@test.ro", "restore-fixture-A1")),
    )
    assert suggest_with_city.status_code == 200
    assert suggest_with_city.json()["suggested_city"] == "Iasi"

    suggest_without_tokens = client.post(
        "/api/organizer/events/suggest",
        json={"title": "!!!", "description": "desc", "city": "Cluj", "location": "Hall"},
        headers=helpers["auth_header"](helpers["login"]("restore-plain-owner@test.ro", "restore-fixture-A1")),
    )
    assert suggest_without_tokens.status_code == 200
    assert suggest_without_tokens.json()["duplicates"] == []

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


def test_record_interactions_refresh_interval_with_aware_cache_enqueues(monkeypatch):
    request = Request({"type": "http", "method": "POST", "path": "/api/analytics/interactions", "headers": []})
    current_user = SimpleNamespace(id=5, role=models.UserRole.student)
    payload = schemas.InteractionBatchIn.model_validate({"events": [{"interaction_type": "click", "event_id": 7}]})
    now = datetime.now(timezone.utc)
    captured_jobs: list[tuple[str, dict, str | None]] = []

    class _RowsQuery:
        def __init__(self, *, rows=None, scalar_value=None):
            self._rows = rows if rows is not None else []
            self._scalar_value = scalar_value

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return list(self._rows)

        def scalar(self):
            return self._scalar_value

    class _RefreshDb:
        def __init__(self):
            self._queries = [
                _RowsQuery(rows=[(7,)]),
                _RowsQuery(scalar_value=now - timedelta(hours=2)),
            ]
            self.interactions = []

        def query(self, *_args, **_kwargs):
            return self._queries.pop(0)

        def add_all(self, rows):
            self.interactions.extend(rows)

        def commit(self):
            return None

    import app.task_queue as task_queue_module

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", False, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_min_interval_seconds", 60, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_top_n", 9, raising=False)
    monkeypatch.setattr(api, "_enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        task_queue_module,
        "enqueue_job",
        lambda _db, job_type, payload, dedupe_key=None: captured_jobs.append((job_type, payload, dedupe_key)),
    )

    db = _RefreshDb()
    api.record_interactions(payload=payload, request=request, db=db, current_user=current_user)

    assert len(db.interactions) == 1
    assert captured_jobs == [("refresh_user_recommendations_ml", {"user_id": 5, "top_n": 9, "skip_training": True}, "5")]


def test_record_interactions_search_only_invalid_meta_skips_event_lookup_and_learning_updates(helpers, monkeypatch):
    client = helpers["client"]
    db = helpers["db"]
    student_token = helpers["register_student"]("invalid-search-only@test.ro")
    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", False, raising=False)

    resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "search", "meta": {"tags": "python", "category": "   ", "city": "   "}}]},
        headers=_auth_header(student_token),
    )

    assert resp.status_code == 204
    assert db.query(models.EventInteraction).count() == 1
    assert db.query(models.UserImplicitInterestTag).count() == 0
    assert db.query(models.UserImplicitInterestCategory).count() == 0
    assert db.query(models.UserImplicitInterestCity).count() == 0


def test_record_interactions_updates_aware_implicit_rows_without_realtime_refresh(helpers, monkeypatch):
    client = helpers["client"]
    db = helpers["db"]
    token = helpers["register_student"]("aware-implicit@test.ro")
    student = db.query(models.User).filter(models.User.email == "aware-implicit@test.ro").first()
    assert student is not None

    tag = models.Tag(name="aware-tag")
    db.add(tag)
    db.commit()
    db.refresh(tag)

    future_seen = datetime.now(timezone.utc) + timedelta(hours=1)
    db.add_all(
        [
            models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(tag.id), score=1.0, last_seen_at=future_seen),
            models.UserImplicitInterestCategory(user_id=int(student.id), category="tech", score=1.0, last_seen_at=future_seen),
            models.UserImplicitInterestCity(user_id=int(student.id), city="cluj", score=1.0, last_seen_at=future_seen),
        ]
    )
    db.commit()

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", False, raising=False)

    resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "search", "meta": {"tags": ["aware-tag"], "category": "Tech", "city": "Cluj"}}]},
        headers=_auth_header(token),
    )

    assert resp.status_code == 204
    tag_row = db.query(models.UserImplicitInterestTag).filter(models.UserImplicitInterestTag.user_id == int(student.id)).first()
    category_row = db.query(models.UserImplicitInterestCategory).filter(models.UserImplicitInterestCategory.user_id == int(student.id)).first()
    city_row = db.query(models.UserImplicitInterestCity).filter(models.UserImplicitInterestCity.user_id == int(student.id)).first()
    assert tag_row is not None and float(tag_row.score or 0.0) >= 1.0
    assert category_row is not None and float(category_row.score or 0.0) >= 1.0
    assert city_row is not None and float(city_row.score or 0.0) >= 1.0


def test_record_interactions_low_signal_payload_does_not_trigger_realtime_refresh(helpers, monkeypatch):
    db = helpers["db"]
    helpers["make_organizer"]("no-refresh-org@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("no-refresh-org@test.ro", "organizer-fixture-A1")
    event_resp = helpers["client"].post(
        "/api/events",
        json=_event_payload(helpers["future_time"](days=2), title="No Refresh Event"),
        headers=_auth_header(organizer_token),
    )
    assert event_resp.status_code == 201

    helpers["register_student"]("no-refresh-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "no-refresh-student@test.ro").first()
    assert student is not None
    jobs: list[tuple[str, dict, str | None]] = []
    import app.task_queue as task_queue_module

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_min_interval_seconds", 0, raising=False)
    monkeypatch.setattr(
        task_queue_module,
        "enqueue_job",
        lambda _db, job_type, payload, dedupe_key=None: jobs.append((job_type, payload, dedupe_key)),
    )
    request = Request({"type": "http", "method": "POST", "path": "/api/analytics/interactions", "headers": []})
    payload = schemas.InteractionBatchIn.model_construct(
        events=[
            schemas.InteractionEventIn.model_construct(
                interaction_type="impression",
                event_id=event_resp.json()["id"],
                meta={"source": "events_list"},
            ),
            schemas.InteractionEventIn.model_construct(
                interaction_type="dwell",
                event_id=event_resp.json()["id"],
                meta="bad-meta",
            ),
            schemas.InteractionEventIn.model_construct(
                interaction_type="dwell",
                event_id=event_resp.json()["id"],
                meta={"seconds": 1},
            ),
        ]
    )

    api.record_interactions(payload=payload, request=request, db=db, current_user=student)
    assert jobs == []


def test_update_event_allows_blank_cover_url_without_content_recompute(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("blank-cover-org@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("blank-cover-org@test.ro", "organizer-fixture-A1")
    created = client.post(
        "/api/events",
        json=_event_payload(
            helpers["future_time"](days=3),
            title="Blank Cover Event",
            cover_url="https://example.com/cover.png",
        ),
        headers=_auth_header(organizer_token),
    )
    assert created.status_code == 201

    updated = client.put(
        f"/api/events/{created.json()['id']}",
        json={"cover_url": "", "max_seats": 11},
        headers=_auth_header(organizer_token),
    )
    assert updated.status_code == 200
    assert updated.json()["cover_url"] == ""
    assert updated.json()["max_seats"] == 11


def test_organizer_suggest_event_skips_date_filter_when_normalized_start_is_none(helpers, monkeypatch):
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


def test_record_interactions_direct_fake_db_covers_aware_rows(monkeypatch):
    aware_seen = datetime.now(timezone.utc) + timedelta(hours=1)

    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return list(self._rows)

    class _FakeDb:
        def __init__(self):
            self._queries = [
                _Query([(1, "aware-tag")]),
                _Query([SimpleNamespace(tag_id=1, last_seen_at=aware_seen, score=1.0)]),
                _Query([SimpleNamespace(category="tech", last_seen_at=aware_seen, score=1.0)]),
                _Query([SimpleNamespace(city="cluj", last_seen_at=aware_seen, score=1.0)]),
            ]
            self.interactions = []
            self.added = []
            self.commits = 0

        def query(self, *_args, **_kwargs):
            return self._queries.pop(0)

        def add_all(self, rows):
            self.interactions.extend(rows)

        def add(self, row):
            self.added.append(row)

        def commit(self):
            self.commits += 1

    request = Request({"type": "http", "method": "POST", "path": "/api/analytics/interactions", "headers": []})
    payload = schemas.InteractionBatchIn.model_validate(
        {"events": [{"interaction_type": "search", "meta": {"tags": ["aware-tag"], "category": "Tech", "city": "Cluj"}}]}
    )
    current_user = SimpleNamespace(id=1, role=models.UserRole.student)
    fake_db = _FakeDb()

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", False, raising=False)
    monkeypatch.setattr(api, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))

    api.record_interactions(payload=payload, request=request, db=fake_db, current_user=current_user)

    assert len(fake_db.interactions) == 1
    assert fake_db.commits == 2


def test_recommendation_reason_map_empty_and_invalid_dwell_seconds_do_not_query_db():
    class _NoQueryDb:
        def query(self, *_args, **_kwargs):
            raise AssertionError("query should not run")

    assert api._recommendation_reason_map(db=_NoQueryDb(), user_id=1, event_ids=[]) == {}
    assert api._event_learning_delta(interaction_type="dwell", meta={"seconds": "slow"}) == pytest.approx(0.0)
    with pytest.raises(AssertionError, match="query should not run"):
        _NoQueryDb().query()


def test_online_learning_and_realtime_refresh_guard_returns(monkeypatch):
    class _GuardDb:
        def query(self, *_args, **_kwargs):
            raise AssertionError("query should not run")

        def commit(self):
            raise AssertionError("commit should not run")

    payload = schemas.InteractionBatchIn.model_validate(
        {"events": [{"interaction_type": "click", "event_id": 1}]}
    )
    now = datetime.now(timezone.utc)
    guard_db = _GuardDb()

    api._apply_online_learning(
        db=guard_db,
        payload=payload,
        current_user=None,
        now=now,
    )
    api._apply_online_learning(
        db=guard_db,
        payload=payload,
        current_user=SimpleNamespace(role=models.UserRole.organizator),
        now=now,
    )

    monkeypatch.setattr(api.settings, "task_queue_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_enabled", False, raising=False)

    api._maybe_enqueue_realtime_recommendation_refresh(
        db=guard_db,
        payload=payload,
        current_user=None,
        now=now,
    )
    api._maybe_enqueue_realtime_recommendation_refresh(
        db=guard_db,
        payload=payload,
        current_user=SimpleNamespace(id=1, role=models.UserRole.organizator),
        now=now,
    )
    api._maybe_enqueue_realtime_recommendation_refresh(
        db=guard_db,
        payload=payload,
        current_user=SimpleNamespace(id=1, role=models.UserRole.student),
        now=now,
    )
    with pytest.raises(AssertionError, match="query should not run"):
        guard_db.query()
    with pytest.raises(AssertionError, match="commit should not run"):
        guard_db.commit()
