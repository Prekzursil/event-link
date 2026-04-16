"""Shared validation and workspace I/O helpers for quality scripts."""

from __future__ import annotations

import ipaddress
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import ParseResult, urlencode, urlparse, urlunparse

_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_HOST_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+$")
_FORBIDDEN_IP_ATTRIBUTES = (
    "is_private",
    "is_loopback",
    "is_link_local",
    "is_reserved",
    "is_multicast",
)
_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}


def _parse_https_url(raw_url: str) -> ParseResult:
    """Parse a candidate URL and reject unsupported schemes or credentials."""
    parsed = urlparse((raw_url or "").strip())
    if parsed.scheme != "https":
        raise ValueError(f"Only https URLs are allowed: {raw_url!r}")
    if parsed.username or parsed.password:
        raise ValueError(f"URL credentials are not allowed: {raw_url!r}")
    return parsed


def _normalized_hostname(parsed: ParseResult, raw_url: str) -> str:
    """Return the normalized hostname for a parsed URL."""
    if not parsed.hostname:
        raise ValueError(f"URL is missing a hostname: {raw_url!r}")
    return parsed.hostname.lower().strip(".")


def _normalized_set(values: set[str] | None) -> set[str]:
    """Normalize an optional hostname set for allowlist comparisons."""
    if values is None:
        return set()
    return {value.lower().strip(".") for value in values if value.strip(".")}


def _validate_host_allowlists(
    hostname: str,
    *,
    allowed_hosts: set[str] | None,
    allowed_host_suffixes: set[str] | None,
) -> None:
    """Validate explicit host and suffix allowlists for a target hostname."""
    normalized_hosts = _normalized_set(allowed_hosts)
    if normalized_hosts and hostname not in normalized_hosts:
        raise ValueError(f"URL host is not in allowlist: {hostname}")

    suffixes = _normalized_set(allowed_host_suffixes)
    if suffixes and not any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in suffixes):
        raise ValueError(f"URL host is not in suffix allowlist: {hostname}")


def _parse_ip_address(hostname: str) -> ipaddress._BaseAddress | None:
    """Parse a hostname as an IP address when possible."""
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        return None


def _is_forbidden_ip(ip_value: ipaddress._BaseAddress | None) -> bool:
    """Return whether an IP address points to a non-public target."""
    if ip_value is None:
        return False
    return any(bool(getattr(ip_value, attribute, False)) for attribute in _FORBIDDEN_IP_ATTRIBUTES)


def _reject_local_target(hostname: str) -> None:
    """Reject localhost and private IP targets for outbound HTTPS calls."""
    if hostname in _LOCAL_HOSTS:
        raise ValueError("Localhost URLs are not allowed.")
    if _is_forbidden_ip(_parse_ip_address(hostname)):
        raise ValueError(f"Private or local addresses are not allowed: {hostname}")


def normalize_https_url(
    raw_url: str,
    *,
    allowed_hosts: set[str] | None = None,
    allowed_host_suffixes: set[str] | None = None,
    strip_query: bool = False,
) -> str:
    """Validate user-provided URLs for CLI scripts.

    Rules:
    - https scheme only,
    - no embedded credentials,
    - reject localhost/private/link-local IP targets,
    - optional hostname allowlist,
    - optional hostname suffix allowlist.
    """
    parsed = _parse_https_url(raw_url)
    hostname = _normalized_hostname(parsed, raw_url)
    _validate_host_allowlists(
        hostname,
        allowed_hosts=allowed_hosts,
        allowed_host_suffixes=allowed_host_suffixes,
    )
    _reject_local_target(hostname)

    sanitized = parsed._replace(fragment="", params="")
    if strip_query:
        sanitized = sanitized._replace(query="")
    return urlunparse(sanitized)


def validate_slug(value: str, *, field_name: str) -> str:
    """Validate a slug-like identifier used in API paths and arguments."""
    slug = (value or "").strip()
    if not slug or not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid {field_name}: {value!r}")
    return slug


def validate_repo_full_name(value: str) -> tuple[str, str]:
    """Validate and split a GitHub-style owner/repo identifier."""
    raw = (value or "").strip()
    parts = raw.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid repo format {value!r}; expected owner/repo")
    owner = validate_slug(parts[0], field_name="repo owner")
    repo = validate_slug(parts[1], field_name="repo name")
    return owner, repo


def validate_commit_sha(value: str) -> str:
    """Validate a Git commit SHA used in provider lookups."""
    sha = (value or "").strip()
    if not _SHA_RE.fullmatch(sha):
        raise ValueError(f"Invalid commit SHA: {value!r}")
    return sha


def build_https_url(*, host: str, path: str, query: dict[str, str] | None = None) -> str:
    """Build and validate a normalized HTTPS URL from host, path, and query."""
    safe_host = (host or "").strip().lower().strip(".")
    if not _HOST_RE.fullmatch(safe_host):
        raise ValueError(f"Invalid host: {host!r}")
    normalized_path = "/" + "/".join(segment for segment in (path or "").split("/") if segment)
    encoded_query = urlencode(query or {})
    return normalize_https_url(
        urlunparse(("https", safe_host, normalized_path, "", encoded_query, "")),
        allowed_hosts={safe_host},
    )


