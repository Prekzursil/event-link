"""Tests for the ml v2 online learning and guardrails behavior."""

from datetime import datetime, timedelta, timezone

from app import api as api_module, auth, models
from app.task_queue import enqueue_job, _evaluate_personalization_guardrails


def _set_setting(obj, name: str, value):  # noqa: ANN001
    """Sets the setting value."""
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def _guardrails_models():
    """Implements the guardrails models helper."""
    older = models.RecommenderModel(
        model_version="old",
        feature_names=["bias"],
        weights=[0.0],
        meta={"hitrate_at_10": 0.1},
        is_active=False,
    )
    active = models.RecommenderModel(
        model_version="new",
        feature_names=["bias"],
        weights=[0.0],
        meta={"hitrate_at_10": 0.1},
        is_active=True,
    )
    return older, active


def _guardrails_users_and_events():
    """Implements the guardrails users and events helper."""
    user = models.User(
        email="guardrails@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
    )
    org = models.User(
        email="org-guard@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    events = [
        models.Event(
            title=title,
            start_time=datetime.now(timezone.utc) + timedelta(days=offset),
            owner=org,
            status="published",
        )
        for offset, title in (
            (1, "Time Event"),
            (2, "Time Event 2"),
            (3, "Recommended Event"),
        )
    ]
    return user, org, events


def _seed_guardrails_interactions(db, *, user_id: int, events) -> None:
    """Implements the seed guardrails interactions helper."""
    now = datetime.now(timezone.utc)
    repeated_impressions = [
        models.EventInteraction(
            user_id=user_id,
            event_id=int(event.id),
            interaction_type="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": sort, "position": 0},
        )
        for event, sort in ((events[0], "time"), (events[2], "recommended"))
        for _ in range(10)
    ]
    db.add_all(
        [
            *repeated_impressions,
            models.EventInteraction(
                user_id=user_id,
                event_id=int(events[0].id),
                interaction_type="click",
                occurred_at=now,
                meta={"source": "events_list", "sort": "time"},
            ),
            models.EventInteraction(
                user_id=user_id,
                event_id=int(events[1].id),
                interaction_type="click",
                occurred_at=now,
                meta={"source": "events_list", "sort": "time"},
            ),
            models.EventInteraction(
                user_id=user_id,
                event_id=int(events[0].id),
                interaction_type="register",
                occurred_at=now + timedelta(minutes=5),
                meta={"source": "event_detail"},
            ),
        ]
    )
    db.commit()


def _prepare_guardrails_rollback_fixture(helpers):
    """Implements the prepare guardrails rollback fixture helper."""
    db = helpers["db"]
    older, active = _guardrails_models()
    user, org, events = _guardrails_users_and_events()
    db.add_all([older, active, user, org, *events])
    db.commit()
    db.refresh(user)
    for event in events:
        db.refresh(event)
    _seed_guardrails_interactions(db, user_id=int(user.id), events=events)
    return db


def _run_guardrails_rollback(db):
    """Runs the guardrails rollback helper path."""
    originals = {}
    try:
        originals["personalization_guardrails_enabled"] = _set_setting(
            api_module.settings,
            "personalization_guardrails_enabled",
            True,
        )
        return _evaluate_personalization_guardrails(
            db=db,
            payload={
                "days": 1,
                "min_impressions": 5,
                "ctr_drop_ratio": 0.1,
                "conversion_drop_ratio": 0.1,
                "click_to_register_window_hours": 72,
            },
        )
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)


def test_background_job_dedupe_key_returns_existing_job(helpers):
    """Verifies background job dedupe key returns existing job behavior."""
    db = helpers["db"]
    job1 = enqueue_job(db, "test_job", {"value": 1}, dedupe_key="k1")
    job2 = enqueue_job(db, "test_job", {"value": 2}, dedupe_key="k1")
    assert int(job1.id) == int(job2.id)
    assert (
        db.query(models.BackgroundJob)
        .filter(models.BackgroundJob.job_type == "test_job")
        .count()
        == 1
    )


def test_online_learning_adds_implicit_interest_tags_from_clicks(helpers):
    """Verifies online learning adds implicit interest tags from clicks behavior."""
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-implicit@test.ro")
    student = (
        db.query(models.User)
        .filter(models.User.email == "student-implicit@test.ro")
        .first()
    )
    assert student is not None

    organizer = models.User(
        email="org-implicit@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    tag = models.Tag(name="rock")
    event = models.Event(
        title="Rock Night",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner=organizer,
        status="published",
    )
    event.tags.append(tag)
    db.add_all([organizer, tag, event])
    db.commit()
    db.refresh(event)

    originals = {}
    try:
        originals["recommendations_online_learning_enabled"] = _set_setting(
            api_module.settings, "recommendations_online_learning_enabled", True
        )
        resp = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp.status_code == 204

        implicit = (
            db.query(models.UserImplicitInterestTag)
            .filter(models.UserImplicitInterestTag.user_id == student.id)
            .all()
        )
        assert len(implicit) == 1
        assert implicit[0].tag_id == tag.id
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)


def test_guardrails_rolls_back_active_model_and_enqueues_recompute(helpers):
    """Verifies guardrails rolls back active model and enqueues recompute behavior."""
    db = _prepare_guardrails_rollback_fixture(helpers)
    result = _run_guardrails_rollback(db)
    assert result["action"] == "rollback"

    active_models = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.is_active.is_(True))
        .all()
    )
    assert len(active_models) == 1
    assert active_models[0].model_version == "old"

    recompute_jobs = (
        db.query(models.BackgroundJob)
        .filter(models.BackgroundJob.job_type == "recompute_recommendations_ml")
        .all()
    )
    assert len(recompute_jobs) == 1
    assert recompute_jobs[0].payload.get("skip_training") is True


def test_admin_personalization_status_includes_active_model_version(helpers):
    """Verifies admin personalization status includes active model version behavior."""
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-status@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-status@test.ro", "admin-fixture-A1")

    db.add(
        models.RecommenderModel(
            model_version="status-model",
            feature_names=["bias"],
            weights=[0.0],
            meta={},
            is_active=True,
        )
    )
    db.commit()

    resp = client.get(
        "/api/admin/personalization/status", headers=helpers["auth_header"](admin_token)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_model_version"] == "status-model"
