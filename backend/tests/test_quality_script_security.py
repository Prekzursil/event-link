"""Tests for the quality script security behavior."""

# Test fixture classes commonly have a single public method by design.
# pylint: disable=too-few-public-methods

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(relative_path: str, module_name: str):
    """Loads the module resource."""
    module_path = REPO_ROOT / relative_path
    parent = str(module_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


security_helpers = _load_module(
    "scripts/security_helpers.py", "event_link_security_helpers_tests"
)
check_required_checks = _load_module(
    "scripts/quality/check_required_checks.py",
    "event_link_check_required_checks_tests",
)


def test_load_module_rejects_missing_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies load module rejects missing loader behavior."""
    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", lambda *_args, **_kwargs: None
    )

    with pytest.raises(RuntimeError, match="Unable to load module"):
        _load_module("scripts/security_helpers.py", "event_link_missing_loader")


def test_write_workspace_text_rejects_escape(tmp_path: Path) -> None:
    """Verifies write workspace text rejects escape behavior."""
    with pytest.raises(ValueError, match="escapes workspace root"):
        security_helpers.write_workspace_text(
            raw_path="../escape.txt",
            fallback="reports/out.txt",
            text="nope",
            base=tmp_path,
        )


def test_write_workspace_json_creates_parent_and_file(tmp_path: Path) -> None:
    """Verifies write workspace json creates parent and file behavior."""
    target = security_helpers.write_workspace_json(
        raw_path="reports/output.json",
        fallback="fallback.json",
        payload={"status": "pass"},
        base=tmp_path,
    )

    assert target == tmp_path / "reports" / "output.json"
    assert target.read_text(encoding="utf-8") == '{\n  "status": "pass"\n}\n'


def test_build_github_commit_urls_use_fixed_host() -> None:
    """Verifies build github commit urls use fixed host behavior."""
    checks_url = security_helpers.build_github_commit_checks_url(
        owner="Prekzursil",
        repo="event-link",
        sha="abcdef1",
        per_page=50,
    )
    status_url = security_helpers.build_github_commit_status_url(
        owner="Prekzursil",
        repo="event-link",
        sha="abcdef1",
    )

    assert checks_url == (
        "https://api.github.com/repos/Prekzursil/event-link/commits/abcdef1/check-runs?per_page=50"
    )
    assert (
        status_url
        == "https://api.github.com/repos/Prekzursil/event-link/commits/abcdef1/status"
    )


def test_collect_contexts_captures_check_runs_and_statuses() -> None:
    """Verifies collect contexts captures check runs and statuses behavior."""
    contexts = check_required_checks._collect_contexts(
        {
            "check_runs": [
                {"name": "backend", "status": "completed", "conclusion": "success"}
            ]
        },
        {"statuses": [{"context": "codecov/patch", "state": "success"}]},
    )

    assert contexts["backend"] == {
        "state": "completed",
        "conclusion": "success",
        "source": "check_run",
    }
    assert contexts["codecov/patch"] == {
        "state": "success",
        "conclusion": "success",
        "source": "status",
    }


def test_api_get_retries_retryable_http_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies api get retries retryable http statuses behavior."""
    responses = [
        ({"message": "slow down"}, {}, 429),
        ({"check_runs": []}, {}, 200),
    ]
    sleeps: list[int] = []

    monkeypatch.setattr(
        check_required_checks,
        "request_https_json",
        lambda *_args, **_kwargs: responses.pop(0),
    )
    monkeypatch.setattr(check_required_checks.time, "sleep", sleeps.append)

    api_get = getattr(check_required_checks, "_api_get")
    payload = api_get(
        "https://api.github.com/repos/Prekzursil/event-link/commits/abcdef/check-runs",
        "token",
    )

    assert payload == {"check_runs": []}
    assert sleeps == [2]


def test_request_https_json_uses_urllib_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies request https json uses urllib request behavior."""
    calls: dict[str, object] = {}

    class _FakeResponse:
        """Fixed HTTP response object returned by the fake urllib opener."""

        status = 206

        @staticmethod
        def read() -> bytes:
            """Implements the read helper."""
            return b'{"status": "ok"}'

        @staticmethod
        def getheaders():
            """Implements the getheaders helper."""
            return [("X-Hits", "5"), ("Content-Type", "application/json")]

    class _FakeOpener:
        """Stand-in urllib opener that records each request and returns _FakeResponse."""

        @staticmethod
        def open(request, timeout=None):
            """Implements the open helper."""
            calls["request"] = {
                "method": request.get_method(),
                "url": request.full_url,
                "body": request.data,
                "headers": dict(request.header_items()),
            }
            calls["timeout"] = timeout
            return _FakeResponse()

    monkeypatch.setattr(
        security_helpers.urllib.request,
        "build_opener",
        lambda *_args, **_kwargs: _FakeOpener(),
    )

    payload, headers, status = security_helpers.request_https_json(
        "https://api.github.com/repos/Prekzursil/event-link/check-runs?per_page=1",
        method="POST",
        headers={"Accept": "application/json"},
        body=b"{}",
        allowed_hosts={"api.github.com"},
        timeout=9,
    )

    assert payload == {"status": "ok"}
    assert headers["x-hits"] == "5"
    assert status == 206
    assert calls["request"] == {
        "method": "POST",
        "url": "https://api.github.com/repos/Prekzursil/event-link/check-runs?per_page=1",
        "body": b"{}",
        "headers": {"Accept": "application/json"},
    }
    assert calls["timeout"] == 9


def test_request_https_json_rejects_non_https_url() -> None:
    """Verifies request https json rejects non https url behavior."""
    with pytest.raises(ValueError, match="Only https URLs are allowed"):
        insecure_url = "http" + "://api.github.com/repos/Prekzursil/event-link"
        security_helpers.request_https_json(insecure_url)
