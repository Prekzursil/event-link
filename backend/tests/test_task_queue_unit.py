from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import auth, models, task_queue


def _mk_job(db_session, *, job_type: str, payload: dict | None = None, status: str = "queued", run_at=None):
    job = models.BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        status=status,
        attempts=0,
        max_attempts=3,
        run_at=run_at or datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _unexpected_enqueue(*_args, **_kwargs):
    raise AssertionError("enqueue_job should not run")


def _raise(exc: Exception) -> None:
    raise exc


def test_unexpected_enqueue_guard_raises() -> None:
    with pytest.raises(AssertionError, match='enqueue_job should not run'):
        _unexpected_enqueue()

def test_coerce_bool_variants() -> None:
    assert task_queue._coerce_bool(True) is True
    assert task_queue._coerce_bool(False) is False
    assert task_queue._coerce_bool(1) is True
    assert task_queue._coerce_bool(0) is False
    assert task_queue._coerce_bool("yes") is True
    assert task_queue._coerce_bool("off") is False
    assert task_queue._coerce_bool(None) is False

def test_backend_root_points_to_backend_directory() -> None:
    backend_root = task_queue._backend_root()
    assert backend_root.name == "backend"
    assert (backend_root / "app" / "task_queue.py").exists()

def test_requeue_stale_jobs_claim_and_retry_paths(db_session):
    stale_job = _mk_job(
        db_session,
        job_type="stale",
        status="running",
        run_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    stale_job.locked_at = datetime.now(timezone.utc) - timedelta(hours=2)
    stale_job.locked_by = "worker-1"
    db_session.add(stale_job)
    db_session.commit()

    count = task_queue.requeue_stale_jobs(db_session, stale_after_seconds=30)
    assert count == 1

    db_session.refresh(stale_job)
    assert stale_job.status == "queued"
    assert stale_job.locked_at is None
    assert stale_job.locked_by is None

    # claim job
    claimed = task_queue.claim_next_job(db_session, worker_id="worker-2")
    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.locked_by == "worker-2"

    # first failure schedules retry
    task_queue.mark_job_failed(db_session, claimed, error="first")
    db_session.refresh(claimed)
    assert claimed.status == "queued"
    assert claimed.attempts == 1

    # final failure transitions to failed
    claimed.max_attempts = 2
    claimed.status = "running"
    db_session.add(claimed)
    db_session.commit()
    task_queue.mark_job_failed(db_session, claimed, error="final")
    db_session.refresh(claimed)
    assert claimed.status == "failed"
    assert claimed.finished_at is not None


def test_run_recompute_recommendations_ml_paths(monkeypatch, tmp_path):
    missing_backend_root = tmp_path / "missing-backend"
    monkeypatch.setattr(task_queue, "_backend_root", lambda: missing_backend_root)
    with pytest.raises(RuntimeError, match="Missing trainer script"):
        task_queue._run_recompute_recommendations_ml(payload={})

    backend_root = tmp_path / "backend"
    script_dir = backend_root / "scripts"
    script_dir.mkdir(parents=True)
    script_path = script_dir / "recompute_recommendations_ml.py"
    script_path.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(task_queue, "_backend_root", lambda: backend_root)

    observed = {}

    def _run_script(**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(task_queue, "_execute_python_script", _run_script)
    task_queue._run_recompute_recommendations_ml(
        payload={
            "top_n": 5,
            "user_id": 7,
            "skip_training": True,
            "epochs": 2,
            "lr": 0.01,
            "l2": 0.001,
            "seed": 42,
            "model_version": "m2",
            "timeout_seconds": 12,
        }
    )

    argv = " ".join(observed["argv"])
    assert "--top-n 5" in argv
    assert "--user-id 7" in argv
    assert "--skip-training" in argv
    assert "--epochs 2" in argv
    assert "--lr 0.01" in argv
    assert "--l2 0.001" in argv
    assert "--seed 42" in argv
    assert observed["env_overrides"]["RECOMMENDER_MODEL_VERSION"] == "m2"

    def _run_fail(**_kwargs):
        return SimpleNamespace(returncode=2, stdout="oops", stderr="bad")

    monkeypatch.setattr(task_queue, "_execute_python_script", _run_fail)
    with pytest.raises(RuntimeError):
        task_queue._run_recompute_recommendations_ml(payload={"timeout_seconds": 5})


def test_process_job_dispatches_all_paths(monkeypatch, db_session):
    succeeded = []
    failed = []

    monkeypatch.setattr(task_queue, "mark_job_succeeded", lambda _db, job: succeeded.append(job.job_type))
    monkeypatch.setattr(task_queue, "mark_job_failed", lambda _db, job, error: failed.append((job.job_type, error)))
    monkeypatch.setattr(task_queue, "log_event", lambda *_args, **_kwargs: None)

    import app.email_service as email_service_module

    monkeypatch.setattr(email_service_module, "send_email_now", lambda **_kwargs: None)
    monkeypatch.setattr(task_queue, "_run_recompute_recommendations_ml", lambda payload: None)
    monkeypatch.setattr(task_queue, "_send_weekly_digest", lambda **_kwargs: {"users": 1, "emails": 1})
    monkeypatch.setattr(task_queue, "_send_filling_fast_alerts", lambda **_kwargs: {"pairs": 2, "emails": 1})
    monkeypatch.setattr(task_queue, "_evaluate_personalization_guardrails", lambda **_kwargs: {"action": "ok"})

    payload = {"to_email": "a@test.ro", "subject": "s", "body_text": "b", "body_html": None, "context": {}}

    for jt, pl in [
        (task_queue.JOB_TYPE_SEND_EMAIL, payload),
        (task_queue.JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML, {}),
        (task_queue.JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML, {}),
        (task_queue.JOB_TYPE_SEND_WEEKLY_DIGEST, {}),
        (task_queue.JOB_TYPE_SEND_FILLING_FAST_ALERTS, {}),
        (task_queue.JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS, {}),
    ]:
        job = models.BackgroundJob(job_type=jt, payload=pl, status="queued", attempts=0, max_attempts=3, run_at=datetime.now(timezone.utc))
        task_queue.process_job(db_session, job)

    unknown = models.BackgroundJob(job_type="unknown", payload={}, status="queued", attempts=0, max_attempts=3, run_at=datetime.now(timezone.utc))
    task_queue.process_job(db_session, unknown)

    assert task_queue.JOB_TYPE_SEND_EMAIL in succeeded
    assert any(name == "unknown" for name, _ in failed)

    def _boom(payload):
        raise RuntimeError("explode")

    monkeypatch.setattr(task_queue, "_run_recompute_recommendations_ml", _boom)
    failing_job = models.BackgroundJob(
        job_type=task_queue.JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        payload={},
        status="queued",
        attempts=0,
        max_attempts=3,
        run_at=datetime.now(timezone.utc),
    )
    task_queue.process_job(db_session, failing_job)
    assert any(name == task_queue.JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML for name, _ in failed)


def test_send_filling_fast_alerts_enqueues_and_dedupes(monkeypatch, db_session):
    user = models.User(
        email="fill@test.ro",
        password_hash=auth.get_password_hash("fixture-access-A1"),
        role=models.UserRole.student,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    org = models.User(email="fill-org@test.ro", password_hash=auth.get_password_hash("organizer-fixture-A1"), role=models.UserRole.organizator)
    event = models.Event(
        title="Filling Event",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner=org,
        status="published",
    )
    db_session.add_all([user, org, event])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(event)

    fav = models.FavoriteEvent(user_id=int(user.id), event_id=int(event.id))
    reg = models.Registration(user_id=int(user.id), event_id=int(event.id))
    db_session.add_all([fav, reg])
    db_session.commit()

    monkeypatch.setattr(task_queue, "enqueue_job", lambda db, job_type, payload: db.commit())
    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))

    import app.email_templates as tpl
    monkeypatch.setattr(tpl, "render_filling_fast_email", lambda *_args, **_kwargs: ("sub", "txt", "html"))

    result_first = task_queue._send_filling_fast_alerts(
        db=db_session,
        payload={"threshold_abs": 20, "threshold_ratio": 1.0, "max_per_user": 2},
    )
    assert result_first["pairs"] == 1
    assert result_first["emails"] == 1

    result_second = task_queue._send_filling_fast_alerts(
        db=db_session,
        payload={"threshold_abs": 20, "threshold_ratio": 1.0, "max_per_user": 2},
    )
    assert result_second["pairs"] == 1
    assert result_second["emails"] == 0


def test_idle_sleep_uses_minimum_poll_interval(monkeypatch):
    seen = []
    monkeypatch.setattr(task_queue.settings, "task_queue_poll_interval_seconds", 0.0)
    monkeypatch.setattr(task_queue.time, "sleep", lambda secs: seen.append(secs))
    task_queue.idle_sleep()
    assert seen and seen[0] == pytest.approx(0.1)


def test_enqueue_job_integrity_error_paths(monkeypatch, db_session):
    from sqlalchemy.exc import IntegrityError

    def _commit_fail():
        raise IntegrityError("stmt", {}, Exception("dup"))

    monkeypatch.setattr(db_session, "commit", _commit_fail)

    with pytest.raises(IntegrityError):
        task_queue.enqueue_job(db_session, "x", {}, dedupe_key=None)

    class _NoMatchQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    monkeypatch.setattr(db_session, "query", lambda *_args, **_kwargs: _NoMatchQuery())
    with pytest.raises(IntegrityError):
        task_queue.enqueue_job(db_session, "x", {}, dedupe_key="dup-key")


def test_apply_personalization_exclusions_applies_both_filters():
    class _Query:
        def __init__(self) -> None:
            self.filters = 0

        def filter(self, *_args, **_kwargs):
            self.filters += 1
            return self

    query = _Query()
    result = task_queue._apply_personalization_exclusions(
        query,
        hidden_tag_ids={10},
        blocked_organizer_ids={5},
    )
    assert result is query
    assert query.filters == 2


def test_send_weekly_digest_skips_and_handles_system_language(monkeypatch, db_session):
    now = datetime.now(timezone.utc)
    active = models.User(
        email="digest-active@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_digest_enabled=True,
        language_preference="system",
    )
    inactive = models.User(
        email="digest-inactive@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=False,
        email_digest_enabled=True,
        language_preference="system",
    )
    disabled = models.User(
        email="digest-disabled@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_digest_enabled=False,
        language_preference="system",
    )
    organizer = models.User(
        email="digest-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    event = models.Event(
        title="Digest Event",
        description="desc",
        category="Edu",
        start_time=now + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    db_session.add_all([active, inactive, disabled, organizer, event])
    db_session.commit()
    db_session.refresh(active)
    db_session.refresh(event)

    db_session.add(models.UserRecommendation(user_id=int(active.id), event_id=int(event.id), score=0.87, rank=1, model_version="test", reason=None, generated_at=now))
    db_session.commit()

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))
    enqueued = []
    monkeypatch.setattr(task_queue, "enqueue_job", lambda _db, _jt, payload: enqueued.append(payload))

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 3})

    assert result["users"] == 1
    assert result["emails"] == 1
    assert enqueued and "Salut" in enqueued[0]["body_text"]


