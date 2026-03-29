#!/usr/bin/env python3
"""Assert that DeepScan reports zero issues for the requested scope."""

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
DEEPSOURCE_HOST = "app.deepsource.com"
DEEPSOURCE_CONTEXT_PREFIX = "DeepSource:"
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
PROVIDER_STATUS_RETRY_ATTEMPTS = 24
PROVIDER_STATUS_RETRY_DELAY_SECONDS = 10.0


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the DeepScan gate."""
    parser = argparse.ArgumentParser(
        description="Assert DeepScan has zero total open issues."
    )
    parser.add_argument(
        "--token",
        default="",
        help="DeepScan API token (falls back to DEEPSCAN_API_TOKEN env)",
    )
    parser.add_argument(
        "--repo",
        default="",
        help="GitHub repository owner/name for DeepScan status discovery",
    )
    parser.add_argument(
        "--sha",
        default="",
        help="Commit SHA for DeepScan status discovery",
    )
    parser.add_argument(
        "--github-token",
        default="",
        help="GitHub token for DeepScan status discovery",
    )
    parser.add_argument(
        "--out-json",
        default="deepscan-zero/deepscan.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="deepscan-zero/deepscan.md",
        help="Output markdown path",
    )
    return parser.parse_args()


def extract_total_open(payload: Any) -> int | None:
    """Extract an issue-count total from nested DeepScan payloads."""
    if isinstance(payload, dict):
        direct_total = _extract_total_from_mapping(payload)
        if direct_total is not None:
            return direct_total
        return _extract_total_from_iterable(payload.values())

    if isinstance(payload, list):
        return _extract_total_from_iterable(payload)

    return None


def _extract_total_from_mapping(payload: dict[str, Any]) -> int | None:
    """Return the first numeric total found in a DeepScan mapping payload."""
    for key, value in payload.items():
        if key in TOTAL_KEYS and isinstance(value, (int, float)):
            return int(value)
    return None


def _extract_total_from_iterable(payload: Any) -> int | None:
    """Return the first numeric total found in nested DeepScan payload items."""
    for nested in payload:
        total = extract_total_open(nested)
        if total is not None:
            return total
    return None


def _request_json(url: str, token: str) -> dict[str, Any]:
    """Fetch a JSON payload from DeepScan with authenticated headers."""
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


def _github_status_payload(
    *, owner: str, repo: str, sha: str, github_token: str
) -> dict[str, Any]:
    """Fetch the GitHub commit-status payload for a repository SHA."""
    payload, _headers, status = request_https_json(
        build_github_commit_status_url(
            owner=owner,
            repo=repo,
            sha=sha,
        ),
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
    """Return a required numeric fragment component from a DeepScan URL."""
    value = str((fragment_values.get(key) or [""])[0]).strip()
    if not value.isdigit():
        raise RuntimeError(f"DeepScan dashboard URL is missing a valid {key} value.")
    return value


def _parse_dashboard_url_ids(dashboard_url: str) -> dict[str, str]:
    """Parse DeepScan dashboard fragment identifiers from a dashboard URL."""
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
    """Return the DeepScan dashboard target URL from GitHub commit statuses."""
    for status in status_payload.get("statuses") or []:
        if str(status.get("context") or "").strip() != "DeepScan":
            continue
        target_url = str(
            status.get("target_url") or status.get("targetUrl") or ""
        ).strip()
        if target_url:
            normalize_https_url(target_url, allowed_host_suffixes={DEEPSCAN_HOST})
            return target_url
    raise RuntimeError("DeepScan commit status did not include a provider target URL.")


def _wait_for_deepscan_dashboard_url(
    *, owner: str, repo: str, sha: str, github_token: str
) -> str:
    """Retry GitHub status discovery until a DeepScan dashboard URL appears."""
    last_error: RuntimeError | None = None
    for attempt in range(STATUS_RETRY_ATTEMPTS):
        try:
            return _deepscan_dashboard_url(
                _github_status_payload(
                    owner=owner,
                    repo=repo,
                    sha=sha,
                    github_token=github_token,
                )
            )
        except RuntimeError as exc:
            last_error = exc
            if attempt == STATUS_RETRY_ATTEMPTS - 1:
                break
            time.sleep(STATUS_RETRY_DELAY_SECONDS)
    raise last_error or RuntimeError(
        "DeepScan commit status did not include a provider target URL."
    )


def _wait_for_provider_status_payload(
    *, owner: str, repo: str, sha: str, github_token: str
) -> dict[str, Any]:
    """Retry GitHub status discovery until DeepSource or DeepScan statuses appear."""
    last_payload: dict[str, Any] = {"statuses": []}
    for attempt in range(PROVIDER_STATUS_RETRY_ATTEMPTS):
        status_payload = _github_status_payload(
            owner=owner,
            repo=repo,
            sha=sha,
            github_token=github_token,
        )
        last_payload = status_payload
        if _matching_statuses(status_payload, prefix="DeepScan") or _matching_statuses(
            status_payload,
            prefix=DEEPSOURCE_CONTEXT_PREFIX,
        ):
            return status_payload
        if attempt == PROVIDER_STATUS_RETRY_ATTEMPTS - 1:
            break
        time.sleep(PROVIDER_STATUS_RETRY_DELAY_SECONDS)
    return last_payload


def _analysis_api_url(ids: dict[str, str], *, owner_bid: str, head_aid: str) -> str:
    """Build the DeepScan analysis API URL for the resolved identifiers."""
    return build_https_url(
        host=DEEPSCAN_HOST,
        path=(
            f"api/teams/{ids['team_id']}/projects/{ids['project_id']}"
            f"/branches/{owner_bid}/analyses/{head_aid}"
        ),
    )


def _resolve_analysis_url_from_dashboard(dashboard_url: str, token: str) -> str:
    """Resolve the DeepScan analysis API URL from a dashboard target URL."""
    ids = _parse_dashboard_url_ids(dashboard_url)
    pull_url = build_https_url(
        host=DEEPSCAN_HOST,
        path=(
            f"api/teams/{ids['team_id']}/projects/{ids['project_id']}"
            f"/pulls/{ids['pull_request_id']}"
        ),
    )
    pull_payload = _request_json(pull_url, token)
    data = pull_payload.get("data") if isinstance(pull_payload, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("DeepScan pull payload did not include a data object.")
    owner_bid = str(data.get("ownerBid") or "").strip()
    head_aid = str(data.get("headAid") or "").strip()
    if not owner_bid.isdigit() or not head_aid.isdigit():
        raise RuntimeError(
            "DeepScan pull payload did not include valid analysis identifiers."
        )
    return _analysis_api_url(ids, owner_bid=owner_bid, head_aid=head_aid)


def _is_dashboard_url(raw_url: str) -> bool:
    """Return ``True`` when a URL points to a DeepScan dashboard fragment."""
    parsed = urlparse(raw_url)
    return parsed.path.rstrip("/") == "/dashboard" and "prid=" in parsed.fragment


def _matching_statuses(
    status_payload: dict[str, Any], *, prefix: str
) -> list[dict[str, Any]]:
    """Return commit statuses whose contexts start with the requested prefix."""
    return [
        status
        for status in status_payload.get("statuses") or []
        if str(status.get("context") or "").strip().startswith(prefix)
    ]


def _status_state(status: dict[str, Any]) -> str:
    """Normalize a status state string for comparison."""
    return str(status.get("state") or "").strip().lower()


def _pending_statuses(statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return statuses still waiting to settle."""
    return [status for status in statuses if _status_state(status) == "pending"]


