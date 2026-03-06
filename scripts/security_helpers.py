from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_HOST_RE = re.compile(r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z0-9-]+$")


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

    parsed = urlparse((raw_url or "").strip())
    if parsed.scheme != "https":
        raise ValueError(f"Only https URLs are allowed: {raw_url!r}")
    if not parsed.hostname:
        raise ValueError(f"URL is missing a hostname: {raw_url!r}")
    if parsed.username or parsed.password:
        raise ValueError(f"URL credentials are not allowed: {raw_url!r}")

    hostname = parsed.hostname.lower().strip(".")
    if allowed_hosts is not None and hostname not in {host.lower().strip(".") for host in allowed_hosts}:
        raise ValueError(f"URL host is not in allowlist: {hostname}")
    if allowed_host_suffixes is not None:
        suffixes = {suffix.lower().strip(".") for suffix in allowed_host_suffixes if suffix.strip(".")}
        if suffixes and not any(hostname == suffix or hostname.endswith(f".{suffix}") for suffix in suffixes):
            raise ValueError(f"URL host is not in suffix allowlist: {hostname}")

    try:
        ip_value = ipaddress.ip_address(hostname)
    except ValueError:
        ip_value = None

    if ip_value is not None and (
        ip_value.is_private
        or ip_value.is_loopback
        or ip_value.is_link_local
        or ip_value.is_reserved
        or ip_value.is_multicast
    ):
        raise ValueError(f"Private or local addresses are not allowed: {hostname}")

    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("Localhost URLs are not allowed.")

    sanitized = parsed._replace(fragment="", params="")
    if strip_query:
        sanitized = sanitized._replace(query="")
    return urlunparse(sanitized)


def validate_slug(value: str, *, field_name: str) -> str:
    slug = (value or "").strip()
    if not slug or not _SLUG_RE.fullmatch(slug):
        raise ValueError(f"Invalid {field_name}: {value!r}")
    return slug


def validate_repo_full_name(value: str) -> tuple[str, str]:
    raw = (value or "").strip()
    parts = raw.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid repo format {value!r}; expected owner/repo")
    owner = validate_slug(parts[0], field_name="repo owner")
    repo = validate_slug(parts[1], field_name="repo name")
    return owner, repo


def validate_commit_sha(value: str) -> str:
    sha = (value or "").strip()
    if not _SHA_RE.fullmatch(sha):
        raise ValueError(f"Invalid commit SHA: {value!r}")
    return sha


def build_https_url(*, host: str, path: str, query: dict[str, str] | None = None) -> str:
    safe_host = (host or "").strip().lower().strip(".")
    if not _HOST_RE.fullmatch(safe_host):
        raise ValueError(f"Invalid host: {host!r}")
    normalized_path = "/" + "/".join(segment for segment in (path or "").split("/") if segment)
    encoded_query = urlencode(query or {})
    return normalize_https_url(
        urlunparse(("https", safe_host, normalized_path, "", encoded_query, "")),
        allowed_hosts={safe_host},
    )


def resolve_workspace_relative_path(
    raw_path: str,
    *,
    fallback: str,
    base: Path | None = None,
    must_exist: bool = False,
    must_be_file: bool = False,
) -> Path:
    root = (base or Path.cwd()).resolve()
    candidate = Path((raw_path or "").strip() or fallback).expanduser()
    if candidate.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {candidate}")

    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace root: {candidate}") from exc

    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {candidate}")
    if must_be_file and resolved.exists() and not resolved.is_file():
        raise ValueError(f"Path must be a regular file: {candidate}")

    return resolved
