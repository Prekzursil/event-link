from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ESLINTRC = REPO_ROOT / ".eslintrc.cjs"
ROOT_TSLINT = REPO_ROOT / "tslint.json"
PROSPECTOR_CONFIG = REPO_ROOT / ".prospector.yaml"


def test_root_legacy_eslint_config_exists_for_provider_compatibility() -> None:
    assert ROOT_ESLINTRC.is_file()

    content = ROOT_ESLINTRC.read_text(encoding="utf-8")
    assert "parser: '@typescript-eslint/parser'" in content
    assert "sourceType: 'module'" in content
    assert "'import/core-modules': ['k6', 'k6/http']" in content
    assert "'**/eslint.config.*'" in content
    assert "plugins: ['import', 'n', 'es-x', 'flowtype']" in content
    assert "'es-x/no-modules': 'off'" in content
    assert "'es-x/no-block-scoped-variables': 'off'" in content
    assert "'es-x/no-trailing-commas': 'off'" in content
    assert "'flowtype/require-parameter-type': 'off'" in content
    assert "'import/no-unresolved': 'off'" in content
    assert "'n/no-missing-import': 'off'" in content


def test_root_tslint_config_disables_legacy_default_export_rule() -> None:
    assert ROOT_TSLINT.is_file()

    content = ROOT_TSLINT.read_text(encoding="utf-8")
    assert '"no-default-export": false' in content


def test_prospector_config_disables_duplicate_bandit_analysis() -> None:
    assert PROSPECTOR_CONFIG.is_file()

    content = PROSPECTOR_CONFIG.read_text(encoding="utf-8")
    assert "bandit:" in content
    assert "run: false" in content
