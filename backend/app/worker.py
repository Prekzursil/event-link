from __future__ import annotations

import os
import signal
import socket
import time

from .config import settings
from .database import SessionLocal
from .logging_utils import configure_logging, log_event, log_warning
from .task_queue import claim_next_job, idle_sleep, process_job, requeue_stale_jobs


def _default_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def main() -> None:
    configure_logging()

    worker_id = os.getenv("WORKER_ID") or _default_worker_id()
    shutdown_requested = False

    def _handle_signal(signum, _frame):  # noqa: ANN001
        nonlocal shutdown_requested
        shutdown_requested = True
        log_warning("worker_shutdown_requested", worker_id=worker_id, signal=signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log_event(
        "worker_started",
        worker_id=worker_id,
        poll_interval_seconds=settings.task_queue_poll_interval_seconds,
    )

    last_requeue_ts = 0.0
    while not shutdown_requested:
        db = SessionLocal()
        try:
            now = time.time()
            if now - last_requeue_ts > max(30, settings.task_queue_stale_after_seconds):
                requeue_stale_jobs(db)
                last_requeue_ts = now

            job = claim_next_job(db, worker_id=worker_id)
            if not job:
                idle_sleep()
                continue
            process_job(db, job)
        except Exception as exc:  # noqa: BLE001
            log_warning("worker_loop_error", worker_id=worker_id, error=str(exc))
            idle_sleep()
        finally:
            db.close()

    log_event("worker_stopped", worker_id=worker_id)


if __name__ == "__main__":
    main()

