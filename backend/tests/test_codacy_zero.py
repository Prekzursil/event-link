from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    module_path = REPO_ROOT / "scripts" / "quality" / "check_codacy_zero.py"
    parent = str(module_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("check_codacy_zero", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_module_raises_when_import_spec_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    original_parent = str((REPO_ROOT / "scripts" / "quality").resolve())
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != original_parent])

    with pytest.raises(RuntimeError, match="Unable to load module"):
        _load_module()


def test_quality_new_issues_prefers_quality_section() -> None:
    module = _load_module()

    assert module._quality_new_issues(
        {
            "newIssues": 99,
            "quality": {"newIssues": 4},
        }
    ) == 4


def test_wait_for_pr_analysis_uses_pr_scope_and_current_head(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    payloads = [
        (
            200,
            {
                "isAnalysing": True,
                "pullRequest": {"headCommitSha": "oldoldoldoldoldoldoldoldoldoldoldoldoldold"},
                "quality": {"newIssues": 12},
            },
        ),
        (
            200,
            {
                "isAnalysing": False,
                "pullRequest": {"headCommitSha": "0123456789abcdef0123456789abcdef01234567"},
                "quality": {"newIssues": 0},
            },
        ),
    ]
    sleeps: list[int] = []

    monkeypatch.setattr(module, "_request_json", lambda **_kwargs: payloads.pop(0))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    status, open_issues, findings = module._wait_for_pr_analysis(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        pr_number="97",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        timeout_seconds=30,
        poll_seconds=6,
    )

    assert status == "pass"
    assert open_issues == 0
    assert findings == []
    assert sleeps == [6]


def test_wait_for_pr_analysis_reports_pr_new_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_request_json",
        lambda **_kwargs: (
            200,
            {
                "isAnalysing": False,
                "pullRequest": {"headCommitSha": "0123456789abcdef0123456789abcdef01234567"},
                "quality": {"newIssues": 43},
            },
        ),
    )

    status, open_issues, findings = module._wait_for_pr_analysis(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        pr_number="97",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        timeout_seconds=30,
        poll_seconds=5,
    )

    assert status == "fail"
    assert open_issues == 43
    assert findings == ["Codacy reports 43 PR new issues (expected 0)."]
