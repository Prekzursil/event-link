from __future__ import annotations

import json
import re
from pathlib import Path

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
    package_json = json.loads(UI_PACKAGE_JSON.read_text(encoding="utf-8"))
    offenders: list[str] = []

    for section_name in ("dependencies", "devDependencies"):
        for package_name, version in package_json.get(section_name, {}).items():
            if not EXACT_VERSION_RE.fullmatch(version):
                offenders.append(f"{section_name}:{package_name}={version}")

    assert offenders == [], offenders


def test_no_current_is_prefix_attribute_regressions() -> None:
    offenders: list[str] = []

    for path, snippets in ANALYZER_REGRESSION_TARGETS.items():
        content = path.read_text(encoding="utf-8")
        for snippet in snippets:
            if snippet in content:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{snippet}")

    assert offenders == [], offenders
