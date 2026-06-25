"""Tests for the workflow contracts behavior."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def test_legacy_repo_owned_quality_workflows_have_been_removed() -> None:
    """Ensure legacy repo-owned quality workflows were removed after migration."""
    for filename in (
        "coverage-100.yml",
        "codacy-zero.yml",
        "deepscan-zero.yml",
        "semgrep-zero.yml",
        "sentry-zero.yml",
        "sonar-zero.yml",
    ):
        assert not (WORKFLOWS_DIR / filename).exists()


def test_qzp_platform_workflows_have_been_retired() -> None:
    """Ensure the Quality-Zero platform/SaaS workflows were retired.

    The repo migrated to the lean ``quality.yml`` gate (the single required
    status check alongside CodeQL), so the QZP wrapper + SaaS-analytics
    workflows no longer live in the tree.
    """
    for filename in (
        "quality-zero-gate.yml",
        "quality-zero-platform.yml",
        "quality-zero-backlog.yml",
        "quality-zero-remediation.yml",
        "codecov-analytics.yml",
        "codacy-tool-sync.yml",
    ):
        assert not (WORKFLOWS_DIR / filename).exists()


def test_lean_quality_and_security_workflows_are_present() -> None:
    """Ensure the lean quality gate, CodeQL, and app CI workflows remain."""
    for filename in ("quality.yml", "codeql.yml", "ci.yml"):
        assert (WORKFLOWS_DIR / filename).exists(), filename


def test_ci_workflow_defines_explicit_top_level_permissions() -> None:
    """Ensure the app CI workflow declares explicit top-level permissions."""
    content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
    assert "permissions: {}" in content


def test_repo_contract_files_exist_for_platform_governance() -> None:
    """Ensure repo contract files for governance and local verification exist."""
    verify = (REPO_ROOT / "scripts" / "verify").read_text(encoding="utf-8")
    deepsource = (REPO_ROOT / ".deepsource.toml").read_text(encoding="utf-8")
    qlty = (REPO_ROOT / ".qlty" / "qlty.toml").read_text(encoding="utf-8")

    assert "-m venv" in verify
    assert "ensurepip --upgrade" in verify
    assert "pytest-cov" in verify
    assert "lizard" in verify
    assert "--cov-branch" in verify
    assert "backend/tests" in verify
    assert "RUN_INTEGRATION_TESTS" in verify
    assert "npm --prefix ui ci" in verify
    assert "npm --prefix ui run test" in verify

    assert "version = 1" in deepsource
    assert "test_patterns" in deepsource
    assert (
        'skip_doc_coverage = ["module", "magic", "init", "class", "nonpublic"]'
        in deepsource
    )
    for skip_marker in (
        "skip_doc_coverage = [",
        '"arrow-function-expression"',
        '"class-declaration"',
        '"class-expression"',
        '"function-declaration"',
        '"function-expression"',
        '"method-definition"',
    ):
        assert skip_marker in deepsource

    assert 'config_version = "0"' in qlty
    assert 'mode = "block"' in qlty


def test_e2e_default_access_code_matches_seed_default() -> None:
    """Ensure the seeded default access code stays aligned with E2E helpers."""
    seed_content = (REPO_ROOT / "backend" / "seed_data.py").read_text(encoding="utf-8")
    e2e_utils_content = (REPO_ROOT / "ui" / "e2e" / "utils.ts").read_text(
        encoding="utf-8"
    )

    assert "seed-access-A1" in seed_content
    assert "seed-access-A1" in e2e_utils_content
