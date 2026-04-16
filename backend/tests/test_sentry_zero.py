"""Tests for the sentry zero behavior."""
import importlib.util
import sys
from pathlib import Path


def _load_module():
    """Loads the module resource."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "quality" / "check_sentry_zero.py"
    sys.path.insert(0, str(module_path.parent))
    try:
        spec = importlib.util.spec_from_file_location("check_sentry_zero", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_evaluate_sentry_skips_missing_projects() -> None:
    """Verifies evaluate sentry skips missing projects behavior."""
    module = _load_module()

    def fake_project_result(**_kwargs):
        """Implements the fake project result helper."""
        raise RuntimeError("Sentry API request failed: HTTP 404")

    module._project_result = fake_project_result

    status, project_results, findings = module._evaluate_sentry(
        token="token",
        org="prekzursil",
        safe_projects=["event-link"],
        api_base="https://sentry.io/api/0",
        findings=[],
    )

    assert status == "pass"
    assert project_results == [{"project": "event-link", "unresolved": 0, "state": "not_found"}]
    assert findings == []