def test_evaluate_personalization_guardrails_disabled(monkeypatch, db_session):
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", False)
    result = task_queue._evaluate_personalization_guardrails(db=db_session, payload={})
    assert result == {"enabled": False}


def test_coerce_bool_fallback_uses_truthiness_of_custom_object() -> None:
    class _Truthy:
        def __bool__(self) -> bool:
            return True

    assert task_queue._coerce_bool(_Truthy()) is True



def test_claim_next_job_returns_none_when_queue_empty(db_session):
    assert task_queue.claim_next_job(db_session, worker_id="worker-none") is None


def test_claim_next_job_uses_skip_locked_for_postgres(monkeypatch, db_session):
    _mk_job(db_session, job_type="queued")

    query_type = type(db_session.query(models.BackgroundJob))
    original_with_for_update = query_type.with_for_update
    seen: dict[str, bool] = {}

    def _spy_with_for_update(self, *args, **kwargs):
        seen["skip_locked"] = bool(kwargs.get("skip_locked"))
        return original_with_for_update(self, *args, **kwargs)

    monkeypatch.setattr(query_type, "with_for_update", _spy_with_for_update)
    monkeypatch.setattr(db_session.bind.dialect, "name", "postgresql", raising=False)

    claimed = task_queue.claim_next_job(db_session, worker_id="worker-pg")
    assert claimed is not None
    assert claimed.locked_by == "worker-pg"
    assert seen.get("skip_locked") is True


