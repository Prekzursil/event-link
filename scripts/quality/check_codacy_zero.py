#!/usr/bin/env python3
"""Assert that Codacy reports zero issues for the requested scope."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, NamedTuple
from urllib.parse import quote

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_https_url = _security_helpers.build_https_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_slug = _security_helpers.validate_slug
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

TOTAL_KEYS = {"total", "totalItems", "total_items", "count", "hits", "open_issues"}
_CODACY_PROVIDERS = {"gh", "github"}


class CodacyRequest(NamedTuple):
    """Validated Codacy lookup parameters for one evaluation attempt."""

    provider: str
    owner: str
    repo: str
    token: str
    branch: str
    pr_number: str
    commit_sha: str
    timeout_seconds: int
    poll_seconds: int

    def with_provider(self, provider: str) -> "CodacyRequest":
        """Return a copy of the request using a different provider slug."""
        return CodacyRequest(
            provider=provider,
            owner=self.owner,
            repo=self.repo,
            token=self.token,
            branch=self.branch,
            pr_number=self.pr_number,
            commit_sha=self.commit_sha,
            timeout_seconds=self.timeout_seconds,
            poll_seconds=self.poll_seconds,
        )


class BranchAnalysisState(NamedTuple):
    """Repository-branch analysis metadata returned by Codacy."""

    analysed_sha: str
    branch_head_sha: str
    open_issues: int | None


class PrAnalysisState(NamedTuple):
    """Pull-request analysis metadata returned by Codacy."""

    analyzed_commit: str
    analysis_in_progress: bool
    open_issues: int | None


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Codacy zero gate."""
    parser = argparse.ArgumentParser(description="Assert Codacy has zero total open issues.")
    parser.add_argument(
        "--provider",
        default="gh",
        help="Organization provider, for example gh",
    )
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument(
        "--branch",
        default="",
        help="Optional branch name to scope Codacy issues",
    )
    parser.add_argument("--pr-number", default="", help="Optional pull request number")
    parser.add_argument("--commit", default="", help="Optional commit SHA")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Max seconds to wait for Codacy analysis",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=5,
        help="Polling interval while waiting for analysis",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Codacy API token (falls back to CODACY_API_TOKEN env)",
    )
    parser.add_argument(
        "--out-json",
        default="codacy-zero/codacy.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="codacy-zero/codacy.md",
        help="Output markdown path",
    )
    return parser.parse_args()


