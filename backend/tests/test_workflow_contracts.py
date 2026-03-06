from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_GATE = REPO_ROOT / '.github' / 'workflows' / 'quality-zero-gate.yml'
DEEPSCAN_ZERO = REPO_ROOT / '.github' / 'workflows' / 'deepscan-zero.yml'
SEMGREP_ZERO = REPO_ROOT / '.github' / 'workflows' / 'semgrep-zero.yml'
WORKFLOWS_WITH_EXPLICIT_TOP_LEVEL_PERMISSIONS = [
    REPO_ROOT / '.github' / 'workflows' / 'ci.yml',
    REPO_ROOT / '.github' / 'workflows' / 'coverage-100.yml',
    REPO_ROOT / '.github' / 'workflows' / 'codecov-analytics.yml',
    REPO_ROOT / '.github' / 'workflows' / 'quality-zero-gate.yml',
    REPO_ROOT / '.github' / 'workflows' / 'codacy-zero.yml',
    REPO_ROOT / '.github' / 'workflows' / 'codacy-tool-sync.yml',
    REPO_ROOT / '.github' / 'workflows' / 'deepscan-zero.yml',
    REPO_ROOT / '.github' / 'workflows' / 'sentry-zero.yml',
    REPO_ROOT / '.github' / 'workflows' / 'sonar-zero.yml',
    REPO_ROOT / '.github' / 'workflows' / 'snyk-zero.yml',
]


def test_quality_zero_gate_requires_semgrep_zero_not_snyk_zero() -> None:
    content = QUALITY_GATE.read_text(encoding='utf-8')

    assert '--required-context "Semgrep Zero"' in content
    assert '--required-context "Snyk Zero"' not in content


def test_semgrep_zero_workflow_exists_and_supports_pr_and_dispatch() -> None:
    assert SEMGREP_ZERO.is_file()

    content = SEMGREP_ZERO.read_text(encoding='utf-8')
    assert 'name: Semgrep Zero' in content
    assert 'pull_request:' in content
    assert 'workflow_dispatch:' in content
    assert 'name: Semgrep Zero' in content


def test_selected_workflows_define_top_level_permissions_floor() -> None:
    for workflow in WORKFLOWS_WITH_EXPLICIT_TOP_LEVEL_PERMISSIONS:
        content = workflow.read_text(encoding='utf-8')
        assert 'permissions: {}' in content, workflow.name


def test_codacy_tool_sync_workflow_dispatch_has_no_inputs() -> None:
    content = (REPO_ROOT / '.github' / 'workflows' / 'codacy-tool-sync.yml').read_text(encoding='utf-8')

    assert 'workflow_dispatch:' in content
    assert 'inputs:' not in content


def test_ci_and_coverage_workflows_install_lizard_for_backend_quality_checks() -> None:
    ci_content = (REPO_ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    coverage_content = (REPO_ROOT / '.github' / 'workflows' / 'coverage-100.yml').read_text(encoding='utf-8')

    assert 'lizard' in ci_content
    assert 'lizard' in coverage_content


def test_deepscan_zero_workflow_has_github_status_fallback_inputs() -> None:
    content = DEEPSCAN_ZERO.read_text(encoding='utf-8')

    assert 'GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}' in content
    assert 'GITHUB_REPOSITORY: ${{ github.repository }}' in content
    assert 'TARGET_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in content
    assert '--repo "${GITHUB_REPOSITORY}"' in content
    assert '--sha "${TARGET_SHA}"' in content
