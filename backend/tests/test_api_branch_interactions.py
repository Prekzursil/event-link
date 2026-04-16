from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import Request
import pytest

from api_branch_extra_helpers import api, auth_header, event_payload, models, schemas


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

        @staticmethod
        def commit():
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
    assert captured_jobs == [
        ("refresh_user_recommendations_ml", {"user_id": 5, "top_n": 9, "skip_training": True}, "5")
    ]


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
        headers=auth_header(student_token),
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
            models.UserImplicitInterestTag(
                user_id=int(student.id), tag_id=int(tag.id), score=1.0, last_seen_at=future_seen
            ),
            models.UserImplicitInterestCategory(
                user_id=int(student.id), category="tech", score=1.0, last_seen_at=future_seen
            ),
            models.UserImplicitInterestCity(user_id=int(student.id), city="cluj", score=1.0, last_seen_at=future_seen),
        ]
    )
    db.commit()

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", False, raising=False)

    resp = client.post(
        "/api/analytics/interactions",
        json={
            "events": [
                {"interaction_type": "search", "meta": {"tags": ["aware-tag"], "category": "Tech", "city": "Cluj"}}
            ]
        },
        headers=auth_header(token),
    )

    assert resp.status_code == 204
    tag_row = (
        db.query(models.UserImplicitInterestTag)
        .filter(models.UserImplicitInterestTag.user_id == int(student.id))
        .first()
    )
    category_row = (
        db.query(models.UserImplicitInterestCategory)
        .filter(models.UserImplicitInterestCategory.user_id == int(student.id))
        .first()
    )
    city_row = (
        db.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == int(student.id))
        .first()
    )
    assert tag_row is not None and float(tag_row.score or 0.0) >= 1.0
    assert category_row is not None and float(category_row.score or 0.0) >= 1.0
    assert city_row is not None and float(city_row.score or 0.0) >= 1.0


def test_record_interactions_low_signal_payload_does_not_trigger_realtime_refresh(helpers, monkeypatch):
    db = helpers["db"]
    helpers["make_organizer"]("no-refresh-org@test.ro", "organizer-fixture-A1")
    organizer_token = helpers["login"]("no-refresh-org@test.ro", "organizer-fixture-A1")
    event_resp = helpers["client"].post(
        "/api/events",
        json=event_payload(helpers["future_time"](days=2), title="No Refresh Event"),
        headers=auth_header(organizer_token),
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
        {
            "events": [
                {"interaction_type": "search", "meta": {"tags": ["aware-tag"], "category": "Tech", "city": "Cluj"}}
            ]
        }
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
        @staticmethod
        def query(*_args, **_kwargs):
            raise AssertionError("query should not run")

    assert api._recommendation_reason_map(db=_NoQueryDb(), user_id=1, event_ids=[]) == {}
    assert api._event_learning_delta(interaction_type="dwell", meta={"seconds": "slow"}) == pytest.approx(0.0)
    with pytest.raises(AssertionError, match="query should not run"):
        _NoQueryDb().query()


def test_online_learning_and_realtime_refresh_guard_returns(monkeypatch):
    class _GuardDb:
        @staticmethod
        def query(*_args, **_kwargs):
            raise AssertionError("query should not run")

        @staticmethod
        def commit():
            raise AssertionError("commit should not run")

    payload = schemas.InteractionBatchIn.model_validate({"events": [{"interaction_type": "click", "event_id": 1}]})
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
