from __future__ import annotations

import pytest

from app import worker


class _FakeDb:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _prepare_worker(monkeypatch):
    events = []
    warnings = []
    handlers = {}
    db_instances = []

    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker, "log_event", lambda event, **kw: events.append((event, kw)))
    monkeypatch.setattr(worker, "log_warning", lambda event, **kw: warnings.append((event, kw)))
    monkeypatch.setattr(worker, "idle_sleep", lambda: None)
    monkeypatch.setattr(worker, "process_job", lambda db, job: None)
    monkeypatch.setattr(worker, "requeue_stale_jobs", lambda db: 0)

    def _signal(sig, fn):
        handlers[sig] = fn

    monkeypatch.setattr(worker.signal, "signal", _signal)

    def _session_local():
        db = _FakeDb()
        db_instances.append(db)
        return db

    monkeypatch.setattr(worker, "SessionLocal", _session_local)
    monkeypatch.setattr(worker, "_default_worker_id", lambda: "worker-test")
    monkeypatch.setattr(worker.settings, "task_queue_poll_interval_seconds", 0.0)
    monkeypatch.setattr(worker.settings, "task_queue_stale_after_seconds", 1)

    return events, warnings, handlers, db_instances


def test_worker_main_graceful_shutdown(monkeypatch):
    events, warnings, handlers, db_instances = _prepare_worker(monkeypatch)

    def _claim(_db, worker_id):
        assert worker_id == "worker-test"
        handlers[worker.signal.SIGINT](worker.signal.SIGINT, None)
        return None

    monkeypatch.setattr(worker, "claim_next_job", _claim)
    worker.main()

    assert any(evt == "worker_started" for evt, _ in events)
    assert any(evt == "worker_stopped" for evt, _ in events)
    assert any(evt == "worker_shutdown_requested" for evt, _ in warnings)
    assert db_instances and all(db.closed for db in db_instances)




def test_default_worker_id_contains_separator() -> None:
    value = worker._default_worker_id()
    assert ":" in value


def test_worker_main_logs_loop_errors(monkeypatch):
    events, warnings, handlers, db_instances = _prepare_worker(monkeypatch)

    calls = {"count": 0}

    def _claim(_db, worker_id):
        assert worker_id == "worker-test"
        calls["count"] += 1
        if calls["count"] == 1:
            return object()
        handlers[worker.signal.SIGTERM](worker.signal.SIGTERM, None)
        return None

    def _process(_db, _job):
        raise RuntimeError("worker boom")

    monkeypatch.setattr(worker, "claim_next_job", _claim)
    monkeypatch.setattr(worker, "process_job", _process)

    worker.main()

    assert any(evt == "worker_started" for evt, _ in events)
    assert any(evt == "worker_stopped" for evt, _ in events)
    assert any(evt == "worker_loop_error" for evt, _ in warnings)
    assert db_instances and all(db.closed for db in db_instances)

def test_worker_module_entrypoint_runs_main(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "main", lambda: calls.append("ran"))

    worker._maybe_run_main("__main__")
    worker._maybe_run_main("app.worker")

    assert calls == ["ran"]

