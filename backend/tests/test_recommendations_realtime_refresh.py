from datetime import datetime, timedelta, timezone

from app import api as api_module, auth, models


def _set_setting(obj, name: str, value):  # noqa: ANN001
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def _create_realtime_fixture(helpers, *, slug: str, title: str):
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"](f"student-{slug}@test.ro")
    student = db.query(models.User).filter(models.User.email == f"student-{slug}@test.ro").first()
    assert student is not None

    organizer = models.User(
        email=f"org-{slug}@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    event = models.Event(
        title=title,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner=organizer,
        status="published",
    )
    db.add_all([organizer, event])
    db.commit()
    db.refresh(event)
    return client, db, token, student, event


def _refresh_jobs(db):
    return (
        db.query(models.BackgroundJob).filter(models.BackgroundJob.job_type == "refresh_user_recommendations_ml").all()
    )


def test_interactions_enqueues_refresh_job_when_enabled_and_dedupes(helpers):
    client, db, token, student, event = _create_realtime_fixture(
        helpers,
        slug="realtime",
        title="Realtime Event",
    )

    originals = {}
    try:
        originals["task_queue_enabled"] = _set_setting(api_module.settings, "task_queue_enabled", True)
        originals["recommendations_realtime_refresh_enabled"] = _set_setting(
            api_module.settings, "recommendations_realtime_refresh_enabled", True
        )
        originals["recommendations_realtime_refresh_min_interval_seconds"] = _set_setting(
            api_module.settings, "recommendations_realtime_refresh_min_interval_seconds", 0
        )

        resp = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp.status_code == 204

        jobs = _refresh_jobs(db)
        assert len(jobs) == 1
        assert jobs[0].payload["user_id"] == int(student.id)
        assert jobs[0].payload["skip_training"] is True

        resp2 = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp2.status_code == 204

        assert len(_refresh_jobs(db)) == 1
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)


def test_interactions_respects_realtime_refresh_min_interval(helpers):
    client, db, token, student, event = _create_realtime_fixture(
        helpers,
        slug="interval",
        title="Interval Event",
    )

    db.add(
        models.UserRecommendation(
            user_id=int(student.id),
            event_id=int(event.id),
            score=0.9,
            rank=1,
            model_version="test-model",
            generated_at=datetime.now(timezone.utc),
            reason="test",
        )
    )
    db.commit()

    originals = {}
    try:
        originals["task_queue_enabled"] = _set_setting(api_module.settings, "task_queue_enabled", True)
        originals["recommendations_realtime_refresh_enabled"] = _set_setting(
            api_module.settings, "recommendations_realtime_refresh_enabled", True
        )
        originals["recommendations_realtime_refresh_min_interval_seconds"] = _set_setting(
            api_module.settings, "recommendations_realtime_refresh_min_interval_seconds", 3600
        )

        resp = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp.status_code == 204

        assert _refresh_jobs(db) == []
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)
