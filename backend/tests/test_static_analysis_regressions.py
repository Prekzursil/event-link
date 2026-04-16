"""Tests for the static analysis regressions behavior."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_PACKAGE_JSON = REPO_ROOT / "ui" / "package.json"
ANALYZER_REGRESSION_TARGETS = {
    REPO_ROOT / "backend" / "app" / "api.py": [
        "payload.is_active",
        "user.is_active",
        "models.RecommenderModel.is_active",
    ],
    REPO_ROOT / "backend" / "app" / "task_queue.py": [
        "models.RecommenderModel.is_active",
        "active.is_active",
        "previous.is_active",
    ],
    REPO_ROOT / "backend" / "main.py": [
        ".is_unspecified",
    ],
    REPO_ROOT / "backend" / "scripts" / "recompute_recommendations_ml.py": [
        "models.RecommenderModel.is_active",
        "existing_model.is_active",
    ],
}
EXACT_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9][A-Za-z0-9.+-]*)?$")


def test_ui_package_versions_are_exact() -> None:
    """Verifies ui package versions are exact behavior."""
    package_json = json.loads(UI_PACKAGE_JSON.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for section_name in ("dependencies", "devDependencies"):
        for package_name, version in package_json.get(section_name, {}).items():
            if not EXACT_VERSION_RE.fullmatch(version):
                offenders.append(f"{section_name}:{package_name}={version}")

    assert offenders == [], offenders


def test_no_current_is_prefix_attribute_regressions() -> None:
    """Verifies no current is prefix attribute regressions behavior."""
    offenders: list[str] = []

    for path, snippets in ANALYZER_REGRESSION_TARGETS.items():
        content = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in content:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{snippet}")

    assert offenders == [], offenders


def test_ui_package_versions_are_exact_reports_offenders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies ui package versions are exact reports offenders behavior."""
    package_json = tmp_path / "package.json"
    package_json.write_text(
        json.dumps({"dependencies": {"react": "^19.1.0"}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "UI_PACKAGE_JSON", package_json)

    with pytest.raises(AssertionError, match=r"dependencies:react=\^19\.1\.0"):
        test_ui_package_versions_are_exact()


def test_no_current_is_prefix_attribute_regressions_reports_offenders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies no current is prefix attribute regressions reports offenders behavior."""
    module_path = tmp_path / "backend" / "app" / "api.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("payload.is_active = True\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        sys.modules[__name__],
        "ANALYZER_REGRESSION_TARGETS",
        {module_path: ["payload.is_active"]},
    )

    with pytest.raises(AssertionError) as exc_info:
        test_no_current_is_prefix_attribute_regressions()

    message = str(exc_info.value).replace("\\", "/")
    assert "api.py:payload.is_active" in message
