from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ESLINTRC = REPO_ROOT / '.eslintrc.cjs'


def test_root_legacy_eslint_config_exists_for_provider_compatibility() -> None:
    assert ROOT_ESLINTRC.is_file()

    content = ROOT_ESLINTRC.read_text(encoding='utf-8')
    assert "parser: '@typescript-eslint/parser'" in content
    assert "sourceType: 'module'" in content
    assert "'import/core-modules': ['k6', 'k6/http']" in content
    assert "'**/eslint.config.*'" in content
