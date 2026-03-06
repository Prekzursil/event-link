#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
normalize_https_url = _security_helpers.normalize_https_url
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text
build_github_commit_status_url = _security_helpers.build_github_commit_status_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_repo_full_name = _security_helpers.validate_repo_full_name
build_https_url = _security_helpers.build_https_url

DEEPSCAN_HOST = "deepscan.io"
TOTAL_KEYS = {
    "count",
    "hits",
    "open_issues",
    "outstandingDefectCount",
    "outstanding_defect_count",
    "total",
    "totalCount",
    "totalItems",
    "total_items",
}
STATUS_RETRY_ATTEMPTS = 6
STATUS_RETRY_DELAY_SECONDS = 5.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assert DeepScan has zero total open issues.")
    parser.add_argument("--token", default="", help="DeepScan API token (falls back to DEEPSCAN_API_TOKEN env)")
    parser.add_argument("--repo", default="", help="GitHub repository owner/name for DeepScan status discovery")
    parser.add_argument("--sha", default="", help="Commit SHA for DeepScan status discovery")
    parser.add_argument("--github-token", default="", help="GitHub token for DeepScan status discovery")
    parser.add_argument("--out-json", default="deepscan-zero/deepscan.json", help="Output JSON path")
    parser.add_argument("--out-md", default="deepscan-zero/deepscan.md", help="Output markdown path")
    return parser.parse_args()


def extract_total_open(payload: Any) -> int | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in TOTAL_KEYS and isinstance(value, (int, float)):
                return int(value)
        for nested in payload.values():
            total = extract_total_open(nested)
            if total is not None:
                return total
    elif isinstance(payload, list):
        for nested in payload:
            total = extract_total_open(nested)
            if total is not None:
                return total
    return None


def _request_json(url: str, token: str) -> dict[str, Any]:
    safe_url = normalize_https_url(url, allowed_host_suffixes={DEEPSCAN_HOST})
    headers = {
        "Accept": "application/json",
        "User-Agent": "event-link-deepscan-zero-gate",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload, _headers, status = request_https_json(
        safe_url,
        headers=headers,
        method="GET",
        timeout=30,
        allowed_host_suffixes={DEEPSCAN_HOST},
    )
    if not 200 <= status < 300:
        raise RuntimeError(f"DeepScan API request failed: HTTP {status}")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected DeepScan response payload")
    return payload


def _github_status_payload(*, owner: str, repo: str, sha: str, github_token: str) -> dict[str, Any]:
    payload, _headers, status = request_https_json(
        build_github_commit_status_url(owner=owner, repo=repo, sha=sha),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "event-link-deepscan-zero-gate",
        },
        method="GET",
        timeout=30,
        allowed_hosts={"api.github.com"},
    )
    if not 200 <= status < 300:
        raise RuntimeError(f"GitHub API request failed: HTTP {status}")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected GitHub status payload")
    return payload


def _required_numeric(fragment_values: dict[str, list[str]], key: str) -> str:
    value = str((fragment_values.get(key) or [""])[0]).strip()
    if not value.isdigit():
        raise RuntimeError(f"DeepScan dashboard URL is missing a valid {key} value.")
    return value


def _parse_dashboard_url_ids(dashboard_url: str) -> dict[str, str]:
    normalize_https_url(dashboard_url, allowed_host_suffixes={DEEPSCAN_HOST})
    parsed = urlparse((dashboard_url or "").strip())
    fragment_values = parse_qs(parsed.fragment, keep_blank_values=False)
    return {
        "team_id": _required_numeric(fragment_values, "tid"),
        "project_id": _required_numeric(fragment_values, "pid"),
        "branch_id": _required_numeric(fragment_values, "bid"),
        "pull_request_id": _required_numeric(fragment_values, "prid"),
    }


def _deepscan_dashboard_url(status_payload: dict[str, Any]) -> str:
    for status in status_payload.get("statuses") or []:
        if str(status.get("context") or "").strip() != "DeepScan":
            continue
        target_url = str(status.get("target_url") or status.get("targetUrl") or "").strip()
        if target_url:
            normalize_https_url(target_url, allowed_host_suffixes={DEEPSCAN_HOST})
            return target_url
    raise RuntimeError("DeepScan commit status did not include a provider target URL.")


def _wait_for_deepscan_dashboard_url(*, owner: str, repo: str, sha: str, github_token: str) -> str:
    last_error: RuntimeError | None = None
    for attempt in range(STATUS_RETRY_ATTEMPTS):
        try:
            return _deepscan_dashboard_url(
                _github_status_payload(owner=owner, repo=repo, sha=sha, github_token=github_token)
            )
        except RuntimeError as exc:
            last_error = exc
            if attempt == STATUS_RETRY_ATTEMPTS - 1:
                break
            time.sleep(STATUS_RETRY_DELAY_SECONDS)
    raise last_error or RuntimeError("DeepScan commit status did not include a provider target URL.")


