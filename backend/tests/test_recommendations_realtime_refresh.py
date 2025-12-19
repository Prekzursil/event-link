from datetime import datetime, timedelta, timezone

from app import api as api_module, auth, models


def _set_setting(obj, name: str, value):  # noqa: ANN001
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def test_interactions_enqueues_refresh_job_when_enabled_and_dedupes(helpers):
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-realtime@test.ro")
    student = db.query(models.User).filter(models.User.email == "student-realtime@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="org-realtime@test.ro",
        password_hash=auth.get_password_hash("organizer123"),
        role=models.UserRole.organizator,
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)

    event = models.Event(
        title="Realtime Event",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner_id=int(organizer.id),
        status="published",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

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

        jobs = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.job_type == "refresh_user_recommendations_ml")
            .all()
        )
        assert len(jobs) == 1
        assert jobs[0].payload["user_id"] == int(student.id)
        assert jobs[0].payload["skip_training"] is True

        resp2 = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp2.status_code == 204

        jobs2 = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.job_type == "refresh_user_recommendations_ml")
            .all()
        )
        assert len(jobs2) == 1
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)


def test_interactions_respects_realtime_refresh_min_interval(helpers):
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-interval@test.ro")
    student = db.query(models.User).filter(models.User.email == "student-interval@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="org-interval@test.ro",
        password_hash=auth.get_password_hash("organizer123"),
        role=models.UserRole.organizator,
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)

    event = models.Event(
        title="Interval Event",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner_id=int(organizer.id),
        status="published",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

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

        jobs = (
            db.query(models.BackgroundJob)
            .filter(models.BackgroundJob.job_type == "refresh_user_recommendations_ml")
            .all()
        )
        assert jobs == []
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)

