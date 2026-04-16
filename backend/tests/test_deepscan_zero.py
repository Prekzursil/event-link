"""Tests for the deepscan zero behavior."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEEPSCAN_PUBLIC_SHA = "f048fe7022acca4e5159015af0db0d6fef56137b"
DEEPSOURCE_STATUS_SHA = "6d64df2d1be6d0d1225294b9ff979b98a5e712bf"
DEEPSCAN_DASHBOARD_SHA = "2a1fcc315ff970968cb44f4be08ca270733c3c8f"

_DS_API = "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136"
DEEPSCAN_PUBLIC_API = f"{_DS_API}/analyses/3694745"
_DS_DASHBOARD = "https://deepscan.io/dashboard/#view=project&tid=29074&pid=31139"
DEEPSCAN_DASHBOARD_URL = (
    f"{_DS_DASHBOARD}&bid=1008135&subview=pull-request&prid=2297171"
)
DEEPSCAN_DASHBOARD_SHORT = f"{_DS_DASHBOARD}&bid=1008135"
DS_RUN_BASE = "https://app.deepsource.com/gh/Prekzursil/event-link/run"
DS_RUN_URL_PRIMARY = f"{DS_RUN_BASE}/49f1d1ef-93f"


def _load_module():
    """Import the DeepScan quality script directly from the repo checkout."""
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


def _status_payload(*statuses: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """Build a compact GitHub combined-status payload for tests."""
    return {"statuses": list(statuses)}


def _deepsource_status(
    *, state: str, target_url: str, description: str
) -> dict[str, str]:
    """Create a DeepSource-flavored commit-status payload."""
    return {
        "context": "DeepSource: JavaScript",
        "state": state,
        "description": description,
        "target_url": target_url,
    }


def _public_pr_responses() -> dict[str, dict[str, dict[str, int]]]:
    """Provide deterministic public DeepScan API responses for PR analysis lookups."""
    return {
        "https://deepscan.io/api/teams/29074/projects/31139/pulls/2297171": {
            "data": {"ownerBid": 1009136, "headAid": 3694745}
        },
        "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745": {
            "data": {"outstandingDefectCount": 1}
        },
    }


def test_load_module_inserts_parent_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure the helper prepends the script directory before importing."""
    module_path = REPO_ROOT / "scripts" / "quality" / "check_deepscan_zero.py"
    parent = str(module_path.parent)
    original_path = list(sys.path)
    trimmed_path = [entry for entry in original_path if entry != parent]
    monkeypatch.setattr(sys, "path", trimmed_path)

    module = _load_module()

    assert module is not None
    assert sys.path[0] == parent


def test_load_module_raises_when_spec_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail loudly when the target module cannot be resolved from disk."""
    monkeypatch.setattr(
        importlib.util, "spec_from_file_location", lambda *_args, **_kwargs: None
    )

    with pytest.raises(RuntimeError, match="Unable to load module"):
        _load_module()


def test_parse_dashboard_url_ids_from_fragment() -> None:
    """Extract team, project, branch, and PR identifiers from dashboard fragments."""
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


def test_resolve_open_issues_uses_public_pr_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve open issues from the public PR analysis endpoints when available."""
    module = _load_module()
    requested: list[str] = []

    def fake_github_status_payload(
        *, owner: str, repo: str, sha: str, github_token: str
    ):
        """Return a deterministic public DeepScan commit-status payload."""
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == DEEPSCAN_PUBLIC_SHA
        assert github_token == "gh-token"
        return _status_payload(
            {
                "context": "DeepScan",
                "target_url": (
                    "https://deepscan.io/dashboard/#view=project&tid=29074&pid=31139&bid=1008135"
                    "&subview=pull-request&prid=2297171"
                ),
            }
        )

    responses = _public_pr_responses()

    def fake_request_json(url: str, token: str):
        """Serve canned public API responses and record the requested URLs."""
        requested.append(url)
        return responses[url]

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)
    monkeypatch.setattr(module, "_request_json", fake_request_json)
    expected_source_url = (
        "https://deepscan.io/api/teams/29074/projects/31139/"
        "branches/1009136/analyses/3694745"
    )

    open_issues, source_url = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha=DEEPSCAN_PUBLIC_SHA,
        github_token="gh-token",
    )

    assert open_issues == 1
    assert source_url == expected_source_url
    assert requested == [
        "https://deepscan.io/api/teams/29074/projects/31139/pulls/2297171",
        expected_source_url,
    ]


def test_evaluate_deepscan_fails_when_public_count_is_nonzero() -> None:
    """Fail the gate when the public DeepScan analysis reports open issues."""
    module = _load_module()

    def resolve_public_count(**_kwargs):
        """Return a failing public DeepScan issue count."""
        return (
            2,
            "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745",
        )

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="f048fe7022acca4e5159015af0db0d6fef56137b",
        github_token="gh-token",
        findings=[],
        resolver=resolve_public_count,
    )

    assert status == "fail"
    assert open_issues == 2
    assert (
        source_url
        == "https://deepscan.io/api/teams/29074/projects/31139/branches/1009136/analyses/3694745"
    )
    assert findings == ["DeepScan reports 2 open issues (expected 0)."]


