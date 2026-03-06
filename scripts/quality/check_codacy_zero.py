#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_https_url = _security_helpers.build_https_url
resolve_workspace_relative_path = _security_helpers.resolve_workspace_relative_path
validate_slug = _security_helpers.validate_slug

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


def _request_json(*, provider: str, owner: str, repo: str, token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"limit": "1"})
    url = build_https_url(
        host="api.codacy.com",
        path=f"api/v3/analysis/organizations/{provider}/{owner}/repositories/{repo}/issues/search",
        query={"limit": "1"},
    )
    if query:
        # build_https_url already encoded query; this keeps explicit intent and avoids mutable full URL inputs.
        pass

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "api-token": token,
            "User-Agent": "reframe-codacy-zero-gate",
            "Content-Type": "application/json",
        },
        method="POST",
        data=b"{}",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_total_open(payload: Any) -> int | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in TOTAL_KEYS and isinstance(value, (int, float)):
                return int(value)

        for key in ("pagination", "page", "meta"):
            nested = payload.get(key)
            total = extract_total_open(nested)
            if total is not None:
                return total

        for value in payload.values():
            total = extract_total_open(value)
            if total is not None:
                return total

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


def _safe_output_path(raw: str, fallback: str) -> Path:
    return resolve_workspace_relative_path(raw, fallback=fallback)


def main() -> int:
    args = _parse_args()
    token = (args.token or os.environ.get("CODACY_API_TOKEN", "")).strip()

    owner = validate_slug(args.owner, field_name="owner")
    repo = validate_slug(args.repo, field_name="repo")
    provider = validate_slug(args.provider.lower(), field_name="provider")
    if provider not in _CODACY_PROVIDERS:
        print(f"Unsupported Codacy provider: {provider}", file=sys.stderr)
        return 1

    findings: list[str] = []
    open_issues: int | None = None

    if not token:
        findings.append("CODACY_API_TOKEN is missing.")
        status = "fail"
    else:
        last_exc: Exception | None = None
        for candidate in (provider, "gh", "github"):
            if candidate not in _CODACY_PROVIDERS:
                continue
            try:
                payload = _request_json(provider=candidate, owner=owner, repo=repo, token=token)
                open_issues = extract_total_open(payload)
                if open_issues is None:
                    findings.append("Codacy response did not include a parseable total issue count.")
                elif open_issues != 0:
                    findings.append(f"Codacy reports {open_issues} open issues (expected 0).")
                status = "pass" if not findings else "fail"
                break
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code == 404:
                    continue
                findings.append(f"Codacy API request failed: HTTP {exc.code}")
                status = "fail"
                break
            except Exception as exc:  # pragma: no cover - network/runtime surface
                last_exc = exc
                findings.append(f"Codacy API request failed: {exc}")
                status = "fail"
                break
        else:
            findings.append(f"Codacy API endpoint was not found for provider(s): {provider}, gh, github.")
            if last_exc is not None:
                findings.append(f"Last Codacy API error: {last_exc}")
            status = "fail"

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
        out_json = _safe_output_path(args.out_json, "codacy-zero/codacy.json")
        out_md = _safe_output_path(args.out_md, "codacy-zero/codacy.md")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(out_md.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

