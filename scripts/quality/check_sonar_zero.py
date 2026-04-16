#!/usr/bin/env python3
"""Support module: check sonar zero."""

from __future__ import annotations

import argparse
import base64
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
normalize_https_url = _security_helpers.normalize_https_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_slug = _security_helpers.validate_slug
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

SONAR_HOST = "sonarcloud.io"
SONAR_API_BASE = f"https://{SONAR_HOST}"


def _parse_args() -> argparse.Namespace:
    """Implements the parse args helper."""
    parser = argparse.ArgumentParser(
        description="Assert SonarCloud has zero open issues and a passing quality gate."
    )
    parser.add_argument("--project-key", required=True, help="Sonar project key")
    parser.add_argument("--token", default="", help="Sonar token (falls back to SONAR_TOKEN env)")
    parser.add_argument("--branch", default="", help="Optional branch scope")
    parser.add_argument("--pull-request", default="", help="Optional PR scope")
    parser.add_argument(
        "--expected-commit", default="", help="Optional commit SHA that Sonar must have analyzed"
    )
    parser.add_argument(
        "--timeout-seconds", type=int, default=180, help="Max seconds to wait for Sonar analysis"
    )
    parser.add_argument(
        "--poll-seconds", type=int, default=5, help="Polling interval while waiting for analysis"
    )
    parser.add_argument("--out-json", default="sonar-zero/sonar.json", help="Output JSON path")
    parser.add_argument("--out-md", default="sonar-zero/sonar.md", help="Output markdown path")
    return parser.parse_args()


def _auth_header(token: str) -> str:
    """Implements the auth header helper."""
    raw = f"{token}:".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _request_json(url: str, auth_header: str) -> dict[str, Any]:
    """Implements the request json helper."""
    safe_url = normalize_https_url(url, allowed_host_suffixes={SONAR_HOST}).rstrip("/")
    payload, _headers, status = request_https_json(
        safe_url,
        headers={
            "Accept": "application/json",
            "Authorization": auth_header,
            "User-Agent": "event-link-sonar-zero-gate",
        },
        method="GET",
        timeout=30,
        allowed_host_suffixes={SONAR_HOST},
    )
    if not 200 <= status < 300:
        raise RuntimeError(f"Sonar API request failed: HTTP {status}")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Sonar response payload")
    return payload


def _render_md(payload: dict) -> str:
    """Implements the render md helper."""
    lines = [
        "# Sonar Zero Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Project: `{payload['project_key']}`",
        f"- Open issues: `{payload.get('open_issues')}`",
        f"- Open hotspots: `{payload.get('open_hotspots')}`",
        f"- Quality gate: `{payload.get('quality_gate')}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Findings",
    ]
    findings = payload.get("findings") or []
    if findings:
        lines.extend(f"- {item}" for item in findings)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _validated_required_slug(raw_value: str, *, field_name: str, findings: list[str]) -> str:
    """Implements the validated required slug helper."""
    try:
        return validate_slug(raw_value, field_name=field_name)
    except ValueError as exc:
        findings.append(str(exc))
        return ""


def _validated_optional_slug(raw_value: str, *, field_name: str, findings: list[str]) -> str:
    """Implements the validated optional slug helper."""
    value = raw_value.strip()
    if not value:
        return ""
    return _validated_required_slug(value, field_name=field_name, findings=findings)


def _validated_optional_commit(raw_value: str, findings: list[str]) -> str:
    """Implements the validated optional commit helper."""
    value = raw_value.strip()
    if not value:
        return ""
    try:
        return validate_commit_sha(value)
    except ValueError as exc:
        findings.append(str(exc))
        return ""