def test_resolve_open_issues_falls_back_to_deepsource_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use provider commit statuses when the public DeepScan API is unavailable."""
    module = _load_module()
    target_url = (
        "https://app.deepsource.com/gh/Prekzursil/event-link/"
        "run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/"
    )

    def fake_github_status_payload(
        *, owner: str, repo: str, sha: str, github_token: str
    ):
        """Return a failing DeepSource status payload for the requested commit."""
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == DEEPSOURCE_STATUS_SHA
        assert github_token == "gh-token"
        return _status_payload(
            _deepsource_status(
                state="failure",
                description="Analysis failed: Blocking issues or failing metrics found",
                target_url=target_url,
            )
        )

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha=DEEPSOURCE_STATUS_SHA,
        github_token="gh-token",
    )

    assert resolved == (
        1,
        target_url,
        [
            "DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"
        ],
    )


def test_evaluate_deepscan_uses_provider_findings_when_present() -> None:
    """Preserve provider-reported findings in the final gate output."""
    module = _load_module()

    def resolve_provider_findings(**_kwargs):
        """Return a provider failure payload with a single finding."""
        return (
            1,
            "https://app.deepsource.com/gh/Prekzursil/event-link/run/49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/",
            [
                "DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"
            ],
        )

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
        findings=[],
        resolver=resolve_provider_findings,
    )

    assert status == "fail"
    assert open_issues == 1
    assert source_url == (
        "https://app.deepsource.com/gh/Prekzursil/event-link/run/"
        "49f1d1ef-93f4-4852-98c7-fe6163d29263/javascript/"
    )
    assert findings == [
        "DeepSource: JavaScript: Analysis failed: Blocking issues or failing metrics found"
    ]


def test_resolve_open_issues_waits_for_deepsource_pending_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll until pending provider statuses settle into a terminal state."""
    module = _load_module()
    success_url = (
        "https://app.deepsource.com/gh/Prekzursil/event-link/run/ready/javascript/"
    )
    payloads = [
        _status_payload(
            _deepsource_status(
                state="pending",
                description="Analysis in progress...",
                target_url=success_url,
            )
        ),
        _status_payload(
            _deepsource_status(
                state="pending",
                description="Analysis in progress...",
                target_url=success_url,
            )
        ),
        _status_payload(
            _deepsource_status(
                state="success",
                description="Analysis complete",
                target_url=success_url,
            )
        ),
    ]
    sleeps: list[float] = []

    def next_status_payload(**_kwargs):
        """Return the next pending-or-success provider payload."""
        return payloads.pop(0)

    monkeypatch.setattr(
        module,
        "_github_status_payload",
        next_status_payload,
    )
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha=DEEPSOURCE_STATUS_SHA,
        github_token="gh-token",
    )

    assert resolved == (0, success_url, [])
    assert sleeps == [module.PROVIDER_STATUS_RETRY_DELAY_SECONDS]


def test_resolve_open_issues_retries_until_provider_statuses_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry provider-status discovery until matching statuses are published."""
    module = _load_module()
    success_url = (
        "https://app.deepsource.com/gh/Prekzursil/event-link/run/available/javascript/"
    )
    payloads = [
        {"statuses": []},
        _status_payload(
            _deepsource_status(
                state="success",
                description="Analysis complete",
                target_url=success_url,
            )
        ),
        _status_payload(
            _deepsource_status(
                state="success",
                description="Analysis complete",
                target_url=success_url,
            )
        ),
    ]
    sleeps: list[float] = []

    def next_available_status(**_kwargs):
        """Return the next provider payload once statuses become available."""
        return payloads.pop(0)

    monkeypatch.setattr(module, "_github_status_payload", next_available_status)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    resolved = module._resolve_open_issues(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha=DEEPSOURCE_STATUS_SHA,
        github_token="gh-token",
    )

    assert resolved == (0, success_url, [])
    assert sleeps == [module.PROVIDER_STATUS_RETRY_DELAY_SECONDS]


def test_evaluate_deepscan_fails_when_provider_analysis_is_still_pending() -> None:
    """Mark the gate as failed when provider analysis never reaches a terminal state."""
    module = _load_module()

    def resolve_pending_provider(**_kwargs):
        """Return a provider payload that never reaches completion."""
        return (
            0,
            "https://app.deepsource.com/gh/Prekzursil/event-link/run/pending/javascript/",
            ["DeepSource analysis is still in progress."],
        )

    status, open_issues, findings, source_url = module._evaluate_deepscan(
        token="",
        open_issues_url=None,
        repo="Prekzursil/event-link",
        sha="6d64df2d1be6d0d1225294b9ff979b98a5e712bf",
        github_token="gh-token",
        findings=[],
        resolver=resolve_pending_provider,
    )

    assert status == "fail"
    assert open_issues == 0
    assert (
        source_url
        == "https://app.deepsource.com/gh/Prekzursil/event-link/run/pending/javascript/"
    )
    assert findings == ["DeepSource analysis is still in progress."]


def test_wait_for_deepscan_dashboard_url_retries_until_status_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep polling GitHub commit statuses until a DeepScan dashboard URL appears."""
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

    def fake_github_status_payload(
        *, owner: str, repo: str, sha: str, github_token: str
    ):
        """Return the next DeepScan dashboard commit-status payload."""
        assert owner == "Prekzursil"
        assert repo == "event-link"
        assert sha == DEEPSCAN_DASHBOARD_SHA
        assert github_token == "gh-token"
        return payloads.pop(0)

    monkeypatch.setattr(module, "_github_status_payload", fake_github_status_payload)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    resolved = module._wait_for_deepscan_dashboard_url(
        owner="Prekzursil",
        repo="event-link",
        sha=DEEPSCAN_DASHBOARD_SHA,
        github_token="gh-token",
    )

    assert resolved == dashboard_url
    assert sleeps == [module.STATUS_RETRY_DELAY_SECONDS]