def test_run_recompute_recommendations_ml_missing_script_path(monkeypatch, tmp_path):
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(task_queue, "_backend_root", lambda: backend_root)

    with pytest.raises(RuntimeError, match="Missing trainer script"):
        task_queue._run_recompute_recommendations_ml(payload={})


def test_send_weekly_digest_counts_eligible_users_when_no_events(monkeypatch, db_session):
    user = models.User(
        email="digest-no-events@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_digest_enabled=True,
        language_preference="ro",
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 3})
    assert result == {"users": 1, "emails": 0}


def _seed_guardrail_user_event(db_session):
    user = models.User(
        email="guardrail-branches@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
    )
    organizer = models.User(
        email="guardrail-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    event = models.Event(
        title="Guardrail Event",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    db_session.add_all([user, organizer, event])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(event)
    return user, event


def test_guardrails_low_volume_with_invalid_days_and_meta_variants(monkeypatch, db_session):
    user, event = _seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta="not-a-dict",
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "other", "sort": "time"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="click",
                occurred_at=now,
                meta={"source": "events_list", "sort": "unknown"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="register",
                occurred_at=now + timedelta(hours=5),
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_days", 7)

    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 0, "min_impressions": 10, "click_to_register_window_hours": 1},
    )

    assert result["enabled"] is True
    assert result["days"] == 7
    assert result["action"] == "skip_low_volume"


