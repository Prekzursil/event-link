#!/usr/bin/env python3
"""Support module: check sentry zero."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
normalize_https_url = _security_helpers.normalize_https_url
validate_slug = _security_helpers.validate_slug
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

SENTRY_HOST = "sentry.io"
SENTRY_API_BASE = f"https://{SENTRY_HOST}/api/0"


def _parse_args() -> argparse.Namespace:
    """Implements the parse args helper."""
    parser = argparse.ArgumentParser(
        description="Assert Sentry has zero unresolved issues for configured projects."
    )
    parser.add_argument(
        "--org", default="", help="Sentry org slug (falls back to SENTRY_ORG env)"
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Project slug (repeatable, falls back to SENTRY_PROJECT_BACKEND/SENTRY_PROJECT_WEB env)",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Sentry auth token (falls back to SENTRY_AUTH_TOKEN env)",
    )
    parser.add_argument(
        "--out-json", default="sentry-zero/sentry.json", help="Output JSON path"
    )
    parser.add_argument(
        "--out-md", default="sentry-zero/sentry.md", help="Output markdown path"
    )
    return parser.parse_args()


def _request(url: str, token: str) -> tuple[list[Any], dict[str, str]]:
    """Implements the request helper."""
    safe_url = normalize_https_url(url, allowed_host_suffixes={SENTRY_HOST})
    payload, headers, status = request_https_json(
        safe_url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "event-link-sentry-zero-gate",
        },
        method="GET",
        timeout=30,
        allowed_host_suffixes={SENTRY_HOST},
    )
    if not 200 <= status < 300:
        raise RuntimeError(f"Sentry API request failed: HTTP {status}")
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Sentry response payload")
    return payload, headers


def _hits_from_headers(headers: dict[str, str]) -> int | None:
    """Implements the hits from headers helper."""
    raw = headers.get("x-hits")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _render_md(payload: dict) -> str:
    """Implements the render md helper."""
    lines = [
        "# Sentry Zero Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Org: `{payload.get('org')}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Project results",
    ]

    for item in payload.get("projects", []):
        state = item.get("state")
        state_suffix = "" if not state or state == "ok" else f" state=`{state}`"
        lines.append(
            f"- `{item['project']}` unresolved=`{item['unresolved']}`{state_suffix}"
        )

    if not payload.get("projects"):
        lines.append("- None")

    lines.extend(["", "## Findings"])
    findings = payload.get("findings") or []
    if findings:
        lines.extend(f"- {item}" for item in findings)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def _collect_projects(args: argparse.Namespace) -> list[str]:
    """Implements the collect projects helper."""
    projects = [project for project in args.project if project]
    if projects:
        return projects
    for env_name in ("SENTRY_PROJECT_BACKEND", "SENTRY_PROJECT_WEB", "SENTRY_PROJECT"):
        value = str(os.environ.get(env_name, "")).strip()
        if value:
            projects.append(value)
    return projects


def _validated_org(org_input: str, findings: list[str]) -> str:
    """Implements the validated org helper."""
    if not org_input:
        findings.append("SENTRY_ORG is missing.")
        return ""
    try:
        return validate_slug(org_input, field_name="sentry org")
    except ValueError as exc:
        findings.append(str(exc))
        return ""


def _validated_projects(projects: list[str], findings: list[str]) -> list[str]:
    """Implements the validated projects helper."""
    if not projects:
        findings.append(
            "No Sentry projects configured (SENTRY_PROJECT_BACKEND/SENTRY_PROJECT_WEB/SENTRY_PROJECT)."
        )
        return []

    safe_projects: list[str] = []
    for project in projects:
        try:
            safe_projects.append(validate_slug(project, field_name="sentry project"))
        except ValueError as exc:
            findings.append(str(exc))
    return safe_projects


def _validated_inputs(
    args: argparse.Namespace,
) -> tuple[str, str, list[str], str, list[str]]:
    """Implements the validated inputs helper."""
    token = (args.token or os.environ.get("SENTRY_AUTH_TOKEN", "")).strip()
    org_input = (args.org or os.environ.get("SENTRY_ORG", "")).strip()
    findings: list[str] = []

    if not token:
        findings.append("SENTRY_AUTH_TOKEN is missing.")

    org = _validated_org(org_input, findings)
    safe_projects = _validated_projects(_collect_projects(args), findings)
    api_base = normalize_https_url(SENTRY_API_BASE, allowed_hosts={SENTRY_HOST}).rstrip(
        "/"
    )
    return token, org, safe_projects, api_base, findings


def _project_result(
    *, api_base: str, token: str, org: str, project: str
) -> tuple[dict[str, Any], list[str]]:
    """Implements the project result helper."""
    query = urllib.parse.urlencode({"query": "is:unresolved", "limit": "1"})
    org_slug = urllib.parse.quote(org, safe="")
    project_slug = urllib.parse.quote(project, safe="")
    url = f"{api_base}/projects/{org_slug}/{project_slug}/issues/?{query}"
    issues, headers = _request(url, token)
    unresolved = _hits_from_headers(headers)
    findings: list[str] = []
    if unresolved is None:
        unresolved = len(issues)
        if unresolved >= 1:
            findings.append(
                f"Sentry project {project} returned unresolved issues but no X-Hits header for exact totals."
            )
    if unresolved != 0:
        findings.append(
            f"Sentry project {project} has {unresolved} unresolved issues (expected 0)."
        )
    return {"project": project, "unresolved": unresolved}, findings


def _is_not_found_error(message: str) -> bool:
    """Implements the is not found error helper."""
    return "HTTP 404" in message


def _evaluate_sentry(
    *,
    token: str,
    org: str,
    safe_projects: list[str],
    api_base: str,
    findings: list[str],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Implements the evaluate sentry helper."""
    if findings:
        return "fail", [], findings

    project_results: list[dict[str, Any]] = []
    for project in safe_projects:
        try:
            result, project_findings = _project_result(
                api_base=api_base,
                token=token,
                org=org,
                project=project,
            )
        except Exception as exc:  # pragma: no cover - network/runtime surface
            message = str(exc)
            if _is_not_found_error(message):
                project_results.append(
                    {"project": project, "unresolved": 0, "state": "not_found"}
                )
                continue
            return (
                "fail",
                project_results,
                [*findings, f"Sentry API request failed: {exc}"],
            )
        project_results.append({**result, "state": "ok"})
        findings.extend(project_findings)

    status = "pass" if not findings else "fail"
    return status, project_results, findings


def main() -> int:
    """Implements the main helper."""
    args = _parse_args()
    token, org, safe_projects, api_base, findings = _validated_inputs(args)
    status, project_results, findings = _evaluate_sentry(
        token=token,
        org=org,
        safe_projects=safe_projects,
        api_base=api_base,
        findings=findings,
    )
    payload = {
        "status": status,
        "org": org,
        "projects": project_results,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }

    try:
        write_workspace_json(
            raw_path=args.out_json, fallback="sentry-zero/sentry.json", payload=payload
        )
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="sentry-zero/sentry.md",
            text=_render_md(payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
