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


def test_issues_search_request_scopes_results_by_branch() -> None:
    module = _load_module()
    captured: dict[str, object] = {}

    def _fake_request_json(**kwargs):
        captured.update(kwargs)
        return 200, {"total": 0}

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "_request_json", _fake_request_json)
    try:
        status_code, payload = module._issues_search_request(
            provider="gh",
            owner="Prekzursil",
            repo="event-link",
            token="token",
            branch="fix/true-zero-and-coverage-100-v3",
        )
    finally:
        monkeypatch.undo()

    assert status_code == 200
    assert payload == {"total": 0}
    assert captured["path"].endswith("/issues/search?limit=1")
    assert captured["body"] == {"branchName": "fix/true-zero-and-coverage-100-v3"}


def test_evaluate_candidate_reports_branch_open_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_issues_search_request",
        lambda **_kwargs: (200, {"total": 43}),
    )

    status, open_issues, findings = module._evaluate_candidate(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        branch="fix/true-zero-and-coverage-100-v3",
    )

    assert status == "fail"
    assert open_issues == 43
    assert findings == ["Codacy reports 43 open issues (expected 0)."]