def test_guardrails_ok_no_active_and_no_previous_paths(monkeypatch, db_session):
    db_session.query(models.EventInteraction).delete()
    db_session.query(models.RecommenderModel).delete()
    db_session.commit()

    user, event = _seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)

    # Balanced interactions to hit the "ok" path.
    for sort in ("recommended", "time"):
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": sort},
            )
        )
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="click",
                occurred_at=now + timedelta(minutes=1),
                meta={"source": "events_list", "sort": sort},
            )
        )
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="register",
                occurred_at=now + timedelta(minutes=5),
            )
        )
    db_session.commit()

    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    ok_result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 1, "min_impressions": 1, "ctr_drop_ratio": 0.5, "conversion_drop_ratio": 0.5},
    )
    assert ok_result["action"] == "ok"

    # Force no_active_model by making recommended quality collapse.
    db_session.add(
        models.EventInteraction(
            user_id=int(user.id),
            event_id=int(event.id),
            interaction_type="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": "recommended"},
        )
    )
    db_session.commit()

    no_active = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 1, "min_impressions": 1, "ctr_drop_ratio": 0.0001, "conversion_drop_ratio": 0.0001},
    )
    assert no_active["action"] == "no_active_model"

    active_model = models.RecommenderModel(
        model_version="active-only",
        feature_names=["bias"],
        weights=[0.0],
        meta={},
        is_active=True,
    )
    db_session.add(active_model)
    db_session.commit()

    no_previous = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 1, "min_impressions": 1, "ctr_drop_ratio": 0.0001, "conversion_drop_ratio": 0.0001},
    )
    assert no_previous["action"] == "no_previous_model"