def _validated_scope(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    """Implements the validated scope helper."""
    findings: list[str] = []
    runtime = {
        "token": (args.token or os.environ.get("SONAR_TOKEN", "")).strip(),
        "api_base": normalize_https_url(SONAR_API_BASE, allowed_hosts={SONAR_HOST}).rstrip("/"),
        "project_key": _validated_required_slug(
            args.project_key, field_name="sonar project key", findings=findings
        ),
        "branch": _validated_optional_slug(
            args.branch, field_name="sonar branch", findings=findings
        ),
        "pull_request": _validated_optional_slug(
            args.pull_request,
            field_name="sonar pull request",
            findings=findings,
        ),
        "expected_commit": _validated_optional_commit(args.expected_commit, findings),
    }
    if not runtime["token"]:
        findings.append("SONAR_TOKEN is missing.")
    return runtime, findings


def _issues_query(project_key: str, branch: str, pull_request: str) -> str:
    """Implements the issues query helper."""
    issues_query = {
        "componentKeys": project_key,
        "resolved": "false",
        "ps": "1",
    }
    if branch:
        issues_query["branch"] = branch
    if pull_request:
        issues_query["pullRequest"] = pull_request
    return urllib.parse.urlencode(issues_query)


def _gate_query(project_key: str, branch: str, pull_request: str) -> str:
    """Implements the gate query helper."""
    gate_query = {"projectKey": project_key}
    if branch:
        gate_query["branch"] = branch
    if pull_request:
        gate_query["pullRequest"] = pull_request
    return urllib.parse.urlencode(gate_query)


def _hotspots_query(project_key: str, branch: str, pull_request: str) -> str:
    """Implements the hotspots query helper."""
    hotspots_query = {
        "projectKey": project_key,
        "ps": "1",
    }
    if branch:
        hotspots_query["branch"] = branch
    if pull_request:
        hotspots_query["pullRequest"] = pull_request
    return urllib.parse.urlencode(hotspots_query)


def _status_issue_count(status: dict[str, Any]) -> int:
    """Implements the status issue count helper."""
    return sum(int(status.get(key) or 0) for key in ("bugs", "vulnerabilities", "codeSmells"))


def _summary_from_entry(entry: dict[str, Any]) -> tuple[int, str, str]:
    """Implements the summary from entry helper."""
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    commit = entry.get("commit") if isinstance(entry.get("commit"), dict) else {}
    return (
        _status_issue_count(status),
        str(status.get("qualityGateStatus") or "UNKNOWN"),
        str(commit.get("sha") or ""),
    )


def _hotspot_total(
    *, api_base: str, auth: str, project_key: str, branch: str, pull_request: str
) -> int:
    """Implements the hotspot total helper."""
    payload = _request_json(
        f"{api_base}/api/hotspots/search?{_hotspots_query(project_key, branch, pull_request)}", auth
    )
    return int((payload.get("paging") or {}).get("total") or 0)


def _pull_request_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    pull_request: str,
) -> tuple[int, str, int, str]:
    """Implements the pull request summary helper."""
    query = urllib.parse.urlencode({"project": project_key})
    payload = _request_json(f"{api_base}/api/project_pull_requests/list?{query}", auth)
    for entry in payload.get("pullRequests") or []:
        if isinstance(entry, dict) and str(entry.get("key") or "") == pull_request:
            open_issues, quality_gate, analyzed_commit = _summary_from_entry(entry)
            open_hotspots = _hotspot_total(
                api_base=api_base,
                auth=auth,
                project_key=project_key,
                branch="",
                pull_request=pull_request,
            )
            return open_issues, quality_gate, open_hotspots, analyzed_commit
    raise RuntimeError(f"Sonar PR summary not found for pull request {pull_request}")


def _branch_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
) -> tuple[int, str, int, str]:
    """Implements the branch summary helper."""
    query = urllib.parse.urlencode({"project": project_key})
    payload = _request_json(f"{api_base}/api/project_branches/list?{query}", auth)
    for entry in payload.get("branches") or []:
        if isinstance(entry, dict) and str(entry.get("name") or "") == branch:
            open_issues, quality_gate, analyzed_commit = _summary_from_entry(entry)
            open_hotspots = _hotspot_total(
                api_base=api_base,
                auth=auth,
                project_key=project_key,
                branch=branch,
                pull_request="",
            )
            return open_issues, quality_gate, open_hotspots, analyzed_commit
    raise RuntimeError(f"Sonar branch summary not found for branch {branch}")


def _scoped_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
    pull_request: str,
) -> tuple[int, str, int, str]:
    """Implements the scoped summary helper."""
    if pull_request:
        return _pull_request_summary(
            api_base=api_base,
            auth=auth,
            project_key=project_key,
            pull_request=pull_request,
        )
    if branch:
        return _branch_summary(
            api_base=api_base,
            auth=auth,
            project_key=project_key,
            branch=branch,
        )
    raise RuntimeError("Sonar branch or pull-request scope is required for summary checks")


