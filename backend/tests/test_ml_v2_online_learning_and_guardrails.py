from datetime import datetime, timedelta, timezone

from app import api as api_module, auth, models
from app.task_queue import enqueue_job, _evaluate_personalization_guardrails


def _set_setting(obj, name: str, value):  # noqa: ANN001
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def test_background_job_dedupe_key_returns_existing_job(helpers):
    db = helpers["db"]
    job1 = enqueue_job(db, "test_job", {"value": 1}, dedupe_key="k1")
    job2 = enqueue_job(db, "test_job", {"value": 2}, dedupe_key="k1")
    assert int(job1.id) == int(job2.id)
    assert db.query(models.BackgroundJob).filter(models.BackgroundJob.job_type == "test_job").count() == 1


def test_online_learning_adds_implicit_interest_tags_from_clicks(helpers):
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-implicit@test.ro")
    student = db.query(models.User).filter(models.User.email == "student-implicit@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="org-implicit@test.ro",
        password_hash=auth.get_password_hash("organizer123"),
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
    db = helpers["db"]

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
    db.add_all([older, active])
    db.commit()
    db.refresh(older)
    db.refresh(active)

    user = models.User(
        email="guardrails@test.ro",
        password_hash=auth.get_password_hash("password123"),
        role=models.UserRole.student,
    )
    org = models.User(
        email="org-guard@test.ro",
        password_hash=auth.get_password_hash("organizer123"),
        role=models.UserRole.organizator,
    )
    event1 = models.Event(
        title="Time Event",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner=org,
        status="published",
    )
    event2 = models.Event(
        title="Time Event 2",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        owner=org,
        status="published",
    )
    event3 = models.Event(
        title="Recommended Event",
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
        owner=org,
        status="published",
    )
    db.add_all([user, org, event1, event2, event3])
    db.commit()
    db.refresh(user)
    db.refresh(event1)
    db.refresh(event2)
    db.refresh(event3)

    now = datetime.now(timezone.utc)
    for _ in range(10):
        db.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event1.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": "time", "position": 0},
            )
        )
        db.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event3.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": "recommended", "position": 0},
            )
        )

    db.add(
        models.EventInteraction(
            user_id=int(user.id),
            event_id=int(event1.id),
            interaction_type="click",
            occurred_at=now,
            meta={"source": "events_list", "sort": "time"},
        )
    )
    db.add(
        models.EventInteraction(
            user_id=int(user.id),
            event_id=int(event2.id),
            interaction_type="click",
            occurred_at=now,
            meta={"source": "events_list", "sort": "time"},
        )
    )
    db.add(
        models.EventInteraction(
            user_id=int(user.id),
            event_id=int(event1.id),
            interaction_type="register",
            occurred_at=now + timedelta(minutes=5),
            meta={"source": "event_detail"},
        )
    )
    db.commit()

    originals = {}
    try:
        originals["personalization_guardrails_enabled"] = _set_setting(api_module.settings, "personalization_guardrails_enabled", True)
        result = _evaluate_personalization_guardrails(
            db=db,
            payload={
                "days": 1,
                "min_impressions": 5,
                "ctr_drop_ratio": 0.1,
                "conversion_drop_ratio": 0.1,
                "click_to_register_window_hours": 72,
            },
        )
        assert result["action"] == "rollback"
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)

    active_models = db.query(models.RecommenderModel).filter(models.RecommenderModel.is_active.is_(True)).all()
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
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-status@test.ro", "admin123")
    admin_token = helpers["login"]("admin-status@test.ro", "admin123")

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

    resp = client.get("/api/admin/personalization/status", headers=helpers["auth_header"](admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_model_version"] == "status-model"

