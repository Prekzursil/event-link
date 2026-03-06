#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
normalize_https_url = _security_helpers.normalize_https_url
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

DEEPSCAN_HOST = "deepscan.io"
TOTAL_KEYS = {"total", "totalItems", "total_items", "count", "hits", "open_issues"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assert DeepScan has zero total open issues.")
    parser.add_argument("--token", default="", help="DeepScan API token (falls back to DEEPSCAN_API_TOKEN env)")
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
    payload, _headers, status = request_https_json(
        safe_url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "event-link-deepscan-zero-gate",
        },
        method="GET",
        timeout=30,
        allowed_host_suffixes={DEEPSCAN_HOST},
    )
    if not 200 <= status < 300:
        raise RuntimeError(f"DeepScan API request failed: HTTP {status}")
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected DeepScan response payload")
    return payload


def _render_md(payload: dict) -> str:
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


def _validated_inputs(args: argparse.Namespace) -> tuple[str, str | None, list[str]]:
    token = (args.token or os.environ.get("DEEPSCAN_API_TOKEN", "")).strip()
    raw_url = os.environ.get("DEEPSCAN_OPEN_ISSUES_URL", "").strip()
    findings: list[str] = []

    if not token:
        findings.append("DEEPSCAN_API_TOKEN is missing.")
    if not raw_url:
        findings.append("DEEPSCAN_OPEN_ISSUES_URL is missing.")
        return token, None, findings

    try:
        safe_url = normalize_https_url(raw_url, allowed_host_suffixes={DEEPSCAN_HOST})
    except ValueError as exc:
        findings.append(str(exc))
        safe_url = None
    return token, safe_url, findings


def _evaluate_deepscan(*, token: str, open_issues_url: str | None, findings: list[str]) -> tuple[str, int | None, list[str]]:
    if findings or open_issues_url is None:
        return "fail", None, findings

    try:
        payload = _request_json(open_issues_url, token)
    except Exception as exc:  # pragma: no cover - network/runtime surface
        return "fail", None, [*findings, f"DeepScan API request failed: {exc}"]

    open_issues = extract_total_open(payload)
    if open_issues is None:
        return "fail", None, [*findings, "DeepScan response did not include a parseable total issue count."]
    if open_issues != 0:
        return "fail", open_issues, [*findings, f"DeepScan reports {open_issues} open issues (expected 0)."]
    return "pass", open_issues, findings


def main() -> int:
    args = _parse_args()
    token, open_issues_url, findings = _validated_inputs(args)
    status, open_issues, findings = _evaluate_deepscan(
        token=token,
        open_issues_url=open_issues_url,
        findings=findings,
    )
    payload = {
        "status": status,
        "open_issues": open_issues,
        "open_issues_url": open_issues_url,
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
