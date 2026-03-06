#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from _security_import import load_security_helpers

_security_helpers = load_security_helpers(__file__)
build_https_url = _security_helpers.build_https_url
validate_commit_sha = _security_helpers.validate_commit_sha
validate_slug = _security_helpers.validate_slug
request_https_json = _security_helpers.request_https_json
write_workspace_json = _security_helpers.write_workspace_json
write_workspace_text = _security_helpers.write_workspace_text

CODACY_HOST = "api.codacy.com"
NONE_MARKDOWN_ITEM = "- None"
DISABLED_TOOL_NAMES = {
    "CSSLint (deprecated)",
    "ESLint",
    "ESLint (deprecated)",
    "JSHint (deprecated)",
    "Pylint (deprecated)",
    "TSLint (deprecated)",
}
CONFIG_FILE_TOOL_NAMES = {
    "Bandit",
    "ESLint",
    "ESLint (deprecated)",
    "ESLint9",
    "Prospector",
    "Pylint",
    "Pylint (deprecated)",
    "Ruff",
    "Stylelint",
    "TSLint",
    "TSLint (deprecated)",
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
    payload_bytes = b"" if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "event-link-codacy-tool-sync",
        "api-token": token,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    parsed_payload, _response_headers, status = request_https_json(
        url,
        method=method.upper(),
        headers=headers,
        body=payload_bytes,
        timeout=30,
        allowed_hosts={CODACY_HOST},
    )
    raw_text = "" if parsed_payload is None else json.dumps(parsed_payload, sort_keys=True)
    return status, parsed_payload, raw_text


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
        if not uses_config:
            payload["useConfigurationFile"] = True
        if not has_config:
            notes.append(f"{tool_name}: configuration file not detected by Codacy yet; requesting config-file mode anyway")

    return (payload or None), notes


def _append_markdown_section(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend(["", f"## {title}"])
    if items:
        lines.extend(items)
        return
    lines.append(NONE_MARKDOWN_ITEM)


def _tool_uuid(tool_name: str, tool: dict[str, Any]) -> str:
    return validate_slug(str(tool["uuid"]), field_name=f"{tool_name} uuid")


def _tools_by_name(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(tool["name"]): tool for tool in tools if isinstance(tool, dict) and tool.get("name")}


def _is_standard_managed_tool_conflict(message: str) -> bool:
    return "HTTP 409" in message and "enabled by a standard" in message


def _is_reanalysis_forbidden(message: str) -> bool:
    return "HTTP 403" in message and "Operation is not authorized" in message


def _config_only_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("useConfigurationFile") is True:
        return {"useConfigurationFile": True}
    return None


def _sync_tool_settings(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    tools_by_name: dict[str, dict[str, Any]],
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    notes: list[str] = []
    failures: list[str] = []
    tool_changes: list[dict[str, Any]] = []

    for tool_name, tool in sorted(tools_by_name.items()):
        settings = tool.get("settings") if isinstance(tool.get("settings"), dict) else {}
        payload, tool_notes = _planned_tool_payload(tool_name, settings)
        notes.extend(tool_notes)
        if payload is None:
            continue
        tool_changes.append({"tool": tool_name, "payload": payload})
        if dry_run:
            continue
        tool_uuid = _tool_uuid(tool_name, tool)
        try:
            _configure_tool(
                provider=provider,
                owner=owner,
                repo=repo,
                token=token,
                tool_uuid=tool_uuid,
                payload=payload,
            )
        except Exception as exc:
            message = str(exc)
            if _is_standard_managed_tool_conflict(message):
                config_payload = _config_only_payload(payload)
                if config_payload is not None:
                    notes.append(
                        f"{tool_name}: managed by Codacy standard; retrying config-file mode without disable request"
                    )
                    try:
                        _configure_tool(
                            provider=provider,
                            owner=owner,
                            repo=repo,
                            token=token,
                            tool_uuid=tool_uuid,
                            payload=config_payload,
                        )
                    except Exception as retry_exc:
                        failures.append(str(retry_exc))
                    else:
                        continue
                notes.append(f"{tool_name}: managed by Codacy standard; skipping disable request")
                continue
            failures.append(message)

    return tool_changes, notes, failures


def _sync_pattern_settings(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    tools_by_name: dict[str, dict[str, Any]],
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    notes: list[str] = []
    failures: list[str] = []
    pattern_changes: list[dict[str, Any]] = []

    for tool_name, pattern_ids in DISABLED_PATTERNS_BY_TOOL.items():
        tool = tools_by_name.get(tool_name)
        if not isinstance(tool, dict):
            notes.append(f"{tool_name}: tool not present in repository settings")
            continue
        tool_uuid = _tool_uuid(tool_name, tool)
        for pattern_id in sorted(pattern_ids):
            pattern_changes.append({"tool": tool_name, "pattern_id": pattern_id})
            if dry_run:
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

    return pattern_changes, notes, failures


def _trigger_reanalysis(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    commit_sha: str,
    dry_run: bool,
) -> tuple[list[str], list[str]]:
    if dry_run:
        return [], []
    try:
        _reanalyze_commit(provider=provider, owner=owner, repo=repo, token=token, commit_sha=commit_sha)
    except Exception as exc:
        message = str(exc)
        if _is_reanalysis_forbidden(message):
            return ["Codacy reanalysis not authorized for this token; waiting for normal Codacy analysis"], []
        return [], [message]
    return [f"Triggered Codacy reanalysis for {commit_sha}"], []


def _build_payload(
    *,
    context: dict[str, Any],
    tool_changes: list[dict[str, Any]],
    pattern_changes: list[dict[str, Any]],
    notes: list[str],
    failures: list[str],
) -> dict[str, Any]:
    return {
        "status": "pass" if not failures else "fail",
        **context,
        "tool_changes": tool_changes,
        "pattern_changes": pattern_changes,
        "notes": notes,
        "failures": failures,
    }


def _sync_context(*, provider: str, owner: str, repo: str, commit_sha: str, dry_run: bool) -> dict[str, Any]:
    return {
        "provider": provider,
        "owner": owner,
        "repo": repo,
        "commit": commit_sha,
        "dry_run": dry_run,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _apply_reanalysis_if_clean(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    commit_sha: str,
    dry_run: bool,
    notes: list[str],
    failures: list[str],
) -> None:
    if failures:
        return
    reanalysis_notes, reanalysis_failures = _trigger_reanalysis(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        commit_sha=commit_sha,
        dry_run=dry_run,
    )
    notes.extend(reanalysis_notes)
    failures.extend(reanalysis_failures)


def _sync_changes(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    tools_by_name: dict[str, dict[str, Any]],
    dry_run: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    tool_changes, notes, failures = _sync_tool_settings(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        tools_by_name=tools_by_name,
        dry_run=dry_run,
    )
    pattern_changes, pattern_notes, pattern_failures = _sync_pattern_settings(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        tools_by_name=tools_by_name,
        dry_run=dry_run,
    )
    notes.extend(pattern_notes)
    failures.extend(pattern_failures)
    return tool_changes, pattern_changes, notes, failures


def _run_sync(
    *,
    provider: str,
    owner: str,
    repo: str,
    token: str,
    commit_sha: str,
    dry_run: bool,
) -> dict[str, Any]:
    tools_by_name = _tools_by_name(_list_tools(provider=provider, owner=owner, repo=repo, token=token))
    tool_changes, pattern_changes, notes, failures = _sync_changes(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        tools_by_name=tools_by_name,
        dry_run=dry_run,
    )
    _apply_reanalysis_if_clean(
        provider=provider,
        owner=owner,
        repo=repo,
        token=token,
        commit_sha=commit_sha,
        dry_run=dry_run,
        notes=notes,
        failures=failures,
    )
    context = _sync_context(provider=provider, owner=owner, repo=repo, commit_sha=commit_sha, dry_run=dry_run)
    return _build_payload(
        context=context,
        tool_changes=tool_changes,
        pattern_changes=pattern_changes,
        notes=notes,
        failures=failures,
    )


def _tool_change_lines(payload: dict[str, Any]) -> list[str]:
    return [
        f"- `{item['tool']}` -> `{json.dumps(item['payload'], sort_keys=True)}`"
        for item in payload.get("tool_changes") or []
    ]


def _pattern_change_lines(payload: dict[str, Any]) -> list[str]:
    return [f"- `{item['tool']}` disable `{item['pattern_id']}`" for item in payload.get("pattern_changes") or []]


def _prefixed_lines(items: list[str], prefix: str = "- ") -> list[str]:
    return [f"{prefix}{item}" for item in items]


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Codacy Tool Sync",
        "",
        f"- Status: `{payload['status']}`",
        f"- Repository: `{payload['owner']}/{payload['repo']}`",
        f"- Commit reanalyzed: `{payload['commit']}`",
        f"- Dry run: `{payload['dry_run']}`",
        f"- Timestamp (UTC): `{payload['timestamp_utc']}`",
    ]
    _append_markdown_section(lines, "Tool Changes", _tool_change_lines(payload))
    _append_markdown_section(lines, "Pattern Changes", _pattern_change_lines(payload))
    _append_markdown_section(lines, "Notes", _prefixed_lines(list(payload.get("notes") or [])))
    _append_markdown_section(lines, "Failures", _prefixed_lines(list(payload.get("failures") or [])))
    return "\n".join(lines) + "\n"

def _resolve_token(cli_token: str) -> str:
    return (cli_token or os.environ.get("CODACY_API_TOKEN", "")).strip()


def main() -> int:
    args = _parse_args()
    token = _resolve_token(args.token)
    if not token:
        print("CODACY_API_TOKEN is missing", file=sys.stderr)
        return 1

    provider = validate_slug(args.provider.lower(), field_name="provider")
    owner = validate_slug(args.owner, field_name="owner")
    repo = validate_slug(args.repo, field_name="repo")
    commit_sha = validate_commit_sha(args.commit)

    try:
        payload = _run_sync(
            provider=provider,
            owner=owner,
            repo=repo,
            token=token,
            commit_sha=commit_sha,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        write_workspace_json(raw_path=args.out_json, fallback="codacy-tool-sync/codacy-sync.json", payload=payload)
        md_path = write_workspace_text(raw_path=args.out_md, fallback="codacy-tool-sync/codacy-sync.md", text=_render_md(payload))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(md_path.read_text(encoding="utf-8"), end="")
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

