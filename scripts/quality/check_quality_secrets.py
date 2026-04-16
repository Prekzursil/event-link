#!/usr/bin/env python3
"""Validate that required quality-gate secrets and variables exist."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

DEFAULT_REQUIRED_SECRETS = [
    "SONAR_TOKEN",
    "CODACY_API_TOKEN",
    "SENTRY_AUTH_TOKEN",
]

DEFAULT_REQUIRED_VARS = [
    "SENTRY_ORG",
    "SENTRY_PROJECT",
]


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the quality-secrets preflight."""
    parser = argparse.ArgumentParser(
        description=("Validate required quality-gate secrets/variables are configured.")
    )
    parser.add_argument(
        "--required-secret",
        action="append",
        default=[],
        help="Additional required secret env var name",
    )
    parser.add_argument(
        "--required-var",
        action="append",
        default=[],
        help="Additional required variable env var name",
    )
    parser.add_argument(
        "--out-json",
        default="quality-secrets/secrets.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="quality-secrets/secrets.md",
        help="Output markdown path",
    )
    return parser.parse_args()


def _dedupe(items: list[str]) -> list[str]:
    """Return items once each while preserving their first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _is_present(name: str) -> bool:
    """Return whether an environment variable is present and non-blank."""
    return bool(str(os.environ.get(name, "")).strip())


def _partition_present_and_missing(names: list[str]) -> tuple[list[str], list[str]]:
    """Split environment names into missing and present groups."""
    missing: list[str] = []
    present: list[str] = []
    for name in names:
        (present if _is_present(name) else missing).append(name)
    return missing, present


def evaluate_env(required_secrets: list[str], required_vars: list[str]) -> dict[str, list[str]]:
    """Return which required secrets and variables are present or missing."""
    missing_secrets, present_secrets = _partition_present_and_missing(required_secrets)
    missing_vars, present_vars = _partition_present_and_missing(required_vars)
    return {
        "missing_secrets": missing_secrets,
        "missing_vars": missing_vars,
        "present_secrets": present_secrets,
        "present_vars": present_vars,
    }


def _render_md(payload: dict) -> str:
    """Render the Markdown summary for the secrets preflight payload."""
    lines = [
        "# Quality Secrets Preflight",
        "",
        f"- Status: `{payload['status']}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Missing secrets",
    ]
    missing_secrets = payload.get("missing_secrets") or []
    if missing_secrets:
        lines.extend(f"- `{name}`" for name in missing_secrets)
    else:
        lines.append("- None")

    lines.extend(["", "## Missing variables"])
    missing_vars = payload.get("missing_vars") or []
    if missing_vars:
        lines.extend(f"- `{name}`" for name in missing_vars)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> int:
    """Run the quality-secrets preflight check and write report artifacts."""
    args = _parse_args()
    required_secrets = _dedupe(DEFAULT_REQUIRED_SECRETS + list(args.required_secret or []))
    required_vars = _dedupe(DEFAULT_REQUIRED_VARS + list(args.required_var or []))

    result = evaluate_env(required_secrets, required_vars)
    status = "pass" if not result["missing_secrets"] and not result["missing_vars"] else "fail"
    payload = {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "required_secrets": required_secrets,
        "required_vars": required_vars,
        **result,
    }

    try:
        write_workspace_json(
            raw_path=args.out_json,
            fallback="quality-secrets/secrets.json",
            payload=payload,
        )
        out_md = write_workspace_text(
            raw_path=args.out_md,
            fallback="quality-secrets/secrets.md",
            text=_render_md(payload),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(out_md.read_text(encoding="utf-8"), end="")

    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