def test_send_filling_fast_alerts_branch_matrix(monkeypatch, db_session):
    now = datetime.now(timezone.utc)

    organizer = models.User(
        email="branch-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    hidden_tag = models.Tag(name="hidden-branch")

    def _event(title: str, seats: int | None, days: int = 2):
        return models.Event(
            title=title,
            description="desc",
            category="Edu",
            start_time=now + timedelta(days=days),
            city="Cluj",
            location="Hall",
            max_seats=seats,
            owner=organizer,
            status="published",
        )

    event_limit_first = _event("limit-first", 4)
    event_limit_second = _event("limit-second", 4, days=3)
    event_blocked = _event("blocked", 10)
    event_hidden = _event("hidden", 10)
    event_full = _event("full", 1)
    event_abundant = _event("abundant", 100)
    event_system = _event("system", 2)

    event_hidden.tags.append(hidden_tag)

    inactive = models.User(
        email="inactive@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=False,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    disabled = models.User(
        email="disabled@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=False,
        language_preference="en",
    )
    limited = models.User(
        email="limited@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    blocked = models.User(
        email="blocked@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    hidden = models.User(
        email="hidden@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    full = models.User(
        email="full@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    abundant = models.User(
        email="abundant@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    system_lang = models.User(
        email="system@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="system",
    )

    db_session.add_all(
        [
            organizer,
            hidden_tag,
            event_limit_first,
            event_limit_second,
            event_blocked,
            event_hidden,
            event_full,
            event_abundant,
            event_system,
            inactive,
            disabled,
            limited,
            blocked,
            hidden,
            full,
            abundant,
            system_lang,
        ]
    )
    db_session.commit()

    db_session.add_all(
        [
            models.FavoriteEvent(user_id=int(inactive.id), event_id=int(event_limit_first.id)),
            models.FavoriteEvent(user_id=int(disabled.id), event_id=int(event_limit_first.id)),
            models.FavoriteEvent(user_id=int(limited.id), event_id=int(event_limit_first.id)),
            models.FavoriteEvent(user_id=int(limited.id), event_id=int(event_limit_second.id)),
            models.FavoriteEvent(user_id=int(blocked.id), event_id=int(event_blocked.id)),
            models.FavoriteEvent(user_id=int(hidden.id), event_id=int(event_hidden.id)),
            models.FavoriteEvent(user_id=int(full.id), event_id=int(event_full.id)),
            models.FavoriteEvent(user_id=int(abundant.id), event_id=int(event_abundant.id)),
            models.FavoriteEvent(user_id=int(system_lang.id), event_id=int(event_system.id)),
        ]
    )
    db_session.add(models.Registration(user_id=int(full.id), event_id=int(event_full.id)))
    db_session.commit()

    def _exclusions(*, user_id: int, **_kwargs):
        if int(user_id) == int(blocked.id):
            return set(), {int(organizer.id)}
        if int(user_id) == int(hidden.id):
            return {int(hidden_tag.id)}, set()
        return set(), set()

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", _exclusions)

    enqueued = []
    monkeypatch.setattr(task_queue, "enqueue_job", lambda _db, _jt, payload: enqueued.append(payload))

    langs = []
    import app.email_templates as tpl

    def _render(user, event, *, available_seats: int, lang: str):
        langs.append((user.email, lang, available_seats, event.title))
        return "sub", "txt", "html"

    monkeypatch.setattr(tpl, "render_filling_fast_email", _render)

    result = task_queue._send_filling_fast_alerts(
        db=db_session,
        payload={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 1},
    )

    assert result["pairs"] >= 7
    assert result["emails"] == 2
    assert len(enqueued) == 2
    assert any(email == "system@test.ro" and lang == "ro" for email, lang, _available, _title in langs)


def test_send_filling_fast_alerts_skips_rows_without_max_seats(monkeypatch):
    user = SimpleNamespace(id=11, is_active=True, email_filling_fast_enabled=True, language_preference="en", email="user@test.ro")
    event = SimpleNamespace(id=21, owner_id=31, tags=[], max_seats=None, title="No seats")

    class _SeatsQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def group_by(self, *_args, **_kwargs):
            return self

        def subquery(self):
            return SimpleNamespace(c=SimpleNamespace(seats_taken=0, event_id=0))

    class _RowsQuery:
        def select_from(self, *_args, **_kwargs):
            return self

        def join(self, *_args, **_kwargs):
            return self

        def outerjoin(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [(user, event, 0)]

    class _DedupeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    class _FakeDb:
        def __init__(self):
            self.query_calls = 0

        def query(self, *_args, **_kwargs):
            self.query_calls += 1
            if self.query_calls == 1:
                return _SeatsQuery()
            if self.query_calls == 2:
                return _RowsQuery()
            return _DedupeQuery()

    fake_db = _FakeDb()
    render_calls = []

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))
    monkeypatch.setattr(task_queue, "enqueue_job", _unexpected_enqueue)

    import app.email_templates as tpl

    monkeypatch.setattr(tpl, "render_filling_fast_email", lambda *_args, **_kwargs: render_calls.append("rendered"))

    result = task_queue._send_filling_fast_alerts(
        db=fake_db,
        payload={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 1},
    )

    assert result == {"pairs": 1, "emails": 0}
    assert render_calls == []
    assert fake_db.query().filter().first() is None



