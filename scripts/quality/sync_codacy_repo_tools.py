#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_https_url = _security_helpers.build_https_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_slug = _security_helpers.validate_slug
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

CODACY_HOST = "api.codacy.com"
DISABLED_TOOL_NAMES = {
    "CSSLint (deprecated)",
    "ESLint",
    "ESLint (deprecated)",
    "JSHint (deprecated)",
    "Prospector",
    "Pylint (deprecated)",
    "TSLint (deprecated)",
}
CONFIG_FILE_TOOL_NAMES = {
    "Bandit",
    "ESLint9",
    "Ruff",
    "Stylelint",
}
DISABLED_PATTERNS_BY_TOOL = {
    "Pylint": {"PyLint_W1618"},
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Codacy repository tool settings to the repo's intended analyzer profile.")
    parser.add_argument("--provider", default="gh", help="Codacy provider slug, for example gh")
    parser.add_argument("--owner", required=True, help="Repository owner")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--commit", required=True, help="Commit SHA to reanalyze")
    parser.add_argument("--token", default="", help="Codacy API token, defaults to CODACY_API_TOKEN")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without mutating Codacy")
    parser.add_argument("--out-json", default="codacy-tool-sync/codacy-sync.json", help="Output JSON path")
    parser.add_argument("--out-md", default="codacy-tool-sync/codacy-sync.md", help="Output markdown path")
    return parser.parse_args()


def _request_codacy(
    *,
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any, str]:
    url = build_https_url(host=CODACY_HOST, path=path)
    parsed = urlparse(url)
    payload_bytes = b"" if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "event-link-codacy-tool-sync",
        "api-token": token,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    connection = http.client.HTTPSConnection(parsed.hostname, port=parsed.port or 443, timeout=30)
    try:
        connection.request(method.upper(), parsed.path or "/", body=payload_bytes, headers=headers)
        response = connection.getresponse()
        raw_text = response.read().decode("utf-8")
        parsed_payload: Any = None
        if raw_text.strip():
            parsed_payload = json.loads(raw_text)
        return int(response.status), parsed_payload, raw_text
    finally:
        connection.close()


def _list_tools(*, provider: str, owner: str, repo: str, token: str) -> list[dict[str, Any]]:
    status, payload, raw = _request_codacy(
        method="GET",
        path=f"api/v3/analysis/organizations/{provider}/{owner}/repositories/{repo}/tools",
        token=token,
    )
    if status != 200 or not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeError(f"Unable to list Codacy tools: HTTP {status} {raw[:400]}")
    return payload["data"]


def _configure_tool(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    tool_uuid: str,
    payload: dict[str, Any],
) -> None:
    status, _data, raw = _request_codacy(
        method="PATCH",
        path=f"api/v3/analysis/organizations/{provider}/{owner}/repositories/{repo}/tools/{tool_uuid}",
        token=token,
        body=payload,
    )
    if status != 204:
        raise RuntimeError(f"Codacy tool patch failed for {tool_uuid}: HTTP {status} {raw[:400]}")


def _disable_pattern(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    tool_uuid: str,
    pattern_id: str,
) -> None:
    status, _data, raw = _request_codacy(
        method="PATCH",
        path=(
            f"api/v3/analysis/organizations/{provider}/{owner}/repositories/{repo}/tools/{tool_uuid}/patterns"
            f"?search={pattern_id}"
        ),
        token=token,
        body={"enabled": False},
    )
    if status != 204:
        raise RuntimeError(f"Codacy pattern patch failed for {pattern_id} on {tool_uuid}: HTTP {status} {raw[:400]}")


def _reanalyze_commit(*, provider: str, owner: str, repo: str, token: str, commit_sha: str) -> None:
    status, _data, raw = _request_codacy(
        method="POST",
        path=f"api/v3/organizations/{provider}/{owner}/repositories/{repo}/reanalyzeCommit",
        token=token,
        body={"commitUuid": commit_sha, "cleanCache": True},
    )
    if status != 204:
        raise RuntimeError(f"Codacy reanalyze failed for {commit_sha}: HTTP {status} {raw[:400]}")


def _planned_tool_payload(tool_name: str, settings: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    payload: dict[str, Any] = {}

    should_enable = tool_name not in DISABLED_TOOL_NAMES
    if bool(settings.get("isEnabled")) != should_enable:
        payload["enabled"] = should_enable

    if tool_name in CONFIG_FILE_TOOL_NAMES:
        has_config = bool(settings.get("hasConfigurationFile"))
        uses_config = bool(settings.get("usesConfigurationFile"))
        if has_config:
            if not uses_config:
                payload["useConfigurationFile"] = True
        else:
            notes.append(f"{tool_name}: configuration file not detected by Codacy yet")

    return (payload or None), notes


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Codacy Tool Sync",
        "",
        f"- Status: `{payload['status']}`",
        f"- Repository: `{payload['owner']}/{payload['repo']}`",
        f"- Commit reanalyzed: `{payload['commit']}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
        "",
        "## Tool Changes",
    ]
    tool_changes = payload.get("tool_changes") or []
    if tool_changes:
        for item in tool_changes:
            lines.append(f"- `{item['tool']}` -> `{json.dumps(item['payload'], sort_keys=True)}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Pattern Changes"])
    pattern_changes = payload.get("pattern_changes") or []
    if pattern_changes:
        for item in pattern_changes:
            lines.append(f"- `{item['tool']}` disable `{item['pattern_id']}`")
    else:
        lines.append("- None")

    lines.extend(["", "## Notes"])
    notes = payload.get("notes") or []
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- None")

    lines.extend(["", "## Failures"])
    failures = payload.get("failures") or []
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    token = (args.token or os.environ.get("CODACY_API_TOKEN", "")).strip()
    if not token:
        print("CODACY_API_TOKEN is missing", file=sys.stderr)
        return 1

    provider = validate_slug(args.provider.lower(), field_name="provider")
    owner = validate_slug(args.owner, field_name="owner")
    repo = validate_slug(args.repo, field_name="repo")
    commit_sha = validate_commit_sha(args.commit)

    notes: list[str] = []
    failures: list[str] = []
    tool_changes: list[dict[str, Any]] = []
    pattern_changes: list[dict[str, Any]] = []

    try:
        tools = _list_tools(provider=provider, owner=owner, repo=repo, token=token)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    tools_by_name = {tool.get("name"): tool for tool in tools if isinstance(tool, dict) and tool.get("name")}

    for tool_name, tool in sorted(tools_by_name.items()):
        settings = tool.get("settings") if isinstance(tool.get("settings"), dict) else {}
        payload, tool_notes = _planned_tool_payload(tool_name, settings)
        notes.extend(tool_notes)
        if payload is None:
            continue
        tool_changes.append({
            "tool": tool_name,
            "payload": payload,
        })
        if args.dry_run:
            continue
        try:
            _configure_tool(
                provider=provider,
                owner=owner,
                repo=repo,
                token=token,
                tool_uuid=validate_slug(str(tool["uuid"]), field_name=f"{tool_name} uuid"),
                payload=payload,
            )
        except Exception as exc:
            failures.append(str(exc))

    for tool_name, pattern_ids in DISABLED_PATTERNS_BY_TOOL.items():
        tool = tools_by_name.get(tool_name)
        if not isinstance(tool, dict):
            notes.append(f"{tool_name}: tool not present in repository settings")
            continue
        tool_uuid = validate_slug(str(tool["uuid"]), field_name=f"{tool_name} uuid")
        for pattern_id in sorted(pattern_ids):
            pattern_changes.append({"tool": tool_name, "pattern_id": pattern_id})
            if args.dry_run:
                continue
            try:
                _disable_pattern(
                    provider=provider,
                    owner=owner,
                    repo=repo,
                    token=token,
                    tool_uuid=tool_uuid,
                    pattern_id=pattern_id,
                )
            except Exception as exc:
                failures.append(str(exc))

    if not failures and not args.dry_run:
        try:
            _reanalyze_commit(provider=provider, owner=owner, repo=repo, token=token, commit_sha=commit_sha)
            notes.append(f"Triggered Codacy reanalysis for {commit_sha}")
        except Exception as exc:
            failures.append(str(exc))

    status = "pass" if not failures else "fail"
    payload = {
        "status": status,
        "provider": provider,
        "owner": owner,
        "repo": repo,
        "commit": commit_sha,
        "dry_run": args.dry_run,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tool_changes": tool_changes,
        "pattern_changes": pattern_changes,
        "notes": notes,
        "failures": failures,
    }

    try:
        write_workspace_json(raw_path=args.out_json, fallback="codacy-tool-sync/codacy-sync.json", payload=payload)
        md_path = write_workspace_text(raw_path=args.out_md, fallback="codacy-tool-sync/codacy-sync.md", text=_render_md(payload))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(md_path.read_text(encoding="utf-8"), end="")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
