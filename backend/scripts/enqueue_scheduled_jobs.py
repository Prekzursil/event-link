#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bootstrap_imports() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))

    os.environ.setdefault("EMAIL_ENABLED", "false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enqueue scheduled background jobs.")
    parser.add_argument("--retrain-ml", action="store_true", help="Enqueue ML recommendations retraining job.")
    parser.add_argument("--weekly-digest", action="store_true", help="Enqueue weekly digest notification job.")
    parser.add_argument("--filling-fast", action="store_true", help="Enqueue filling-fast notification job.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enqueue the default set (retrain-ml + filling-fast).",
    )
    parser.add_argument("--top-n", type=int, default=50, help="Top-N recommendations to store per user.")
    args = parser.parse_args()

    _bootstrap_imports()

    from app import models  # noqa: PLC0415
    from app.database import SessionLocal  # noqa: PLC0415
    from app.task_queue import (  # noqa: PLC0415
        enqueue_job,
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        JOB_TYPE_SEND_WEEKLY_DIGEST,
        JOB_TYPE_SEND_FILLING_FAST_ALERTS,
    )

    wanted = {
        "retrain": bool(args.retrain_ml or args.all),
        "weekly_digest": bool(args.weekly_digest),
        "filling_fast": bool(args.filling_fast or args.all),
    }
    if not any(wanted.values()):
        wanted["retrain"] = True
        wanted["filling_fast"] = True

    def enqueue_once(db, job_type: str, payload: dict) -> int | None:
        existing = (
            db.query(models.BackgroundJob.id)
            .filter(models.BackgroundJob.job_type == job_type, models.BackgroundJob.status.in_(["queued", "running"]))
            .first()
        )
        if existing:
            return None
        job = enqueue_job(db, job_type, payload)
        return int(job.id)

    created: list[tuple[str, int]] = []
    with SessionLocal() as db:
        if wanted["retrain"]:
            job_id = enqueue_once(
                db,
                JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
                {"top_n": int(args.top_n)},
            )
            if job_id is not None:
                created.append((JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML, job_id))

        if wanted["weekly_digest"]:
            job_id = enqueue_once(db, JOB_TYPE_SEND_WEEKLY_DIGEST, {})
            if job_id is not None:
                created.append((JOB_TYPE_SEND_WEEKLY_DIGEST, job_id))

        if wanted["filling_fast"]:
            job_id = enqueue_once(db, JOB_TYPE_SEND_FILLING_FAST_ALERTS, {})
            if job_id is not None:
                created.append((JOB_TYPE_SEND_FILLING_FAST_ALERTS, job_id))

    for job_type, job_id in created:
        print(f"enqueued job_type={job_type} job_id={job_id}")
    if not created:
        print("no jobs enqueued (already queued/running)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

