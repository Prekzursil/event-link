#!/usr/bin/env python3
"""Command-line helper: enqueue scheduled jobs."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


def _bootstrap_imports() -> None:
    """Implements the bootstrap imports helper."""
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))

    os.environ.setdefault("EMAIL_ENABLED", "false")


def _parse_args() -> argparse.Namespace:
    """Implements the parse args helper."""
    parser = argparse.ArgumentParser(description="Enqueue scheduled background jobs.")
    parser.add_argument("--retrain-ml", action="store_true", help="Enqueue ML recommendations retraining job.")
    parser.add_argument(
        "--guardrails",
        action="store_true",
        help="Enqueue personalization guardrails evaluation job (CTR/conversion checks + auto-rollback).",
    )
    parser.add_argument("--weekly-digest", action="store_true", help="Enqueue weekly digest notification job.")
    parser.add_argument("--filling-fast", action="store_true", help="Enqueue filling-fast notification job.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enqueue the default set (retrain-ml + guardrails + filling-fast).",
    )
    parser.add_argument("--top-n", type=int, default=50, help="Top-N recommendations to store per user.")
    return parser.parse_args()


def _job_constants() -> dict[str, str]:
    """Implements the job constants helper."""
    from app.task_queue import (  # noqa: PLC0415
        JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS,
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        JOB_TYPE_SEND_FILLING_FAST_ALERTS,
        JOB_TYPE_SEND_WEEKLY_DIGEST,
    )

    return {
        "retrain": JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        "guardrails": JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS,
        "weekly_digest": JOB_TYPE_SEND_WEEKLY_DIGEST,
        "filling_fast": JOB_TYPE_SEND_FILLING_FAST_ALERTS,
    }


def _wanted_jobs(args: argparse.Namespace) -> dict[str, bool]:
    """Implements the wanted jobs helper."""
    wanted = {
        "retrain": bool(args.retrain_ml or args.all),
        "guardrails": bool(args.guardrails or args.all),
        "weekly_digest": bool(args.weekly_digest),
        "filling_fast": bool(args.filling_fast or args.all),
    }
    if any(wanted.values()):
        return wanted
    return {
        "retrain": True,
        "guardrails": True,
        "weekly_digest": False,
        "filling_fast": True,
    }


def _job_payloads(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    """Implements the job payloads helper."""
    return {
        "retrain": {"top_n": int(args.top_n)},
        "weekly_digest": {},
        "guardrails": {},
        "filling_fast": {},
    }


def _enqueue_once(db, enqueue_job, *, job_type: str, payload: dict[str, Any]) -> int | None:
    """Implements the enqueue once helper."""
    job = enqueue_job(db, job_type, payload, dedupe_key="global")
    if getattr(job, "_deduped", False):
        return None
    return int(job.id)


def _enqueue_requested_jobs(
    db, enqueue_job, *, wanted: dict[str, bool], payloads: dict[str, dict[str, Any]]
) -> list[tuple[str, int]]:
    """Implements the enqueue requested jobs helper."""
    created: list[tuple[str, int]] = []
    for key, job_type in _job_constants().items():
        if not wanted[key]:
            continue
        job_id = _enqueue_once(db, enqueue_job, job_type=job_type, payload=payloads[key])
        if job_id is not None:
            created.append((job_type, job_id))
    return created


def _print_results(created: list[tuple[str, int]]) -> None:
    """Implements the print results helper."""
    if not created:
        print("no jobs enqueued (already queued/running)")
        return
    for job_type, job_id in created:
        print(f"enqueued job_type={job_type} job_id={job_id}")


def main() -> int:
    """Implements the main helper."""
    args = _parse_args()
    _bootstrap_imports()

    from app.database import SessionLocal  # noqa: PLC0415
    from app.task_queue import enqueue_job  # noqa: PLC0415

    with SessionLocal() as db:
        created = _enqueue_requested_jobs(
            db,
            enqueue_job,
            wanted=_wanted_jobs(args),
            payloads=_job_payloads(args),
        )
    _print_results(created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