def _analysis_api_url(ids: dict[str, str], *, owner_bid: str, head_aid: str) -> str:
    return build_https_url(
        host=DEEPSCAN_HOST,
        path=(
            f"api/teams/{ids['team_id']}/projects/{ids['project_id']}"
            f"/branches/{owner_bid}/analyses/{head_aid}"
        ),
    )


def _resolve_analysis_url_from_dashboard(dashboard_url: str, token: str) -> str:
    ids = _parse_dashboard_url_ids(dashboard_url)
    pull_url = build_https_url(
        host=DEEPSCAN_HOST,
        path=f"api/teams/{ids['team_id']}/projects/{ids['project_id']}/pulls/{ids['pull_request_id']}",
    )
    pull_payload = _request_json(pull_url, token)
    data = pull_payload.get("data") if isinstance(pull_payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("DeepScan pull payload did not include a data object.")
    owner_bid = str(data.get("ownerBid") or "").strip()
    head_aid = str(data.get("headAid") or "").strip()
    if not owner_bid.isdigit() or not head_aid.isdigit():
        raise RuntimeError("DeepScan pull payload did not include valid analysis identifiers.")
    return _analysis_api_url(ids, owner_bid=owner_bid, head_aid=head_aid)


def _is_dashboard_url(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    return parsed.path.rstrip("/") == "/dashboard" and "prid=" in parsed.fragment


def _resolve_open_issues(
    *,
    token: str,
    open_issues_url: str | None,
    repo: str,
    sha: str,
    github_token: str,
) -> tuple[int, str]:
    if open_issues_url:
        analysis_url = (
            _resolve_analysis_url_from_dashboard(open_issues_url, token)
            if _is_dashboard_url(open_issues_url)
            else open_issues_url
        )
    else:
        owner, repo_name = validate_repo_full_name(repo)
        safe_sha = validate_commit_sha(sha)
        dashboard_url = _wait_for_deepscan_dashboard_url(
            owner=owner,
            repo=repo_name,
            sha=safe_sha,
            github_token=github_token,
        )
        analysis_url = _resolve_analysis_url_from_dashboard(dashboard_url, token)

    analysis_payload = _request_json(analysis_url, token)
    open_issues = extract_total_open(analysis_payload)
    if open_issues is None:
        raise RuntimeError("DeepScan response did not include a parseable total issue count.")
    return open_issues, analysis_url


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# DeepScan Zero Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Open issues: `{payload.get('open_issues')}`",
        f"- Source URL: `{payload.get('open_issues_url') or 'n/a'}`",
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


def _validated_inputs(args: argparse.Namespace) -> tuple[str, str | None, str, str, str, list[str]]:
    token = (args.token or os.environ.get("DEEPSCAN_API_TOKEN", "")).strip()
    raw_url = os.environ.get("DEEPSCAN_OPEN_ISSUES_URL", "").strip()
    repo = (args.repo or os.environ.get("GITHUB_REPOSITORY", "")).strip()
    sha = (args.sha or os.environ.get("TARGET_SHA", "") or os.environ.get("GITHUB_SHA", "")).strip()
    github_token = (args.github_token or os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")).strip()
    findings: list[str] = []
    safe_url: str | None = None

    if raw_url:
        try:
            safe_url = normalize_https_url(raw_url, allowed_host_suffixes={DEEPSCAN_HOST})
        except ValueError as exc:
            findings.append(str(exc))
    if safe_url is None and not (repo and sha and github_token):
        findings.append(
            "DeepScan open-issues URL is missing and GitHub status fallback is not fully configured."
        )

    return token, safe_url, repo, sha, github_token, findings


def _evaluate_deepscan(
    *,
    token: str,
    open_issues_url: str | None,
    repo: str,
    sha: str,
    github_token: str,
    findings: list[str],
    resolver=_resolve_open_issues,
) -> tuple[str, int | None, list[str], str | None]:
    if findings:
        return "fail", None, findings, open_issues_url

    try:
        open_issues, source_url = resolver(
            token=token,
            open_issues_url=open_issues_url,
            repo=repo,
            sha=sha,
            github_token=github_token,
        )
    except Exception as exc:  # pragma: no cover - network/runtime surface
        return "fail", None, [*findings, f"DeepScan API request failed: {exc}"], open_issues_url

    if open_issues != 0:
        return "fail", open_issues, [*findings, f"DeepScan reports {open_issues} open issues (expected 0)."], source_url
    return "pass", open_issues, findings, source_url


def main() -> int:
    args = _parse_args()
    token, open_issues_url, repo, sha, github_token, findings = _validated_inputs(args)
    status, open_issues, findings, resolved_url = _evaluate_deepscan(
        token=token,
        open_issues_url=open_issues_url,
        repo=repo,
        sha=sha,
        github_token=github_token,
        findings=findings,
    )
    payload = {
        "status": status,
        "open_issues": open_issues,
        "open_issues_url": resolved_url,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }

    try:
        write_workspace_json(raw_path=args.out_json, fallback="deepscan-zero/deepscan.json", payload=payload)
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="deepscan-zero/deepscan.md",
            text=_render_md(payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())