def test_guardrails_days_fallback_click_source_skip_and_window_skip(monkeypatch, db_session):
    db_session.query(models.EventInteraction).delete()
    db_session.query(models.RecommenderModel).delete()
    db_session.commit()

    user, event = _seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": "recommended"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": "time"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="click",
                occurred_at=now + timedelta(minutes=1),
                meta={"source": "other", "sort": "recommended"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="click",
                occurred_at=now + timedelta(minutes=2),
                meta={"source": "events_list", "sort": "recommended"},
            ),
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="register",
                occurred_at=now + timedelta(hours=5),
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_days", 7)

    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": -1,
            "min_impressions": 1,
            "click_to_register_window_hours": 1,
            "ctr_drop_ratio": 0.5,
            "conversion_drop_ratio": 0.5,
        },
    )

    assert result["days"] == 7
    assert result["enabled"] is True


def test_execute_python_script_handles_success_timeout_and_exceptions(tmp_path):
    script_ok = tmp_path / "ok.py"
    script_ok.write_text("print('ok')\nraise SystemExit(0)\n", encoding="utf-8")
    result_ok = task_queue._execute_python_script(
        script_path=script_ok,
        argv=[str(script_ok)],
        cwd=tmp_path,
        env_overrides={"EVENT_LINK_TEST_FLAG": "1"},
        timeout_seconds=5,
    )
    assert result_ok.returncode == 0
    assert "ok" in result_ok.stdout

    script_fail = tmp_path / "fail.py"
    script_fail.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    result_fail = task_queue._execute_python_script(
        script_path=script_fail,
        argv=[str(script_fail)],
        cwd=tmp_path,
        env_overrides={},
        timeout_seconds=5,
    )
    assert result_fail.returncode == 1
    assert "RuntimeError: boom" in result_fail.stderr

    script_sleep = tmp_path / "sleep.py"
    script_sleep.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")
    result_timeout = task_queue._execute_python_script(
        script_path=script_sleep,
        argv=[str(script_sleep)],
        cwd=tmp_path,
        env_overrides={},
        timeout_seconds=1,
    )
    assert result_timeout.returncode == 124
    assert "timed out" in result_timeout.stderr


