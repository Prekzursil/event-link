from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_GATE = REPO_ROOT / '.github' / 'workflows' / 'quality-zero-gate.yml'
SEMGREP_ZERO = REPO_ROOT / '.github' / 'workflows' / 'semgrep-zero.yml'


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
