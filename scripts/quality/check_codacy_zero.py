#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_https_url = _security_helpers.build_https_url
validate_slug = _security_helpers.validate_slug
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

TOTAL_KEYS = {"total", "totalItems", "total_items", "count", "hits", "open_issues"}
_CODACY_PROVIDERS = {"gh", "github"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assert Codacy has zero total open issues.")
    parser.add_argument("--provider", default="gh", help="Organization provider, for example gh")
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--token", default="", help="Codacy API token (falls back to CODACY_API_TOKEN env)")
    parser.add_argument("--out-json", default="codacy-zero/codacy.json", help="Output JSON path")
    parser.add_argument("--out-md", default="codacy-zero/codacy.md", help="Output markdown path")
    return parser.parse_args()


def _request_json(*, provider: str, owner: str, repo: str, token: str) -> tuple[int, dict[str, Any]]:
    url = build_https_url(
        host="api.codacy.com",
        path=f"api/v3/analysis/organizations/{provider}/{owner}/repositories/{repo}/issues/search",
        query={"limit": "1"},
    )
    payload, _headers, status = request_https_json(
        url,
        headers={
            "Accept": "application/json",
            "api-token": token,
            "User-Agent": "reframe-codacy-zero-gate",
            "Content-Type": "application/json",
        },
        method="POST",
        body=b"{}",
        timeout=30,
        allowed_hosts={"api.codacy.com"},
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Codacy response payload")
    return status, payload


def _extract_total_from_mapping(payload: dict[str, Any]) -> int | None:
    for key, value in payload.items():
        if key in TOTAL_KEYS and isinstance(value, (int, float)):
            return int(value)
    for key in ("pagination", "page", "meta"):
        total = extract_total_open(payload.get(key))
        if total is not None:
            return total
    return None


def _extract_total_from_values(payload: dict[str, Any]) -> int | None:
    for value in payload.values():
        total = extract_total_open(value)
        if total is not None:
            return total
    return None


def extract_total_open(payload: Any) -> int | None:
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


def _render_md(payload: dict) -> str:
    lines = [
        "# Codacy Zero Gate",
        "",
        f"- Status: `{payload['status']}`",
        f"- Owner/repo: `{payload['owner']}/{payload['repo']}`",
        f"- Open issues: `{payload.get('open_issues')}`",
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


def _validated_inputs(args: argparse.Namespace) -> tuple[str, str, str, str]:
    owner = validate_slug(args.owner, field_name="owner")
    repo = validate_slug(args.repo, field_name="repo")
    provider = validate_slug(args.provider.lower(), field_name="provider")
    if provider not in _CODACY_PROVIDERS:
        raise ValueError(f"Unsupported Codacy provider: {provider}")
    token = (args.token or os.environ.get("CODACY_API_TOKEN", "")).strip()
    return token, owner, repo, provider


def _provider_candidates(provider: str) -> list[str]:
    candidates: list[str] = []
    for candidate in (provider, "gh", "github"):
        if candidate in _CODACY_PROVIDERS and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _evaluate_candidate(*, provider: str, owner: str, repo: str, token: str) -> tuple[str, int | None, list[str]]:
    status_code, payload = _request_json(provider=provider, owner=owner, repo=repo, token=token)
    if status_code == 404:
        return "retry", None, []
    if not 200 <= status_code < 300:
        return "fail", None, [f"Codacy API request failed: HTTP {status_code}"]

    open_issues = extract_total_open(payload)
    if open_issues is None:
        return "fail", None, ["Codacy response did not include a parseable total issue count."]
    if open_issues != 0:
        return "fail", open_issues, [f"Codacy reports {open_issues} open issues (expected 0)."]
    return "pass", open_issues, []


def _evaluate_codacy(*, provider: str, owner: str, repo: str, token: str) -> tuple[str, int | None, list[str]]:
    if not token:
        return "fail", None, ["CODACY_API_TOKEN is missing."]

    last_exc: Exception | None = None
    for candidate in _provider_candidates(provider):
        try:
            status, open_issues, findings = _evaluate_candidate(
                provider=candidate,
                owner=owner,
                repo=repo,
                token=token,
            )
        except Exception as exc:  # pragma: no cover - network/runtime surface
            last_exc = exc
            return "fail", None, [f"Codacy API request failed: {exc}"]
        if status == "retry":
            continue
        return status, open_issues, findings

    findings = [f"Codacy API endpoint was not found for provider(s): {provider}, gh, github."]
    if last_exc is not None:
        findings.append(f"Last Codacy API error: {last_exc}")
    return "fail", None, findings


def main() -> int:
    args = _parse_args()
    try:
        token, owner, repo, provider = _validated_inputs(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    status, open_issues, findings = _evaluate_codacy(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
    )
    payload = {
        "status": status,
        "owner": owner,
        "repo": repo,
        "provider": provider,
        "open_issues": open_issues,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
    }

    try:
        write_workspace_json(raw_path=args.out_json, fallback="codacy-zero/codacy.json", payload=payload)
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="codacy-zero/codacy.md",
            text=_render_md(payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
