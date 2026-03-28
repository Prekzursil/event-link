from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / '.github' / 'workflows'
WRAPPER_TEMPLATE_REF = '@d3aabc77c858e27cb7ade824e9fbf3dd9203f256'
MUTATION_TEMPLATE_REF = '@7268fee30f1cf796938d97fe460259f27386a8cd'


def test_quality_zero_repo_uses_platform_wrapper_workflows() -> None:
    quality_platform = (WORKFLOWS_DIR / 'quality-zero-platform.yml').read_text(encoding='utf-8')
    quality_gate = (WORKFLOWS_DIR / 'quality-zero-gate.yml').read_text(encoding='utf-8')
    analytics = (WORKFLOWS_DIR / 'codecov-analytics.yml').read_text(encoding='utf-8')

    assert 'name: Quality Zero Platform' in quality_platform
    assert WRAPPER_TEMPLATE_REF in quality_platform
    assert 'platform_repository: Prekzursil/quality-zero-platform' in quality_platform
    assert 'platform_ref: main' in quality_platform
    assert 'SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}' in quality_platform
    assert 'CODACY_API_TOKEN: ${{ secrets.CODACY_API_TOKEN }}' in quality_platform
    assert 'DEEPSCAN_API_TOKEN: ${{ secrets.DEEPSCAN_API_TOKEN }}' in quality_platform
    assert 'SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}' in quality_platform
    assert 'CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}' in quality_platform

    assert 'name: Quality Zero Gate' in quality_gate
    assert WRAPPER_TEMPLATE_REF in quality_gate
    assert 'platform_repository: Prekzursil/quality-zero-platform' in quality_gate
    assert 'platform_ref: main' in quality_gate
    assert 'secrets: inherit' not in quality_gate

    assert 'name: Codecov Analytics' in analytics
    assert WRAPPER_TEMPLATE_REF in analytics
    assert 'platform_repository: Prekzursil/quality-zero-platform' in analytics
    assert 'platform_ref: main' in analytics
    assert 'CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}' in analytics


def test_quality_zero_mutation_wrappers_are_present_and_scoped() -> None:
    backlog = (WORKFLOWS_DIR / 'quality-zero-backlog.yml').read_text(encoding='utf-8')
    remediation = (WORKFLOWS_DIR / 'quality-zero-remediation.yml').read_text(encoding='utf-8')

    assert MUTATION_TEMPLATE_REF in backlog
    assert 'lane: quality' in backlog
    assert 'CODEX_AUTH_JSON: ${{ secrets.CODEX_AUTH_JSON }}' in backlog
    assert 'secrets: inherit' not in backlog

    assert MUTATION_TEMPLATE_REF in remediation
    assert 'failure_context: Quality Zero Gate' in remediation
    assert 'CODEX_AUTH_JSON: ${{ secrets.CODEX_AUTH_JSON }}' in remediation
    assert 'workflow_run: # zizmor: ignore[dangerous-triggers]' in remediation
    assert 'secrets: inherit' not in remediation


def test_legacy_repo_owned_quality_workflows_have_been_removed() -> None:
    for filename in (
        'coverage-100.yml',
        'codacy-zero.yml',
        'deepscan-zero.yml',
        'semgrep-zero.yml',
        'sentry-zero.yml',
        'sonar-zero.yml',
    ):
        assert not (WORKFLOWS_DIR / filename).exists()


def test_ci_and_wrapper_workflows_define_explicit_top_level_permissions() -> None:
    expected_permissions = {
        'ci.yml': ['permissions: {}'],
        'quality-zero-platform.yml': [
            'permissions:',
            '  contents: read',
            '  id-token: write',
            '  pull-requests: write',
        ],
        'quality-zero-gate.yml': [
            'permissions:',
            '  contents: read',
        ],
        'codecov-analytics.yml': [
            'permissions:',
            '  contents: read',
            '  id-token: write',
        ],
        'quality-zero-backlog.yml': ['permissions: {}'],
        'quality-zero-remediation.yml': ['permissions: {}'],
        'codacy-tool-sync.yml': ['permissions: {}'],
    }

    for workflow_name, markers in expected_permissions.items():
        content = (WORKFLOWS_DIR / workflow_name).read_text(encoding='utf-8')
        for marker in markers:
            assert marker in content, workflow_name


def test_repo_contract_files_exist_for_platform_governance() -> None:
    agents = (REPO_ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    verify = (REPO_ROOT / 'scripts' / 'verify').read_text(encoding='utf-8')
    deepsource = (REPO_ROOT / '.deepsource.toml').read_text(encoding='utf-8')

    assert 'quality-zero-platform' in agents
    assert 'bash scripts/verify' in agents

    assert '-m venv' in verify
    assert 'ensurepip --upgrade' in verify
    assert 'pytest-cov' in verify
    assert 'lizard' in verify
    assert '--cov-branch' in verify
    assert 'backend/tests' in verify
    assert 'RUN_INTEGRATION_TESTS' in verify
    assert 'npm --prefix ui ci' in verify
    assert 'npm --prefix ui run test' in verify

    assert 'version = 1' in deepsource
    assert 'test_patterns' in deepsource
    assert 'skip_doc_coverage = ["module", "magic", "init", "class", "nonpublic"]' in deepsource
    assert 'skip_doc_coverage = ["arrow-function-expression"]' in deepsource


def test_e2e_default_access_code_matches_seed_default() -> None:
    seed_content = (REPO_ROOT / 'backend' / 'seed_data.py').read_text(encoding='utf-8')
    e2e_utils_content = (REPO_ROOT / 'ui' / 'e2e' / 'utils.ts').read_text(encoding='utf-8')

    assert 'seed-access-A1' in seed_content
    assert 'seed-access-A1' in e2e_utils_content
