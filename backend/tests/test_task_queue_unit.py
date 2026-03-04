from __future__ import annotations

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


def test_coerce_bool_variants() -> None:
    assert task_queue._coerce_bool(True) is True
    assert task_queue._coerce_bool(False) is False
    assert task_queue._coerce_bool(1) is True
    assert task_queue._coerce_bool(0) is False
    assert task_queue._coerce_bool("yes") is True
    assert task_queue._coerce_bool("off") is False
    assert task_queue._coerce_bool(None) is False


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
    with pytest.raises(RuntimeError):
        task_queue._run_recompute_recommendations_ml(payload={})

    backend_root = tmp_path / "backend"
    script_dir = backend_root / "scripts"
    script_dir.mkdir(parents=True)
    script_path = script_dir / "recompute_recommendations_ml.py"
    script_path.write_text("print('ok')", encoding="utf-8")

    monkeypatch.setattr(task_queue, "_backend_root", lambda: backend_root)

    observed = {}

    def _run(cmd, **kwargs):
        observed["cmd"] = cmd
        observed["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(task_queue.subprocess, "run", _run)
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

    cmd = " ".join(observed["cmd"])
    assert "--top-n 5" in cmd
    assert "--user-id 7" in cmd
    assert "--skip-training" in cmd
    assert "--epochs 2" in cmd
    assert "--lr 0.01" in cmd
    assert "--l2 0.001" in cmd
    assert "--seed 42" in cmd
    assert observed["kwargs"]["env"]["RECOMMENDER_MODEL_VERSION"] == "m2"

    def _run_fail(_cmd, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="oops", stderr="bad")

    monkeypatch.setattr(task_queue.subprocess, "run", _run_fail)
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
        password_hash=auth.get_password_hash("pass123"),
        role=models.UserRole.student,
        email_filling_fast_enabled=True,
        language_preference="en",
    )
    org = models.User(email="fill-org@test.ro", password_hash=auth.get_password_hash("org123"), role=models.UserRole.organizator)
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
    assert seen and seen[0] == 0.1

