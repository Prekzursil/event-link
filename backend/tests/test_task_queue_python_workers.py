"""Tests for the task queue python workers behavior."""

# Tests access private helpers of modules-under-test intentionally.
# pylint: disable=protected-access

# Test fixture classes commonly have a single public method by design.
# pylint: disable=too-few-public-methods

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from app import auth, models, task_queue
from task_queue_test_support import (
    mk_job,
    raise_assertion,
    raise_queue_empty,
    unexpected_enqueue,
)


def test_execute_python_script_handles_success_timeout_and_exceptions(tmp_path):
    """Verifies execute python script handles success timeout and exceptions behavior."""
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
    """Verifies run python entrypoint worker restores env and reports failures behavior."""

    class _Queue:
        """Queue value object used in the surrounding module."""

        def __init__(self) -> None:
            """Initializes the instance state."""
            self.payload = None

        def put(self, value) -> None:
            """Implements the put helper."""
            self.payload = value

    os.environ["EVENT_LINK_QUEUE_FLAG"] = "parent-flag"
    original_flag = os.environ.get("EVENT_LINK_QUEUE_FLAG")
    script_ok = tmp_path / "ok_worker.py"
    script_ok.write_text(
        "import os\nprint(os.environ['EVENT_LINK_QUEUE_FLAG'])\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
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
    """Verifies execute python script timeout path behavior."""
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
                {
                    "get": lambda self, timeout: raise_assertion(
                        "queue get should not run on timeout path"
                    )
                },
            )(),
            "Process": lambda self, *args, **kwargs: process,
        },
    )()

    monkeypatch.setattr(
        task_queue.multiprocessing, "get_context", lambda _mode: context
    )
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
    """Verifies execute python script queue empty fallback behavior."""
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
            "Queue": lambda self: type(
                "_EmptyQueue", (), {"get": lambda self, timeout: raise_queue_empty()}
            )(),
            "Process": lambda self, *args, **kwargs: process,
        },
    )()

    monkeypatch.setattr(
        task_queue.multiprocessing, "get_context", lambda _mode: context
    )
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
    """Verifies enqueue job success and deduped existing path behavior."""
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
        """Implements the commit fail helper."""
        raise IntegrityError("stmt", {}, RuntimeError("dup"))

    monkeypatch.setattr(db_session, "commit", _commit_fail)
    deduped = task_queue.enqueue_job(db_session, "mail", {"x": 2}, dedupe_key="dup-key")
    assert deduped.id == existing.id
    assert getattr(deduped, "_deduped", False) is True


def test_mark_job_succeeded_and_load_personalization_exclusions(db_session):
    """Verifies mark job succeeded and load personalization exclusions behavior."""
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
        models.user_hidden_tags.insert().values(
            user_id=int(user.id), tag_id=int(tag.id)
        )
    )
    db_session.execute(
        models.user_blocked_organizers.insert().values(
            user_id=int(user.id),
            organizer_id=int(organizer.id),
        )
    )
    db_session.commit()

    hidden_tag_ids, blocked_organizer_ids = task_queue._load_personalization_exclusions(
        db=db_session,
        user_id=int(user.id),
    )
    assert hidden_tag_ids == {int(tag.id)}
    assert blocked_organizer_ids == {int(organizer.id)}

    job = mk_job(db_session, job_type="success-case", status="running")
    task_queue.mark_job_succeeded(db_session, job)
    db_session.refresh(job)
    assert job.status == "succeeded"
    assert job.finished_at is not None
    assert job.dedupe_key is None


def test_send_weekly_digest_skips_already_sent_delivery(monkeypatch, db_session):
    """Verifies send weekly digest skips already sent delivery behavior."""
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

    monkeypatch.setattr(
        task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set())
    )
    monkeypatch.setattr(task_queue, "enqueue_job", unexpected_enqueue)

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 1})
    assert result == {"users": 1, "emails": 0}