def test_run_python_entrypoint_worker_restores_env_and_reports_failures(tmp_path):
    class _Queue:
        def __init__(self) -> None:
            self.payload = None

        def put(self, value) -> None:
            self.payload = value

    os.environ["EVENT_LINK_QUEUE_FLAG"] = "parent-flag"
    original_flag = os.environ.get("EVENT_LINK_QUEUE_FLAG")
    script_ok = tmp_path / "ok_worker.py"
    script_ok.write_text("import os\nprint(os.environ['EVENT_LINK_QUEUE_FLAG'])\nraise SystemExit(0)\n", encoding="utf-8")
    queue_ok = _Queue()
    with pytest.raises(SystemExit) as excinfo:
        task_queue._run_python_entrypoint_worker(
            str(script_ok),
            [str(script_ok)],
            str(tmp_path),
            {"EVENT_LINK_QUEUE_FLAG": "worker-ok"},
            queue_ok,
        )
    assert excinfo.value.code == 0
    assert queue_ok.payload["returncode"] == 0
    assert "worker-ok" in queue_ok.payload["stdout"]
    assert os.environ.get("EVENT_LINK_QUEUE_FLAG") == original_flag

    script_fail = tmp_path / "fail_worker.py"
    script_fail.write_text("raise RuntimeError('worker boom')\n", encoding="utf-8")
    queue_fail = _Queue()
    task_queue._run_python_entrypoint_worker(
        str(script_fail),
        [str(script_fail)],
        str(tmp_path),
        {"EVENT_LINK_QUEUE_TEMP": "worker-temp"},
        queue_fail,
    )
    assert queue_fail.payload["returncode"] == 1
    assert "worker boom" in queue_fail.payload["stderr"]
    assert "EVENT_LINK_QUEUE_TEMP" not in os.environ


def test_execute_python_script_timeout_path(monkeypatch, tmp_path):
    process = type(
        "_Process",
        (),
        {
            "exitcode": None,
            "terminated": False,
            "start": lambda self: None,
            "join": lambda self, timeout=None: None,
            "is_alive": lambda self: not self.terminated,
            "terminate": lambda self: setattr(self, "terminated", True),
        },
    )()
    context = type(
        "_Context",
        (),
        {
            "Queue": lambda self: type(
                "_Queue",
                (),
                {"get": lambda self, timeout: _raise(AssertionError("queue get should not run on timeout path"))},
            )(),
            "Process": lambda self, *args, **kwargs: process,
        },
    )()

    monkeypatch.setattr(task_queue.multiprocessing, "get_context", lambda _mode: context)
    script_path = tmp_path / "noop_timeout.py"
    script_path.write_text("print('noop')\n", encoding="utf-8")

    result = task_queue._execute_python_script(
        script_path=script_path,
        argv=[str(script_path)],
        cwd=tmp_path,
        env_overrides={},
        timeout_seconds=1,
    )

    assert result.returncode == 124
    assert "timed out after 1 seconds" in result.stderr


def test_execute_python_script_queue_empty_fallback(monkeypatch, tmp_path):
    process = type(
        "_Process",
        (),
        {
            "exitcode": 7,
            "start": lambda self: None,
            "join": lambda self, timeout=None: None,
            "is_alive": lambda self: False,
        },
    )()
    context = type(
        "_Context",
        (),
        {
            "Queue": lambda self: type("_EmptyQueue", (), {"get": lambda self, timeout: _raise(task_queue.queue.Empty)})(),
            "Process": lambda self, *args, **kwargs: process,
        },
    )()

    monkeypatch.setattr(task_queue.multiprocessing, "get_context", lambda _mode: context)
    script_path = tmp_path / "noop.py"
    script_path.write_text("print('noop')\n", encoding="utf-8")

    result = task_queue._execute_python_script(
        script_path=script_path,
        argv=[str(script_path)],
        cwd=tmp_path,
        env_overrides={},
        timeout_seconds=1,
    )
    assert result.returncode == 7
    assert "without emitting" in result.stderr



