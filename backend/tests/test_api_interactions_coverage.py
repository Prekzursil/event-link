"""Interaction analytics tests split out of test_api_helper_coverage for size."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from datetime import timedelta

from app import api, auth, models


def _configure_record_interactions_settings(monkeypatch) -> None:
    """Enable analytics and realtime-learning settings for interaction tests."""
    for name, value in (
        ("analytics_enabled", True),
        ("recommendations_online_learning_enabled", True),
        ("recommendations_online_learning_dwell_threshold_seconds", 10),
        ("recommendations_online_learning_max_score", 10.0),
        ("task_queue_enabled", True),
        ("recommendations_use_ml_cache", True),
        ("recommendations_realtime_refresh_enabled", True),
    ):
        monkeypatch.setattr(api.settings, name, value)


def _record_interactions_payload(event_id: int) -> dict:
    """Build a mixed interaction payload that hits the helper edge branches."""
    return {
        "events": [
            {"interaction_type": "click", "event_id": 999999},
            {"interaction_type": "view", "event_id": event_id},
            {"interaction_type": "share", "event_id": event_id},
            {"interaction_type": "favorite", "event_id": event_id},
            {"interaction_type": "register", "event_id": event_id},
            {
                "interaction_type": "dwell",
                "event_id": event_id,
                "meta": {"seconds": 20},
            },
            {
                "interaction_type": "search",
                "meta": {
                    "tags": ["analytics-visible", "", None],
                    "category": "Tech",
                    "city": "Bucuresti",
                },
            },
            {
                "interaction_type": "filter",
                "meta": {
                    "tags": ["analytics-visible"],
                    "category": "Tech",
                    "city": "Bucuresti",
                },
            },
            {
                "interaction_type": "click",
                "event_id": event_id,
                "occurred_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            },
        ]
    }


def _seed_implicit_interest_rows(db, student_id: int, visible_tag_id: int) -> None:
    """Seeds implicit-interest tag/category/city rows for a student."""
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    for row in (
        models.UserImplicitInterestTag(
            user_id=student_id,
            tag_id=visible_tag_id,
            score=1.0,
            last_seen_at=now_naive,
        ),
        models.UserImplicitInterestCategory(
            user_id=student_id,
            category="tech",
            score=1.0,
            last_seen_at=now_naive,
        ),
        models.UserImplicitInterestCity(
            user_id=student_id,
            city="bucuresti",
            score=1.0,
            last_seen_at=now_naive,
        ),
    ):
        db.add(row)
    db.commit()


def _seed_record_interactions_context(helpers, monkeypatch):
    """Create an interaction-heavy fixture set for analytics helper coverage."""
    client = helpers["client"]
    db = helpers["db"]
    student_token = helpers["register_student"]("interactions@test.ro")
    student = (
        db.query(models.User)
        .filter(models.User.email == "interactions@test.ro")
        .first()
    )
    assert student is not None
    organizer = models.User(
        email="interactions-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    visible_tag = models.Tag(name="analytics-visible")
    hidden_tag = models.Tag(name="analytics-hidden")
    event = models.Event(
        title="Interaction Event",
        description="desc",
        category="Tech",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Bucuresti",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    event.tags.extend([visible_tag, hidden_tag])
    db.add_all([organizer, visible_tag, hidden_tag, event])
    db.commit()
    db.execute(
        models.user_hidden_tags.insert().values(
            user_id=int(student.id), tag_id=int(hidden_tag.id)
        )
    )
    _seed_implicit_interest_rows(db, int(student.id), int(visible_tag.id))
    _configure_record_interactions_settings(monkeypatch)
    captured_jobs: list[tuple[str, dict, str | None]] = []
    import app.task_queue as tq

    def _capture_enqueue_job(_db, job_type, payload, dedupe_key=None):
        """Capture queued jobs while returning a deterministic queued response."""
        captured_jobs.append((job_type, payload, dedupe_key))
        return SimpleNamespace(id=77, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _capture_enqueue_job)
    return SimpleNamespace(
        client=client,
        db=db,
        student=student,
        student_token=student_token,
        visible_tag=visible_tag,
        hidden_tag=hidden_tag,
        event=event,
        payload=_record_interactions_payload(int(event.id)),
        captured_jobs=captured_jobs,
    )


def _assert_implicit_rows_present(context) -> None:
    """Asserts that the student's visible-tag/category/city rows are live."""
    refreshed_tag = (
        context.db.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == int(context.student.id),
            models.UserImplicitInterestTag.tag_id == int(context.visible_tag.id),
        )
        .first()
    )
    assert refreshed_tag is not None
    assert float(refreshed_tag.score or 0.0) > 1.0
    hidden_row = (
        context.db.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == int(context.student.id),
            models.UserImplicitInterestTag.tag_id == int(context.hidden_tag.id),
        )
        .first()
    )
    assert hidden_row is None
    cat_row = (
        context.db.query(models.UserImplicitInterestCategory)
        .filter(models.UserImplicitInterestCategory.user_id == int(context.student.id))
        .first()
    )
    city_row = (
        context.db.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == int(context.student.id))
        .first()
    )
    assert cat_row is not None and float(cat_row.score or 0.0) > 1.0
    assert city_row is not None and float(city_row.score or 0.0) > 1.0


def test_record_interactions_updates_scores_and_skips_hidden_tags(monkeypatch, helpers):
    """Interaction recording should update visible interests and skip hidden tags."""
    context = _seed_record_interactions_context(helpers, monkeypatch)
    response = context.client.post(
        "/api/analytics/interactions",
        json=context.payload,
        headers=helpers["auth_header"](context.student_token),
    )
    assert response.status_code == 204
    _assert_implicit_rows_present(context)


def test_record_interactions_enqueues_refresh_job(monkeypatch, helpers):
    """Interaction recording should enqueue a refresh job when realtime is enabled."""
    context = _seed_record_interactions_context(helpers, monkeypatch)
    response = context.client.post(
        "/api/analytics/interactions",
        json=context.payload,
        headers=helpers["auth_header"](context.student_token),
    )
    assert response.status_code == 204
    assert any(
        job_type == "refresh_user_recommendations_ml"
        for job_type, _payload, _dedupe in context.captured_jobs
    )


def test_record_interactions_disabled_and_empty_paths(monkeypatch, helpers):
    """Interaction recording should no-op when analytics or learning is disabled."""
    client = helpers["client"]
    db = helpers["db"]

    student_token = helpers["register_student"]("interactions-empty@test.ro")

    monkeypatch.setattr(api.settings, "analytics_enabled", False)
    disabled_resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "click", "event_id": 12345}]},
        headers=helpers["auth_header"](student_token),
    )
    assert disabled_resp.status_code == 204

    monkeypatch.setattr(api.settings, "analytics_enabled", True)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", False)
    empty_resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "click", "event_id": 12345}]},
        headers=helpers["auth_header"](student_token),
    )
    assert empty_resp.status_code == 204

    stored = db.query(models.EventInteraction).count()
    assert stored == 0
