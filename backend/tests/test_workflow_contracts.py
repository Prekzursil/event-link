from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_GATE = REPO_ROOT / '.github' / 'workflows' / 'quality-zero-gate.yml'
DEEPSCAN_ZERO = REPO_ROOT / '.github' / 'workflows' / 'deepscan-zero.yml'
SEMGREP_ZERO = REPO_ROOT / '.github' / 'workflows' / 'semgrep-zero.yml'
SNYK_ZERO = REPO_ROOT / '.github' / 'workflows' / 'snyk-zero.yml'
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
]


def test_quality_zero_gate_requires_semgrep_zero_not_snyk_zero() -> None:
    content = QUALITY_GATE.read_text(encoding='utf-8')

    assert '--required-context "codecov/patch"' in content
    assert '--required-context "Semgrep Zero"' in content
    assert '--required-context "Snyk Zero"' not in content


def test_semgrep_zero_workflow_exists_and_supports_pr_and_dispatch() -> None:
    assert SEMGREP_ZERO.is_file()

    content = SEMGREP_ZERO.read_text(encoding='utf-8')
    assert 'name: Semgrep Zero' in content
    assert 'pull_request:' in content
    assert 'workflow_dispatch:' in content
    assert 'name: Semgrep Zero' in content


def test_snyk_zero_workflow_has_been_removed() -> None:
    assert not SNYK_ZERO.exists()


def test_selected_workflows_define_top_level_permissions_floor() -> None:
    for workflow in WORKFLOWS_WITH_EXPLICIT_TOP_LEVEL_PERMISSIONS:
        content = workflow.read_text(encoding='utf-8')
        assert 'permissions: {}' in content, workflow.name


def test_quality_zero_gate_and_codacy_zero_workflows_enable_concurrency() -> None:
    quality_content = QUALITY_GATE.read_text(encoding='utf-8')
    codacy_content = (REPO_ROOT / '.github' / 'workflows' / 'codacy-zero.yml').read_text(encoding='utf-8')

    assert 'concurrency:' in quality_content
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in quality_content
    assert 'concurrency:' in codacy_content
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in codacy_content


def test_codacy_tool_sync_workflow_dispatch_has_no_inputs() -> None:
    content = (REPO_ROOT / '.github' / 'workflows' / 'codacy-tool-sync.yml').read_text(encoding='utf-8')

    assert 'workflow_dispatch:' in content
    assert 'inputs:' not in content


def test_ci_and_coverage_workflows_install_lizard_for_backend_quality_checks() -> None:
    ci_content = (REPO_ROOT / '.github' / 'workflows' / 'ci.yml').read_text(encoding='utf-8')
    coverage_content = (REPO_ROOT / '.github' / 'workflows' / 'coverage-100.yml').read_text(encoding='utf-8')

    assert 'lizard' in ci_content
    assert 'lizard' in coverage_content


def test_codecov_analytics_uploads_existing_reports_to_codacy() -> None:
    content = (REPO_ROOT / '.github' / 'workflows' / 'codecov-analytics.yml').read_text(encoding='utf-8')

    assert 'CODACY_API_TOKEN: ${{ secrets.CODACY_API_TOKEN }}' in content
    assert 'CODACY_ORGANIZATION_PROVIDER: gh' in content
    assert 'CODACY_USERNAME: Prekzursil' in content
    assert 'CODACY_PROJECT_NAME: ${{ github.event.repository.name }}' in content
    assert 'python -m pip install -r backend/requirements.txt pytest pytest-cov lizard' in content
    assert 'npm --prefix ui run test:unit:coverage' in content
    assert 'bash <(curl -Ls https://coverage.codacy.com/get.sh) report "${report_args[@]}"' in content


def test_deepscan_zero_workflow_has_github_status_fallback_inputs() -> None:
    content = DEEPSCAN_ZERO.read_text(encoding='utf-8')

    assert 'GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}' in content
    assert 'GITHUB_REPOSITORY: ${{ github.repository }}' in content
    assert 'TARGET_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in content
    assert '--repo "${GITHUB_REPOSITORY}"' in content
    assert '--sha "${TARGET_SHA}"' in content


def test_sonar_zero_workflow_waits_for_the_current_commit_analysis() -> None:
    content = (REPO_ROOT / '.github' / 'workflows' / 'sonar-zero.yml').read_text(encoding='utf-8')

    assert 'TARGET_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in content
    assert '--expected-commit "${TARGET_SHA}"' in content


def test_codacy_zero_workflow_uses_branch_scoped_analysis_and_provider_precheck() -> None:
    content = (REPO_ROOT / '.github' / 'workflows' / 'codacy-zero.yml').read_text(encoding='utf-8')

    assert 'CHECK_SHA: ${{ github.event.pull_request.head.sha || github.sha }}' in content
    assert 'CODACY_BRANCH: ${{ github.event.pull_request.head.ref || github.ref_name }}' in content
    assert '--required-context "Codacy Static Code Analysis"' in content
    assert '--branch "${CODACY_BRANCH}"' in content
    assert '--pr-number' not in content
    assert '--commit "${CHECK_SHA}"' not in content


def test_e2e_default_access_code_matches_seed_default() -> None:
    seed_content = (REPO_ROOT / 'backend' / 'seed_data.py').read_text(encoding='utf-8')
    e2e_utils_content = (REPO_ROOT / 'ui' / 'e2e' / 'utils.ts').read_text(encoding='utf-8')

    assert 'seed-access-A1' in seed_content
    assert 'seed-access-A1' in e2e_utils_content