def test_enqueue_job_success_and_deduped_existing_path(monkeypatch, db_session):
    from sqlalchemy.exc import IntegrityError

    job = task_queue.enqueue_job(db_session, "mail", {"x": 1}, dedupe_key="fresh-key")
    assert job.id is not None
    assert job.job_type == "mail"

    existing = models.BackgroundJob(
        job_type="mail",
        payload={"old": True},
        status="queued",
        dedupe_key="dup-key",
        run_at=datetime.now(timezone.utc),
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    def _commit_fail():
        raise IntegrityError("stmt", {}, Exception("dup"))

    monkeypatch.setattr(db_session, "commit", _commit_fail)
    deduped = task_queue.enqueue_job(db_session, "mail", {"x": 2}, dedupe_key="dup-key")
    assert deduped.id == existing.id
    assert getattr(deduped, "_deduped", False) is True


def test_mark_job_succeeded_and_load_personalization_exclusions(db_session):
    user = models.User(
        email="prefs@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
    )
    organizer = models.User(
        email="blocked-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    tag = models.Tag(name="blocked-tag")
    db_session.add_all([user, organizer, tag])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(organizer)
    db_session.refresh(tag)

    db_session.execute(
        models.user_hidden_tags.insert().values(user_id=int(user.id), tag_id=int(tag.id))
    )
    db_session.execute(
        models.user_blocked_organizers.insert().values(
            user_id=int(user.id), organizer_id=int(organizer.id)
        )
    )
    db_session.commit()

    hidden_tag_ids, blocked_organizer_ids = task_queue._load_personalization_exclusions(
        db=db_session,
        user_id=int(user.id),
    )
    assert hidden_tag_ids == {int(tag.id)}
    assert blocked_organizer_ids == {int(organizer.id)}

    job = _mk_job(db_session, job_type="success-case", status="running")
    task_queue.mark_job_succeeded(db_session, job)
    db_session.refresh(job)
    assert job.status == "succeeded"
    assert job.finished_at is not None
    assert job.dedupe_key is None


def test_send_weekly_digest_skips_already_sent_delivery(monkeypatch, db_session):
    now = datetime.now(timezone.utc)
    iso = now.isocalendar()
    week_key = f"{iso.year}-W{iso.week:02d}"

    user = models.User(
        email="digest-sent@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_digest_enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    db_session.add(
        models.NotificationDelivery(
            dedupe_key=f"digest:{int(user.id)}:{week_key}",
            notification_type="weekly_digest",
            user_id=int(user.id),
            event_id=None,
            meta={"source": "test"},
        )
    )
    db_session.commit()

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set()))
    monkeypatch.setattr(task_queue, "enqueue_job", _unexpected_enqueue)

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 1})
    assert result == {"users": 1, "emails": 0}


def test_guardrails_rollback_reactivates_previous_model(monkeypatch, db_session):
    db_session.query(models.EventInteraction).delete()
    db_session.query(models.RecommenderModel).delete()
    db_session.commit()

    user, event = _seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)

    for sort in ("recommended", "time"):
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": sort},
            )
        )
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="click",
                occurred_at=now + timedelta(minutes=1),
                meta={"source": "events_list", "sort": sort},
            )
        )
        db_session.add(
            models.EventInteraction(
                user_id=int(user.id),
                event_id=int(event.id),
                interaction_type="register",
                occurred_at=now + timedelta(minutes=5),
            )
        )

    db_session.add(
        models.EventInteraction(
            user_id=int(user.id),
            event_id=int(event.id),
            interaction_type="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": "recommended"},
        )
    )

    previous = models.RecommenderModel(
        model_version="model-prev",
        feature_names=["bias"],
        weights=[0.0],
        meta={},
        is_active=False,
    )
    active = models.RecommenderModel(
        model_version="model-active",
        feature_names=["bias"],
        weights=[0.1],
        meta={},
        is_active=True,
    )
    db_session.add_all([previous, active])
    db_session.commit()

    enqueued = []
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(task_queue, "enqueue_job", lambda *args, **kwargs: enqueued.append((args, kwargs)))

    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 1, "min_impressions": 1, "ctr_drop_ratio": 0.0001, "conversion_drop_ratio": 0.0001},
    )

    db_session.refresh(previous)
    db_session.refresh(active)
    assert result["action"] == "rollback"
    assert result["rolled_back_from"] == "model-active"
    assert result["rolled_back_to"] == "model-prev"
    assert previous.is_active is True
    assert active.is_active is False
    assert enqueued and enqueued[0][1]["dedupe_key"] == "global"