def _failed_statuses(statuses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return statuses that are neither pending nor successful."""
    return [
        status
        for status in statuses
        if _status_state(status) not in {"pending", "success"}
    ]


def _first_status_target_url(
    statuses: list[dict[str, Any]], *, allowed_host_suffixes: set[str]
) -> str | None:
    """Return the first valid target URL found in a status list."""
    for status in statuses:
        target_url = str(
            status.get("target_url") or status.get("targetUrl") or ""
        ).strip()
        if target_url:
            return normalize_https_url(
                target_url,
                allowed_host_suffixes=allowed_host_suffixes,
            )
    return None


def _status_finding(status: dict[str, Any]) -> str:
    """Format a failing status as a human-readable finding."""
    context = str(status.get("context") or "").strip()
    description = (
        str(status.get("description") or "").strip() or "status not successful"
    )
    return f"{context}: {description}"


def _deepsource_status_summary(
    status_payload: dict[str, Any],
) -> tuple[int, str | None, list[str]] | None:
    """Summarize failing DeepSource commit statuses if any are present."""
    matches = _matching_statuses(status_payload, prefix=DEEPSOURCE_CONTEXT_PREFIX)
    if not matches:
        return None

    failing = _failed_statuses(matches)
    findings = [_status_finding(status) for status in failing]
    source_url = _first_status_target_url(
        [*failing, *matches],
        allowed_host_suffixes={DEEPSOURCE_HOST},
    )
    return len(failing), source_url, findings


def _pending_deepsource_summary(
    pending: list[dict[str, Any]],
) -> tuple[int, str | None, list[str]]:
    """Summarize a pending DeepSource status set for reporting."""
    pending_contexts = [str(status.get("context") or "").strip() for status in pending]
    source_url = _first_status_target_url(
        pending,
        allowed_host_suffixes={DEEPSOURCE_HOST},
    )
    context_list = ", ".join(context for context in pending_contexts if context)
    message = "DeepSource analysis is still in progress."
    if context_list:
        message = f"{message} Pending contexts: {context_list}."
    return 0, source_url, [message]


def _wait_for_deepsource_status_summary(
    *, owner: str, repo: str, sha: str, github_token: str
) -> tuple[int, str | None, list[str]] | None:
    """Wait for DeepSource status contexts to appear and settle."""
    pending_summary: tuple[int, str | None, list[str]] | None = None

    for attempt in range(PROVIDER_STATUS_RETRY_ATTEMPTS):
        status_payload = _github_status_payload(
            owner=owner,
            repo=repo,
            sha=sha,
            github_token=github_token,
        )
        matches = _matching_statuses(status_payload, prefix=DEEPSOURCE_CONTEXT_PREFIX)
        if not matches:
            return None

        pending = _pending_statuses(matches)
        if not pending:
            summary = _deepsource_status_summary(status_payload)
            if summary is None:
                return None
            return summary

        pending_summary = _pending_deepsource_summary(pending)
        if attempt == PROVIDER_STATUS_RETRY_ATTEMPTS - 1:
            break
        time.sleep(PROVIDER_STATUS_RETRY_DELAY_SECONDS)

    return pending_summary


def _resolve_open_issues(
    *,
    token: str,
    open_issues_url: str | None,
    repo: str,
    sha: str,
    github_token: str,
) -> tuple[int, str] | tuple[int, str | None, list[str]]:
    """Resolve the open-issues source for DeepScan and report the total."""
    if open_issues_url:
        analysis_url = (
            _resolve_analysis_url_from_dashboard(open_issues_url, token)
            if _is_dashboard_url(open_issues_url)
            else open_issues_url
        )
    else:
        owner, repo_name = validate_repo_full_name(repo)
        safe_sha = validate_commit_sha(sha)
        status_payload = _wait_for_provider_status_payload(
            owner=owner,
            repo=repo_name,
            sha=safe_sha,
            github_token=github_token,
        )
        try:
            dashboard_url = _deepscan_dashboard_url(status_payload)
        except RuntimeError:
            deepsource_summary = _wait_for_deepsource_status_summary(
                owner=owner,
                repo=repo_name,
                sha=safe_sha,
                github_token=github_token,
            )
            if deepsource_summary is not None:
                return deepsource_summary
            raise
        analysis_url = _resolve_analysis_url_from_dashboard(dashboard_url, token)

    analysis_payload = _request_json(analysis_url, token)
    open_issues = extract_total_open(analysis_payload)
    if open_issues is None:
        raise RuntimeError(
            "DeepScan response did not include a parseable total issue count."
        )
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


def _preferred_value(arg_value: str, *env_names: str) -> str:
    """Return the first non-empty value from an argument or environment."""
    if arg_value:
        return arg_value.strip()
    for env_name in env_names:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return ""


def _validated_open_issues_url(raw_url: str, findings: list[str]) -> str | None:
    """Normalize an optional DeepScan URL and record validation failures."""
    if not raw_url:
        return None
    try:
        return normalize_https_url(
            raw_url,
            allowed_host_suffixes={DEEPSCAN_HOST, DEEPSOURCE_HOST},
        )
    except ValueError as exc:
        findings.append(str(exc))
        return None


def _github_status_fallback_configured(
    *, repo: str, sha: str, github_token: str
) -> bool:
    """Return ``True`` when the GitHub fallback inputs are fully available."""
    return all((repo, sha, github_token))


def _validated_inputs(
    args: argparse.Namespace,
) -> tuple[str, str | None, str, str, str, list[str]]:
    """Resolve and validate CLI and environment inputs for the gate."""
    token = _preferred_value(args.token, "DEEPSCAN_API_TOKEN")
    raw_url = os.environ.get("DEEPSCAN_OPEN_ISSUES_URL", "").strip()
    repo = _preferred_value(args.repo, "GITHUB_REPOSITORY")
    sha = _preferred_value(args.sha, "TARGET_SHA", "GITHUB_SHA")
    github_token = _preferred_value(args.github_token, "GITHUB_TOKEN", "GH_TOKEN")
    findings: list[str] = []
    safe_url = _validated_open_issues_url(raw_url, findings)

    if safe_url is None and not _github_status_fallback_configured(
        repo=repo,
        sha=sha,
        github_token=github_token,
    ):
        findings.append(
            (
                "DeepScan open-issues URL is missing and GitHub status fallback "
                "is not fully configured."
            )
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
    """Evaluate the DeepScan gate using the resolved analysis source."""
    if findings:
        return "fail", None, findings, open_issues_url

    try:
        resolved = resolver(
            token=token,
            open_issues_url=open_issues_url,
            repo=repo,
            sha=sha,
            github_token=github_token,
        )
        if len(resolved) == 3:
            open_issues, source_url, resolver_findings = resolved
        else:
            open_issues, source_url = resolved
            resolver_findings = []
    except Exception as exc:  # pragma: no cover - network/runtime surface
        return (
            "fail",
            None,
            [*findings, f"DeepScan API request failed: {exc}"],
            open_issues_url,
        )

    if resolver_findings:
        return "fail", open_issues, [*findings, *resolver_findings], source_url
    if open_issues != 0:
        issue_findings = resolver_findings or [
            f"DeepScan reports {open_issues} open issues (expected 0)."
        ]
        return "fail", open_issues, [*findings, *issue_findings], source_url
    return "pass", open_issues, findings, source_url


def main() -> int:
    """Run the DeepScan zero-issues gate and write report artifacts."""
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
        write_workspace_json(
            raw_path=args.out_json,
            fallback="deepscan-zero/deepscan.json",
            payload=payload,
        )
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