def _decode_json_payload(raw_text: str) -> object | None:
    """Decode JSON when possible and preserve raw text otherwise."""
    raw = raw_text.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_text": raw_text}


def _open_https_request(
    request: urllib.request.Request, *, timeout: int
) -> urllib.response.addinfourl | urllib.error.HTTPError:
    """Open an HTTPS request and preserve HTTP errors as response objects."""
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler())
    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return exc


def request_https_json(
    raw_url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
    allowed_hosts: set[str] | None = None,
    allowed_host_suffixes: set[str] | None = None,
) -> tuple[object | None, dict[str, str], int]:
    """Perform an HTTPS JSON request and return payload, headers, and status."""
    safe_url = normalize_https_url(
        raw_url,
        allowed_hosts=allowed_hosts,
        allowed_host_suffixes=allowed_host_suffixes,
    )
    request = urllib.request.Request(
        safe_url,
        data=body,
        headers=headers or {},
        method=method.upper(),
    )
    response = _open_https_request(request, timeout=timeout)
    try:
        raw_text = response.read().decode("utf-8")
        payload = _decode_json_payload(raw_text)
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        status_value = getattr(response, "status", None)
        if status_value is None:
            status_value = response.getcode()
        return payload, response_headers, int(status_value)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _workspace_root(base: Path | None) -> Path:
    """Return the resolved workspace root for report writes."""
    return (base or Path.cwd()).resolve()


def _candidate_relative_path(raw_path: str, fallback: str) -> Path:
    """Build a relative output path from a raw CLI argument or fallback."""
    candidate = Path((raw_path or "").strip() or fallback).expanduser()
    if candidate.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {candidate}")
    return candidate


def _resolve_workspace_path(root: Path, candidate: Path) -> Path:
    """Resolve a candidate path beneath the workspace root."""
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace root: {candidate}") from exc
    return resolved


def _validate_resolved_path(
    resolved: Path,
    *,
    candidate: Path,
    must_exist: bool,
    must_be_file: bool,
) -> None:
    """Validate a resolved workspace path against caller requirements."""
    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {candidate}")
    if must_be_file and resolved.exists() and not resolved.is_file():
        raise ValueError(f"Path must be a regular file: {candidate}")


def resolve_workspace_relative_path(
    raw_path: str,
    *,
    fallback: str,
    base: Path | None = None,
    must_exist: bool = False,
    must_be_file: bool = False,
) -> Path:
    """Resolve a workspace-relative path without allowing path escapes."""
    root = _workspace_root(base)
    candidate = _candidate_relative_path(raw_path, fallback)
    resolved = _resolve_workspace_path(root, candidate)
    _validate_resolved_path(
        resolved,
        candidate=candidate,
        must_exist=must_exist,
        must_be_file=must_be_file,
    )
    return resolved


def build_github_api_url(
    *,
    owner: str,
    repo: str,
    resource: tuple[str, ...],
    query: dict[str, str] | None = None,
) -> str:
    """Build a validated GitHub REST API URL for a repository resource."""
    safe_owner = validate_slug(owner, field_name="repo owner")
    safe_repo = validate_slug(repo, field_name="repo name")
    path_segments = (
        "repos",
        safe_owner,
        safe_repo,
        *[validate_slug(segment, field_name="api segment") for segment in resource],
    )
    return build_https_url(
        host="api.github.com",
        path="/".join(path_segments),
        query=query,
    )


def build_github_commit_checks_url(*, owner: str, repo: str, sha: str, per_page: int = 100) -> str:
    """Build the GitHub commit check-runs API URL for a commit."""
    safe_sha = validate_commit_sha(sha)
    return build_github_api_url(
        owner=owner,
        repo=repo,
        resource=("commits", safe_sha, "check-runs"),
        query={"per_page": str(per_page)},
    )


def build_github_commit_status_url(*, owner: str, repo: str, sha: str) -> str:
    """Build the GitHub commit status API URL for a commit."""
    safe_sha = validate_commit_sha(sha)
    return build_github_api_url(
        owner=owner,
        repo=repo,
        resource=("commits", safe_sha, "status"),
    )


def write_workspace_text(
    *,
    raw_path: str,
    fallback: str,
    text: str,
    base: Path | None = None,
) -> Path:
    """Write text to a validated workspace-relative file path."""
    target = resolve_workspace_relative_path(raw_path, fallback=fallback, base=base)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def write_workspace_json(
    *,
    raw_path: str,
    fallback: str,
    payload: object,
    base: Path | None = None,
) -> Path:
    """Write JSON to a validated workspace-relative file path."""
    return write_workspace_text(
        raw_path=raw_path,
        fallback=fallback,
        text=json.dumps(payload, indent=2, sort_keys=True) + "\n",
        base=base,
    )
