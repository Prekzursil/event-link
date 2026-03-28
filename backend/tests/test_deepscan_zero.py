from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    module_path = REPO_ROOT / "scripts" / "quality" / "check_deepscan_zero.py"
    parent = str(module_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("check_deepscan_zero", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_module_inserts_parent_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = REPO_ROOT / "scripts" / "quality" / "check_deepscan_zero.py"
    parent = str(module_path.parent)
    original_path = list(sys.path)
    trimmed_path = [entry for entry in original_path if entry != parent]
    monkeypatch.setattr(sys, "path", trimmed_path)

    module = _load_module()

    assert module is not None
    assert sys.path[0] == parent


def test_load_module_raises_when_spec_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="Unable to load module"):
        _load_module()


def test_parse_dashboard_url_ids_from_fragment() -> None:
    module = _load_module()

    ids = module._parse_dashboard_url_ids(
        "https://deepscan.io/dashboard/#view=project&tid=29074&pid=31139&bid=1008135&subview=pull-request&prid=2297171"
    )

    assert ids == {
        "team_id": "29074",
        "project_id": "31139",
        "branch_id": "1008135",
        "pull_request_id": "2297171",
    }


def test_resolve_open_issues_uses_public_pr_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    requested: list[str] = []

    def fake_github_status_payload(*, owner: str, repo: str, sha: str, github_token: str):
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == "f048fe7022acca4e5159015af0db0d6fef56137b"
        assert github_token == "gh-token"
        return {
            "statuses": [
                {
                    "context": "DeepScan",
                    "target_url": (
                        "https://deepscan.io/dashboard/#view=project&tid=29074&pid=31139&bid=1008135"
                        "&subview=pull-request&prid=2297171"
                    ),
                }
            ]
        }

    responses = {
        "https://deepscan.io/api/teams/29074/projects/31139/pulls/2297171": {
            "data": {
                "ownerBid": 1009136,
                "headAid": 3694745,
            }
        },
        "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745": {
            "data": {"outstandingDefectCount": 1}
        },
    }

    def fake_request_json(url: str, token: str):
        requested.append(url)
        return responses[url]

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)
    monkeypatch.setattr(module, "_request_json", fake_request_json)

    open_issues, source_url = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="f048fe7022acca4e5159015af0db0d6fef56137b",
        github_token="gh-token",
    )

    assert open_issues == 1
    assert source_url == "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745"
    assert requested == [
        "https://deepscan.io/api/teams/29074/projects/31139/pulls/2297171",
        "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745",
    ]


def test_evaluate_deepscan_fails_when_public_count_is_nonzero() -> None:
    module = _load_module()

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="f048fe7022acca4e5159015af0db0d6fef56137b",
        github_token="gh-token",
        findings=[],
        resolver=lambda **_kwargs: (
            2,
            "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745",
        ),
    )

    assert status == "fail"
    assert open_issues == 2
    assert source_url == "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745"
    assert findings == ["DeepScan reports 2 open issues (expected 0)."]


def test_resolve_open_issues_falls_back_to_deepsource_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()

    def fake_github_status_payload(*, owner: str, repo: str, sha: str, github_token: str):
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == "6d64df2d1be6d0d1225294b9ff979b98a5e712bf"
        assert github_token == "gh-token"
        return {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "failure",
                    "description": "Analysis failed: Blocking issues or failing metrics found",
                    "target_url": (
                        "https://app.deepsource.com/gh/Prekzursil/event-link/"
                        "run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/"
                    ),
                }
            ]
        }

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
    )

    assert resolved == (
        1,
        "https://app.deepsource.com/gh/Prekzursil/event-link/run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/",
        ["DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"],
    )


def test_evaluate_deepscan_uses_provider_findings_when_present() -> None:
    module = _load_module()

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
        findings=[],
        resolver=lambda **_kwargs: (
            1,
            "https://app.deepsource.com/gh/Prekzursil/event-link/run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/",
            ["DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"],
        ),
    )

    assert status == "fail"
    assert open_issues == 1
    assert source_url == "https://app.deepsource.com/gh/Prekzursil/event-link/run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/"
    assert findings == ["DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"]


def test_resolve_open_issues_waits_for_deepsource_pending_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    success_url = "https://app.deepsource.com/gh/Prekzursil/event-link/run/ready/javascript/"
    payloads = [
        {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "pending",
                    "description": "Analysis in progress...",
                    "target_url": success_url,
                }
            ]
        },
        {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "pending",
                    "description": "Analysis in progress...",
                    "target_url": success_url,
                }
            ]
        },
        {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "success",
                    "description": "Analysis complete",
                    "target_url": success_url,
                }
            ]
        },
    ]
    sleeps: list[float] = []

    monkeypatch.setattr(
        module,
        "_github_status_payload",
        lambda **_kwargs: payloads.pop(0),
    )
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
    )

    assert resolved == (0, success_url, [])
    assert sleeps == [module.PROVIDER_STATUS_RETRY_DELAY_SECONDS]


def test_resolve_open_issues_retries_until_provider_statuses_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    success_url = "https://app.deepsource.com/gh/Prekzursil/event-link/run/available/javascript/"
    payloads = [
        {"statuses": []},
        {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "success",
                    "description": "Analysis complete",
                    "target_url": success_url,
                }
            ]
        },
        {
            "statuses": [
                {
                    "context": "DeepSource: JavaScript",
                    "state": "success",
                    "description": "Analysis complete",
                    "target_url": success_url,
                }
            ]
        },
    ]
    sleeps: list[float] = []

    monkeypatch.setattr(module, "_github_status_payload", lambda **_kwargs: payloads.pop(0))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
    )

    assert resolved == (0, success_url, [])
    assert sleeps == [module.PROVIDER_STATUS_RETRY_DELAY_SECONDS]


def test_evaluate_deepscan_fails_when_provider_analysis_is_still_pending() -> None:
    module = _load_module()

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
        findings=[],
        resolver=lambda **_kwargs: (
            0,
            "https://app.deepsource.com/gh/Prekzursil/event-link/run/pending/javascript/",
            ["DeepSource analysis is still in progress."],
        ),
    )

    assert status == "fail"
    assert open_issues == 0
    assert source_url == "https://app.deepsource.com/gh/Prekzursil/event-link/run/pending/javascript/"
    assert findings == ["DeepSource analysis is still in progress."]


def test_wait_for_deepscan_dashboard_url_retries_until_status_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    dashboard_url = (
        "https://deepscan.io/dashboard/#view=project&tid=29074&pid=31139&bid=1008135"
        "&subview=pull-request&prid=2297205"
    )
    payloads = [
        {"statuses": []},
        {"statuses": [{"context": "DeepScan", "target_url": dashboard_url}]},
    ]
    sleeps: list[float] = []

    def fake_github_status_payload(*, owner: str, repo: str, sha: str, github_token: str):
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == "2a1fcc315ff970968cb44f4be08ca270733c3c8f"
        assert github_token == "gh-token"
        return payloads.pop(0)

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: sleeps.append(seconds))

    resolved = module._wait_for_deepscan_dashboard_url(
        owner="Prekzursil",
        repo="event-link",
        sha="2a1fcc315ff970968cb44f4be08ca270733c3c8f",
        github_token="gh-token",
    )

    assert resolved == dashboard_url
    assert sleeps == [module.STATUS_RETRY_DELAY_SECONDS]