def _legacy_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
    pull_request: str,
) -> tuple[int, str, int, str]:
    """Implements the legacy summary helper."""
    issues_url = f"{api_base}/api/issues/search?{_issues_query(project_key, branch, pull_request)}"
    issues_payload = _request_json(issues_url, auth)
    paging = issues_payload.get("paging") or {}
    open_issues = int(paging.get("total") or 0)

    gate_url = f"{api_base}/api/qualitygates/project_status?{_gate_query(project_key, branch, pull_request)}"
    gate_payload = _request_json(gate_url, auth)
    project_status = gate_payload.get("projectStatus") or {}
    quality_gate = str(project_status.get("status") or "UNKNOWN")

    hotspots_url = (
        f"{api_base}/api/hotspots/search?{_hotspots_query(project_key, branch, pull_request)}"
    )
    hotspots_payload = _request_json(hotspots_url, auth)
    hotspots_paging = hotspots_payload.get("paging") or {}
    open_hotspots = int(hotspots_paging.get("total") or 0)

    return open_issues, quality_gate, open_hotspots, ""


def _current_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
    pull_request: str,
) -> tuple[int, str, int, str]:
    """Implements the current summary helper."""
    if branch or pull_request:
        return _scoped_summary(
            api_base=api_base,
            auth=auth,
            project_key=project_key,
            branch=branch,
            pull_request=pull_request,
        )
    return _legacy_summary(
        api_base=api_base,
        auth=auth,
        project_key=project_key,
        branch=branch,
        pull_request=pull_request,
    )


def _await_current_analysis(
    *,
    runtime: dict[str, str],
    auth: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> tuple[int, str, int]:
    """Implements the await current analysis helper."""
    deadline = time.time() + max(timeout_seconds, 1)

    while True:
        open_issues, quality_gate, open_hotspots, analyzed_commit = _current_summary(
            api_base=runtime["api_base"],
            auth=auth,
            project_key=runtime["project_key"],
            branch=runtime["branch"],
            pull_request=runtime["pull_request"],
        )
        expected_commit = runtime["expected_commit"]
        if not expected_commit or analyzed_commit == expected_commit:
            return open_issues, quality_gate, open_hotspots
        if time.time() > deadline:
            raise RuntimeError(
                f"Sonar has not analyzed commit {expected_commit}; latest analyzed commit is {analyzed_commit or 'unknown'}."
            )
        time.sleep(max(poll_seconds, 1))


def _evaluate_sonar(
    *,
    runtime: dict[str, str],
    timeout_seconds: int,
    poll_seconds: int,
    findings: list[str],
) -> tuple[str, int | None, str | None, list[str]]:
    """Implements the evaluate sonar helper."""
    if findings:
        return "fail", None, None, None, findings

    try:
        open_issues, quality_gate, open_hotspots = _await_current_analysis(
            runtime=runtime,
            auth=_auth_header(runtime["token"]),
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
    except Exception as exc:  # pragma: no cover - network/runtime surface
        return "fail", None, None, None, [*findings, f"Sonar API request failed: {exc}"]

    if open_issues != 0:
        findings.append(f"Sonar reports {open_issues} open issues (expected 0).")
    if open_hotspots != 0:
        findings.append(f"Sonar reports {open_hotspots} open security hotspots (expected 0).")
    if quality_gate != "OK":
        findings.append(f"Sonar quality gate status is {quality_gate} (expected OK).")
    status = "pass" if not findings else "fail"
    return status, open_issues, quality_gate, open_hotspots, findings


def main() -> int:
    """Implements the main helper."""
    args = _parse_args()
    runtime, findings = _validated_scope(args)
    status, open_issues, quality_gate, open_hotspots, findings = _evaluate_sonar(
        runtime=runtime,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        findings=findings,
    )
    payload = {
        "status": status,
        "project_key": runtime["project_key"],
        "open_issues": open_issues,
        "open_hotspots": open_hotspots,
        "quality_gate": quality_gate,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }

    try:
        write_workspace_json(
            raw_path=args.out_json, fallback="sonar-zero/sonar.json", payload=payload
        )
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="sonar-zero/sonar.md",
            text=_render_md(payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
