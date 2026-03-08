#!/usr/bin/env python3
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
    parser = argparse.ArgumentParser(description="Assert SonarCloud has zero open issues and a passing quality gate.")
    parser.add_argument("--project-key", required=True, help="Sonar project key")
    parser.add_argument("--token", default="", help="Sonar token (falls back to SONAR_TOKEN env)")
    parser.add_argument("--branch", default="", help="Optional branch scope")
    parser.add_argument("--pull-request", default="", help="Optional PR scope")
    parser.add_argument("--expected-commit", default="", help="Optional commit SHA that Sonar must have analyzed")
    parser.add_argument("--timeout-seconds", type=int, default=180, help="Max seconds to wait for Sonar analysis")
    parser.add_argument("--poll-seconds", type=int, default=5, help="Polling interval while waiting for analysis")
    parser.add_argument("--out-json", default="sonar-zero/sonar.json", help="Output JSON path")
    parser.add_argument("--out-md", default="sonar-zero/sonar.md", help="Output markdown path")
    return parser.parse_args()


def _auth_header(token: str) -> str:
    raw = f"{token}:".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _request_json(url: str, auth_header: str) -> dict[str, Any]:
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
    lines = [
        "# Sonar Zero Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Project: `{payload['project_key']}`",
        f"- Open issues: `{payload.get('open_issues')}`",
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


def _validated_scope(args: argparse.Namespace) -> tuple[str, str, str, str, str, list[str]]:
    token = (args.token or os.environ.get("SONAR_TOKEN", "")).strip()
    api_base = normalize_https_url(SONAR_API_BASE, allowed_hosts={SONAR_HOST}).rstrip("/")
    findings: list[str] = []

    try:
        project_key = validate_slug(args.project_key, field_name="sonar project key")
    except ValueError as exc:
        findings.append(str(exc))
        project_key = ""

    branch = args.branch.strip()
    if branch:
        try:
            branch = validate_slug(branch, field_name="sonar branch")
        except ValueError as exc:
            findings.append(str(exc))

    pull_request = args.pull_request.strip()
    if pull_request:
        try:
            pull_request = validate_slug(pull_request, field_name="sonar pull request")
        except ValueError as exc:
            findings.append(str(exc))

    expected_commit = args.expected_commit.strip()
    if expected_commit:
        try:
            expected_commit = validate_commit_sha(expected_commit)
        except ValueError as exc:
            findings.append(str(exc))

    if not token:
        findings.append("SONAR_TOKEN is missing.")

    return token, api_base, project_key, branch, pull_request, expected_commit, findings


def _issues_query(project_key: str, branch: str, pull_request: str) -> str:
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
    gate_query = {"projectKey": project_key}
    if branch:
        gate_query["branch"] = branch
    if pull_request:
        gate_query["pullRequest"] = pull_request
    return urllib.parse.urlencode(gate_query)


def _status_issue_count(status: dict[str, Any]) -> int:
    return sum(int(status.get(key) or 0) for key in ("bugs", "vulnerabilities", "codeSmells"))


def _summary_from_entry(entry: dict[str, Any]) -> tuple[int, str, str]:
    status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
    commit = entry.get("commit") if isinstance(entry.get("commit"), dict) else {}
    return _status_issue_count(status), str(status.get("qualityGateStatus") or "UNKNOWN"), str(commit.get("sha") or "")


def _pull_request_summary(*, api_base: str, auth: str, project_key: str, pull_request: str) -> tuple[int, str, str]:
    query = urllib.parse.urlencode({"project": project_key})
    payload = _request_json(f"{api_base}/api/project_pull_requests/list?{query}", auth)
    for entry in payload.get("pullRequests") or []:
        if isinstance(entry, dict) and str(entry.get("key") or "") == pull_request:
            return _summary_from_entry(entry)
    raise RuntimeError(f"Sonar PR summary not found for pull request {pull_request}")


def _branch_summary(*, api_base: str, auth: str, project_key: str, branch: str) -> tuple[int, str, str]:
    query = urllib.parse.urlencode({"project": project_key})
    payload = _request_json(f"{api_base}/api/project_branches/list?{query}", auth)
    for entry in payload.get("branches") or []:
        if isinstance(entry, dict) and str(entry.get("name") or "") == branch:
            return _summary_from_entry(entry)
    raise RuntimeError(f"Sonar branch summary not found for branch {branch}")


def _scoped_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
    pull_request: str,
) -> tuple[int, str, str]:
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
) -> tuple[int, str, str]:
    issues_url = f"{api_base}/api/issues/search?{_issues_query(project_key, branch, pull_request)}"
    issues_payload = _request_json(issues_url, auth)
    paging = issues_payload.get("paging") or {}
    open_issues = int(paging.get("total") or 0)

    gate_url = f"{api_base}/api/qualitygates/project_status?{_gate_query(project_key, branch, pull_request)}"
    gate_payload = _request_json(gate_url, auth)
    project_status = gate_payload.get("projectStatus") or {}
    quality_gate = str(project_status.get("status") or "UNKNOWN")
    return open_issues, quality_gate, ""


def _current_summary(
    *,
    api_base: str,
    auth: str,
    project_key: str,
    branch: str,
    pull_request: str,
) -> tuple[int, str, str]:
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


def _evaluate_sonar(
    *,
    token: str,
    api_base: str,
    project_key: str,
    branch: str,
    pull_request: str,
    expected_commit: str,
    timeout_seconds: int,
    poll_seconds: int,
    findings: list[str],
) -> tuple[str, int | None, str | None, list[str]]:
    if findings:
        return "fail", None, None, findings

    auth = _auth_header(token)
    open_issues: int | None = None
    quality_gate: str | None = None
    analyzed_commit = ""
    deadline = time.time() + max(timeout_seconds, 1)

    try:
        while True:
            open_issues, quality_gate, analyzed_commit = _current_summary(
                api_base=api_base,
                auth=auth,
                project_key=project_key,
                branch=branch,
                pull_request=pull_request,
            )
            if not expected_commit or analyzed_commit == expected_commit:
                break
            if time.time() > deadline:
                findings.append(
                    f"Sonar has not analyzed commit {expected_commit}; latest analyzed commit is {analyzed_commit or 'unknown'}."
                )
                return "fail", open_issues, quality_gate, findings
            time.sleep(max(poll_seconds, 1))
    except Exception as exc:  # pragma: no cover - network/runtime surface
        return "fail", None, None, [*findings, f"Sonar API request failed: {exc}"]

    if open_issues != 0:
        findings.append(f"Sonar reports {open_issues} open issues (expected 0).")
    if quality_gate != "OK":
        findings.append(f"Sonar quality gate status is {quality_gate} (expected OK).")
    status = "pass" if not findings else "fail"
    return status, open_issues, quality_gate, findings


def main() -> int:
    args = _parse_args()
    token, api_base, project_key, branch, pull_request, expected_commit, findings = _validated_scope(args)
    status, open_issues, quality_gate, findings = _evaluate_sonar(
        token=token,
        api_base=api_base,
        project_key=project_key,
        branch=branch,
        pull_request=pull_request,
        expected_commit=expected_commit,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        findings=findings,
    )
    payload = {
        "status": status,
        "project_key": project_key,
        "open_issues": open_issues,
        "quality_gate": quality_gate,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }

    try:
        write_workspace_json(raw_path=args.out_json, fallback="sonar-zero/sonar.json", payload=payload)
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