def _request_json(
    *,
    path: str,
    token: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Request JSON from the Codacy API and validate the top-level payload."""
    url = build_https_url(host="api.codacy.com", path=path)
    payload_bytes = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    payload, _headers, status = request_https_json(
        url,
        headers={
            "Accept": "application/json",
            "api-token": token,
            "User-Agent": "event-link-codacy-zero-gate",
            "Content-Type": "application/json",
        },
        method=method,
        body=payload_bytes,
        timeout=30,
        allowed_hosts={"api.codacy.com"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Codacy response payload")
    return status, payload


def _issues_search_request(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    branch: str,
) -> tuple[int, dict[str, Any]]:
    """Submit the Codacy issues search request for the requested repository scope."""
    body: dict[str, str] = {}
    if branch:
        body["branchName"] = branch
    return _request_json(
        path=(f"api/v3/analysis/organizations/{provider}/{owner}/repositories/" f"{repo}/issues/search?limit=1"),
        token=token,
        method="POST",
        body=body,
    )


def _repository_analysis_request(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    branch: str,
) -> tuple[int, dict[str, Any]]:
    """Fetch repository-level Codacy analysis metadata for a branch or default scope."""
    branch_query = f"?branch={quote(branch, safe='')}" if branch else ""
    return _request_json(
        path=(f"api/v3/analysis/organizations/{provider}/{owner}/repositories/" f"{repo}{branch_query}"),
        token=token,
    )


def _extract_total_from_mapping(payload: dict[str, Any]) -> int | None:
    """Read total-count keys from a mapping or its common pagination children."""
    for key, value in payload.items():
        if key in TOTAL_KEYS and isinstance(value, (int, float)):
            return int(value)
    for key in ("pagination", "page", "meta"):
        total = extract_total_open(payload.get(key))
        if total is not None:
            return total
    return None


def _extract_total_from_values(payload: dict[str, Any]) -> int | None:
    """Search nested mapping values for the first parseable total count."""
    for value in payload.values():
        total = extract_total_open(value)
        if total is not None:
            return total
    return None


def extract_total_open(payload: Any) -> int | None:
    """Extract an issue-count total from nested Codacy response payloads."""
    if isinstance(payload, dict):
        direct_total = _extract_total_from_mapping(payload)
        if direct_total is not None:
            return direct_total
        return _extract_total_from_values(payload)

    if isinstance(payload, list):
        for item in payload:
            total = extract_total_open(item)
            if total is not None:
                return total

    return None


def _markdown_code_parts(value: Any) -> tuple[str, str, str]:
    """Return backtick-wrapped markdown fragments for a single value."""
    return ("`", str(value).replace("`", "'"), "`")


def _markdown_fact_parts(label: str, value: Any) -> tuple[str, str, str, str, str]:
    """Return markdown fragments for a bullet-point fact line."""
    code_left, code_value, code_right = _markdown_code_parts(value)
    prefix = f"- {label}: "
    return (prefix, code_left, code_value, code_right, "")


def _markdown_finding_parts(item: Any) -> tuple[str, str]:
    """Normalize a finding string for markdown bullet output."""
    cleaned = str(item).replace("\r", " ").replace("\n", " ")
    return ("- ", cleaned)


def _build_markdown_report_lines(payload: dict[str, Any]) -> list[str]:
    """Build the markdown report lines for the final Codacy gate artifact."""
    lines = [
        "# Codacy Zero Gate",
        "",
        "".join(_markdown_fact_parts("Status", payload["status"])),
        "".join(
            _markdown_fact_parts(
                "Owner/repo",
                str(payload["owner"]) + "/" + str(payload["repo"]),
            )
        ),
        "".join(_markdown_fact_parts("Branch", payload.get("branch") or "default")),
        "".join(_markdown_fact_parts("Open issues", payload.get("open_issues"))),
        "".join(_markdown_fact_parts("Timestamp (UTC)", payload["timestamp_utc"])),
        "",
        "## Findings",
    ]
    findings = payload.get("findings") or []
    if findings:
        lines.extend("".join(_markdown_finding_parts(item)) for item in findings)
    else:
        lines.append("- None")
    return lines


def _validated_inputs(args: argparse.Namespace) -> tuple[str, str, str, str]:
    """Validate repository identity inputs and resolve the Codacy token."""
    owner = validate_slug(args.owner, field_name="owner")
    repo = validate_slug(args.repo, field_name="repo")
    provider = validate_slug(args.provider.lower(), field_name="provider")
    if provider not in _CODACY_PROVIDERS:
        raise ValueError(f"Unsupported Codacy provider: {provider}")
    token = (args.token or os.environ.get("CODACY_API_TOKEN", "")).strip()
    return token, owner, repo, provider


def _provider_candidates(provider: str) -> list[str]:
    """Return the ordered provider slugs to try against Codacy."""
    candidates: list[str] = []
    for candidate in (provider, "gh", "github"):
        if candidate in _CODACY_PROVIDERS and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _validated_pr_number(pr_number: str) -> str:
    """Validate the optional pull-request number when one is provided."""
    value = pr_number.strip()
    if not value:
        return ""
    return validate_slug(value, field_name="pull request number")


def _preferred_commit_sha(raw_commit: str) -> str:
    """Resolve the preferred commit SHA from args or known CI environment keys."""
    value = raw_commit.strip()
    if not value:
        for env_name in ("CHECK_SHA", "TARGET_SHA", "GITHUB_SHA"):
            value = os.environ.get(env_name, "").strip()
            if value:
                break
    return validate_commit_sha(value) if value else ""


def _quality_new_issues(payload: dict[str, Any]) -> int | None:
    """Extract the new-issues count from quality or top-level Codacy payloads."""
    quality = payload.get("quality")
    if isinstance(quality, dict):
        value = quality.get("newIssues")
        if isinstance(value, (int, float)):
            return int(value)
    value = payload.get("newIssues")
    if isinstance(value, (int, float)):
        return int(value)
    return extract_total_open(payload)


def _evaluate_repo_total(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    branch: str,
) -> tuple[str, int | None, list[str]]:
    """Evaluate the total open-issues count from repository-level metadata."""
    status_code, payload = _repository_analysis_request(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        branch=branch,
    )
    if status_code == 404:
        return "retry", None, []
    if not 200 <= status_code < 300:
        return "fail", None, [f"Codacy API request failed: HTTP {status_code}"]

    open_issues = _repository_open_issues(payload)
    if open_issues is None:
        return (
            "fail",
            None,
            ["Codacy response did not include a parseable total issue count."],
        )
    if open_issues != 0:
        return (
            "fail",
            open_issues,
            [f"Codacy reports {open_issues} open issues (expected 0)."],
        )
    return "pass", open_issues, []


def _repository_open_issues(payload: dict[str, Any]) -> int | None:
    """Extract the repository open-issues count from a Codacy response."""
    data = payload.get("data")
    if isinstance(data, dict):
        issues_count = data.get("issuesCount")
        if isinstance(issues_count, (int, float)):
            return int(issues_count)
        return extract_total_open(data)
    return extract_total_open(payload)


def _repository_analysis_state(payload: dict[str, Any]) -> BranchAnalysisState:
    """Extract repository branch-analysis state from a Codacy response."""
    data = payload.get("data")
    if not isinstance(data, dict):
        return BranchAnalysisState("", "", extract_total_open(payload))

    last_analysed_commit = data.get("lastAnalysedCommit")
    selected_branch = data.get("selectedBranch")
    branch_info = data.get("branch")
    analysed_sha = str((last_analysed_commit or {}).get("sha") or "").strip()
    branch_head_sha = str(
        (selected_branch or {}).get("lastCommit") or (branch_info or {}).get("lastCommit") or ""
    ).strip()
    return BranchAnalysisState(
        analysed_sha,
        branch_head_sha,
        _repository_open_issues(payload),
    )


def _issues_result(
    *,
    open_issues: int | None,
    missing_message: str,
    nonzero_message: str,
) -> tuple[str, int | None, list[str]]:
    """Convert a parsed issue count into the gate's pass/fail tuple."""
    if open_issues is None:
        return "fail", None, [missing_message]
    if open_issues != 0:
        return "fail", open_issues, [nonzero_message]
    return "pass", open_issues, []


def _branch_head_mismatch(branch_head_sha: str, commit_sha: str) -> bool:
    """Return whether the observed branch head differs from the requested commit."""
    return bool(branch_head_sha and commit_sha and branch_head_sha != commit_sha)


def _branch_analysis_result(
    state: BranchAnalysisState,
    commit_sha: str,
) -> tuple[str, int | None, list[str]] | None:
    """Return a branch-analysis result when Codacy has reached the expected head."""
    expected_sha = commit_sha or state.branch_head_sha
    if not expected_sha:
        return (
            "fail",
            None,
            ["Codacy repository response did not include a branch head commit."],
        )
    if _branch_head_mismatch(state.branch_head_sha, commit_sha):
        return None
    if state.analysed_sha != expected_sha:
        return None
    return _issues_result(
        open_issues=state.open_issues,
        missing_message=("Codacy repository response did not include a parseable " "total issue count."),
        nonzero_message=f"Codacy reports {state.open_issues} open issues (expected 0).",
    )


def _wait_for_branch_analysis(
    request: CodacyRequest,
) -> tuple[str, int | None, list[str]]:
    """Poll Codacy until branch analysis reaches the requested or current head."""
    deadline = time.time() + max(request.timeout_seconds, 1)

    while True:
        status_code, payload = _repository_analysis_request(
            provider=request.provider,
            owner=request.owner,
            repo=request.repo,
            token=request.token,
            branch=request.branch,
        )
        if status_code == 404:
            return "retry", None, []
        if not 200 <= status_code < 300:
            return "fail", None, [f"Codacy API request failed: HTTP {status_code}"]

        state = _repository_analysis_state(payload)
        result = _branch_analysis_result(state, request.commit_sha)
        if result is not None:
            return result

        if time.time() > deadline:
            expected_sha = request.commit_sha or state.branch_head_sha or "unknown"
            return (
                "fail",
                None,
                [
                    "Codacy has not finished branch analysis for commit "
                    f"{expected_sha}; latest analyzed head is "
                    f"{state.analysed_sha or 'unknown'}."
                ],
            )
        time.sleep(max(request.poll_seconds, 1))


def _pr_analysis_state(payload: dict[str, Any]) -> PrAnalysisState:
    """Extract pull-request analysis state from a Codacy response."""
    pull_request = payload.get("pullRequest") if isinstance(payload.get("pullRequest"), dict) else {}
    return PrAnalysisState(
        str(pull_request.get("headCommitSha") or ""),
        bool(payload.get("isAnalysing")),
        _quality_new_issues(payload),
    )


def _pr_analysis_result(
    state: PrAnalysisState,
    commit_sha: str,
) -> tuple[str, int | None, list[str]] | None:
    """Return a PR-analysis result once Codacy has analyzed the target commit."""
    if state.analyzed_commit != commit_sha or state.analysis_in_progress:
        return None
    return _issues_result(
        open_issues=state.open_issues,
        missing_message=("Codacy PR response did not include a parseable new issue count."),
        nonzero_message=(f"Codacy reports {state.open_issues} PR new issues (expected 0)."),
    )


def _wait_for_pr_analysis(request: CodacyRequest) -> tuple[str, int | None, list[str]]:
    """Poll Codacy until PR analysis reaches the requested commit."""
    path = (
        "api/v3/analysis/organizations/"
        f"{request.provider}/"
        f"{request.owner}/repositories/"
        f"{request.repo}/pull-requests/{request.pr_number}"
    )
    deadline = time.time() + max(request.timeout_seconds, 1)

    while True:
        status_code, payload = _request_json(path=path, token=request.token)
        if status_code == 404:
            return "retry", None, []
        if not 200 <= status_code < 300:
            return "fail", None, [f"Codacy API request failed: HTTP {status_code}"]

        state = _pr_analysis_state(payload)
        result = _pr_analysis_result(state, request.commit_sha)
        if result is not None:
            return result

        if time.time() > deadline:
            return (
                "fail",
                None,
                [
                    "Codacy has not finished PR analysis for commit "
                    f"{request.commit_sha}; latest analyzed head is "
                    f"{state.analyzed_commit or 'unknown'}."
                ],
            )
        time.sleep(max(request.poll_seconds, 1))


def _evaluate_commit_analysis(
    request: CodacyRequest,
) -> tuple[str, int | None, list[str]]:
    """Evaluate Codacy's commit-scoped analysis for the requested commit SHA."""
    path = (
        "api/v3/analysis/organizations/"
        f"{request.provider}/"
        f"{request.owner}/repositories/"
        f"{request.repo}/commits/{request.commit_sha}"
    )
    status_code, payload = _request_json(path=path, token=request.token)
    if status_code == 404:
        return "retry", None, []
    if not 200 <= status_code < 300:
        return "fail", None, [f"Codacy API request failed: HTTP {status_code}"]

    return _issues_result(
        open_issues=_quality_new_issues(payload),
        missing_message=("Codacy commit response did not include a parseable new issue count."),
        nonzero_message=("Codacy reports " f"{_quality_new_issues(payload)} commit new issues (expected 0)."),
    )


def _evaluate_candidate(request: CodacyRequest) -> tuple[str, int | None, list[str]]:
    """Evaluate the best Codacy scope available for the current request."""
    if request.branch:
        return _wait_for_branch_analysis(request)
    if request.pr_number and request.commit_sha:
        return _wait_for_pr_analysis(request)
    if request.commit_sha:
        return _evaluate_commit_analysis(request)
    return _evaluate_repo_total(
        provider=request.provider,
        owner=request.owner,
        repo=request.repo,
        token=request.token,
        branch=request.branch,
    )


def _evaluate_codacy(request: CodacyRequest) -> tuple[str, int | None, list[str]]:
    """Evaluate Codacy across supported providers until one returns a result."""
    if not request.token:
        return "fail", None, ["CODACY_API_TOKEN is missing."]

    last_exc: Exception | None = None
    for candidate in _provider_candidates(request.provider):
        try:
            status, open_issues, findings = _evaluate_candidate(request.with_provider(candidate))
        except Exception as exc:  # pragma: no cover - network/runtime surface
            last_exc = exc
            return "fail", None, [f"Codacy API request failed: {exc}"]
        if status == "retry":
            continue
        return status, open_issues, findings

    findings = ["Codacy API endpoint was not found for provider(s): " f"{request.provider}, gh, github."]
    if last_exc is not None:
        findings.append(f"Last Codacy API error: {last_exc}")
    return "fail", None, findings


def _result_payload(
    *,
    status: str,
    owner: str,
    repo: str,
    provider: str,
    branch: str,
    pr_number: str,
    commit_sha: str,
    open_issues: int | None,
    findings: list[str],
) -> dict[str, Any]:
    """Build the serialized result payload for the Codacy gate."""
    return {
        "status": status,
        "owner": owner,
        "repo": repo,
        "provider": provider,
        "branch": branch,
        "pr_number": pr_number,
        "commit": commit_sha,
        "open_issues": open_issues,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }


def _write_reports(payload: dict[str, Any], args: argparse.Namespace) -> str:
    """Write JSON and markdown artifacts for the Codacy gate result."""
    write_workspace_json(
        raw_path=args.out_json,
        fallback="codacy-zero/codacy.json",
        payload=payload,
    )
    markdown_report = "\n".join(_build_markdown_report_lines(payload)) + "\n"
    out_md = write_workspace_text(
        raw_path=args.out_md,
        fallback="codacy-zero/codacy.md",
        text=markdown_report,
    )
    return out_md.read_text(encoding="utf-8")


def main() -> int:
    """Run the Codacy zero-issues gate and write report artifacts."""
    args = _parse_args()
    try:
        token, owner, repo, provider = _validated_inputs(args)
        branch = args.branch.strip()
        pr_number = _validated_pr_number(args.pr_number)
        commit_sha = _preferred_commit_sha(args.commit)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    request = CodacyRequest(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        branch=branch,
        pr_number=pr_number,
        commit_sha=commit_sha,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    status, open_issues, findings = _evaluate_codacy(request)
    payload = _result_payload(
        status=status,
        owner=owner,
        repo=repo,
        provider=provider,
        branch=branch,
        pr_number=pr_number,
        commit_sha=commit_sha,
        open_issues=open_issues,
        findings=findings,
    )

    try:
        markdown_output = _write_reports(payload, args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(markdown_output, end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
