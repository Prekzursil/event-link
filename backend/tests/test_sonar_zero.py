from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    module_path = REPO_ROOT / "scripts" / "quality" / "check_sonar_zero.py"
    parent = str(module_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("check_sonar_zero", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pull_request_summary_uses_scoped_status_counts() -> None:
    module = _load_module()

    def fake_request_json(url: str, auth_header: str):
        assert "project_pull_requests/list" in url
        assert auth_header == "auth"
        return {
            "pullRequests": [
                {
                    "key": "97",
                    "status": {"qualityGateStatus": "OK", "bugs": 0, "vulnerabilities": 0, "codeSmells": 0},
                    "commit": {"sha": "abc123abc123abc123abc123abc123abc123abcd"},
                }
            ]
        }

    module._request_json = fake_request_json

    open_issues, quality_gate, commit_sha = module._pull_request_summary(
        api_base="https://sonarcloud.io",
        auth="auth",
        project_key="Prekzursil_event-link",
        pull_request="97",
    )

    assert open_issues == 0
    assert quality_gate == "OK"
    assert commit_sha == "abc123abc123abc123abc123abc123abc123abcd"


def test_evaluate_sonar_waits_for_expected_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    summaries = [
        (1, "ERROR", "oldoldoldoldoldoldoldoldoldoldoldoldoldold"),
        (0, "OK", "0123456789abcdef0123456789abcdef01234567"),
    ]
    sleeps: list[int] = []

    monkeypatch.setattr(module, "_current_summary", lambda **_kwargs: summaries.pop(0))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    status, open_issues, quality_gate, findings = module._evaluate_sonar(
        runtime={
            "token": "token",
            "api_base": "https://sonarcloud.io",
            "project_key": "Prekzursil_event-link",
            "branch": "",
            "pull_request": "97",
            "expected_commit": "0123456789abcdef0123456789abcdef01234567",
        },
        timeout_seconds=30,
        poll_seconds=7,
        findings=[],
    )

    assert status == "pass"
    assert open_issues == 0
    assert quality_gate == "OK"
    assert findings == []
    assert sleeps == [7]


def test_evaluate_sonar_fails_when_expected_commit_never_arrives(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    summaries = [(0, "OK", "feedfeedfeedfeedfeedfeedfeedfeedfeedfeed")] * 2
    timestamps = iter([0, 2, 4])

    monkeypatch.setattr(module, "_current_summary", lambda **_kwargs: summaries.pop(0))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(module.time, "time", lambda: next(timestamps))

    status, open_issues, quality_gate, findings = module._evaluate_sonar(
        runtime={
            "token": "token",
            "api_base": "https://sonarcloud.io",
            "project_key": "Prekzursil_event-link",
            "branch": "",
            "pull_request": "97",
            "expected_commit": "0123456789abcdef0123456789abcdef01234567",
        },
        timeout_seconds=1,
        poll_seconds=1,
        findings=[],
    )

    assert status == "fail"
    assert open_issues is None
    assert quality_gate is None
    assert findings == [
        "Sonar API request failed: Sonar has not analyzed commit 0123456789abcdef0123456789abcdef01234567; latest analyzed commit is feedfeedfeedfeedfeedfeedfeedfeedfeedfeed."
    ]
