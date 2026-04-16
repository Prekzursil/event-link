#!/usr/bin/env python3
"""Support module: check required checks."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_github_commit_checks_url = _security_helpers.build_github_commit_checks_url
build_github_commit_status_url = _security_helpers.build_github_commit_status_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_repo_full_name = _security_helpers.validate_repo_full_name
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text


def _parse_args() -> argparse.Namespace:
    """Implements the parse args helper."""
    parser = argparse.ArgumentParser(
        description=(
            "Wait for required GitHub check contexts and assert they are successful."
        )
    )
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--sha", required=True, help="commit SHA")
    parser.add_argument(
        "--required-context", action="append", default=[], help="Required context name"
    )
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=20)
    parser.add_argument("--out-json", default="quality-zero-gate/required-checks.json")
    parser.add_argument("--out-md", default="quality-zero-gate/required-checks.md")
    return parser.parse_args()


def _api_get(url: str, token: str) -> dict[str, Any]:
    """Implements the api get helper."""
    retries = 4
    delay_seconds = 2
    last_error = "GitHub API request exhausted retries"

    for attempt in range(1, retries + 1):
        payload, _headers, status = request_https_json(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "event-link-quality-zero-gate",
            },
            method="GET",
            timeout=30,
            allowed_hosts={"api.github.com"},
        )
        if 200 <= status < 300:
            if not isinstance(payload, dict):
                raise RuntimeError("Unexpected GitHub API response payload")
            return payload

        retryable = status in {429, 500, 502, 503, 504}
        last_error = f"GitHub API request failed: HTTP {status}"
        if not retryable or attempt == retries:
            raise RuntimeError(last_error)

        time.sleep(delay_seconds)
        delay_seconds *= 2

    raise RuntimeError(last_error)


def _check_run_context(run: dict[str, Any]) -> tuple[str, dict[str, str]] | None:
    """Implements the check run context helper."""
    name = str(run.get("name") or "").strip()
    if not name:
        return None
    return name, {
        "state": str(run.get("status") or ""),
        "conclusion": str(run.get("conclusion") or ""),
        "source": "check_run",
    }


def _status_context(status: dict[str, Any]) -> tuple[str, dict[str, str]] | None:
    """Implements the status context helper."""
    name = str(status.get("context") or "").strip()
    if not name:
        return None
    return name, {
        "state": str(status.get("state") or ""),
        "conclusion": str(status.get("state") or ""),
        "source": "status",
    }


def _collect_contexts(
    check_runs_payload: dict[str, Any], status_payload: dict[str, Any]
) -> dict[str, dict[str, str]]:
    """Implements the collect contexts helper."""
    contexts: dict[str, dict[str, str]] = {}
    for run in check_runs_payload.get("check_runs", []) or []:
        context = _check_run_context(run)
        if context is not None:
            name, payload = context
            contexts[name] = payload
    for status in status_payload.get("statuses", []) or []:
        context = _status_context(status)
        if context is not None:
            name, payload = context
            contexts[name] = payload
    return contexts


def _check_run_failure(context: str, observed: dict[str, str]) -> str | None:
    """Implements the check run failure helper."""
    state = observed.get("state")
    if state != "completed":
        return f"{context}: status={state}"
    conclusion = observed.get("conclusion")
    if conclusion != "success":
        return f"{context}: conclusion={conclusion}"
    return None


def _status_failure(context: str, observed: dict[str, str]) -> str | None:
    """Implements the status failure helper."""
    conclusion = observed.get("conclusion")
    if conclusion != "success":
        return f"{context}: state={conclusion}"
    return None


def _evaluate(
    required: list[str], contexts: dict[str, dict[str, str]]
) -> tuple[str, list[str], list[str]]:
    """Implements the evaluate helper."""
    missing: list[str] = []
    failed: list[str] = []

    for context in required:
        observed = contexts.get(context)
        if not observed:
            missing.append(context)
            continue
        failure = (
            _check_run_failure(context, observed)
            if observed.get("source") == "check_run"
            else _status_failure(context, observed)
        )
        if failure is not None:
            failed.append(failure)

    status = "pass" if not missing and not failed else "fail"
    return status, missing, failed


def _render_md(payload: dict[str, Any]) -> str:
    """Implements the render md helper."""
    lines = [
        "# Quality Zero Gate - Required Contexts",
        "",
        f"- Status: `{payload['status']}`",
        f"- Repo/SHA: `{payload['repo']}@{payload['sha']}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Missing contexts",
    ]

    missing = payload.get("missing") or []
    if missing:
        lines.extend(f"- `{name}`" for name in missing)
    else:
        lines.append("- None")

    lines.extend(["", "## Failed contexts"])
    failed = payload.get("failed") or []
    if failed:
        lines.extend(f"- {entry}" for entry in failed)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def _validated_runtime(
    args: argparse.Namespace,
) -> tuple[str, list[str], str, str, str]:
    """Implements the validated runtime helper."""
    required = [item.strip() for item in args.required_context if item.strip()]
    if not required:
        raise ValueError("At least one --required-context is required")

    token = (
        os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    ).strip()
    if not token:
        raise ValueError("GITHUB_TOKEN or GH_TOKEN is required")

    owner, repo = validate_repo_full_name(args.repo)
    sha = validate_commit_sha(args.sha)
    return token, required, owner, repo, sha


def _payload_from_contexts(
    *,
    owner: str,
    repo: str,
    sha: str,
    required: list[str],
    contexts: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Implements the payload from contexts helper."""
    status, missing, failed = _evaluate(required, contexts)
    return {
        "status": status,
        "repo": f"{owner}/{repo}",
        "sha": sha,
        "required": required,
        "missing": missing,
        "failed": failed,
        "contexts": contexts,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_contexts(
    *, owner: str, repo: str, sha: str, token: str
) -> dict[str, dict[str, str]]:
    """Implements the fetch contexts helper."""
    check_runs = _api_get(
        build_github_commit_checks_url(owner=owner, repo=repo, sha=sha, per_page=100),
        token,
    )
    statuses = _api_get(
        build_github_commit_status_url(owner=owner, repo=repo, sha=sha),
        token,
    )
    return _collect_contexts(check_runs, statuses)


def _has_in_progress_check_runs(contexts: dict[str, dict[str, str]]) -> bool:
    """Implements the has in progress check runs helper."""
    return any(
        value.get("state") != "completed"
        for value in contexts.values()
        if value.get("source") == "check_run"
    )


def _poll_required_contexts(
    *,
    owner: str,
    repo: str,
    sha: str,
    token: str,
    required: list[str],
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    """Implements the poll required contexts helper."""
    deadline = time.time() + max(timeout_seconds, 1)
    final_payload: dict[str, Any] | None = None

    while time.time() <= deadline:
        contexts = _fetch_contexts(owner=owner, repo=repo, sha=sha, token=token)
        final_payload = _payload_from_contexts(
            owner=owner,
            repo=repo,
            sha=sha,
            required=required,
            contexts=contexts,
        )
        if final_payload["status"] == "pass":
            return final_payload
        if not final_payload["missing"] and not _has_in_progress_check_runs(contexts):
            return final_payload
        time.sleep(max(poll_seconds, 1))

    if final_payload is None:
        raise RuntimeError("No payload collected")
    return final_payload


def main() -> int:
    """Implements the main helper."""
    args = _parse_args()
    try:
        token, required, owner, repo, sha = _validated_runtime(args)
    except ValueError as exc:
        raise SystemExit(str(exc))

    final_payload = _poll_required_contexts(
        owner=owner,
        repo=repo,
        sha=sha,
        token=token,
        required=required,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )

    try:
        write_workspace_json(
            raw_path=args.out_json,
            fallback="quality-zero-gate/required-checks.json",
            payload=final_payload,
        )
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="quality-zero-gate/required-checks.md",
            text=_render_md(final_payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if final_payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
