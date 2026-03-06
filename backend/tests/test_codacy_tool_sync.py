import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / 'scripts' / 'quality' / 'sync_codacy_repo_tools.py'
    spec = importlib.util.spec_from_file_location('sync_codacy_repo_tools', module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_planned_tool_payload_disables_legacy_tools():
    module = _load_module()

    payload, notes = module._planned_tool_payload('ESLint', {'isEnabled': True})

    assert payload == {'enabled': False}
    assert notes == []


def test_planned_tool_payload_enables_configuration_file_when_available():
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'ESLint9',
        {'isEnabled': True, 'hasConfigurationFile': True, 'usesConfigurationFile': False},
    )

    assert payload == {'useConfigurationFile': True}
    assert notes == []


def test_planned_tool_payload_notes_missing_configuration_files():
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'Stylelint',
        {'isEnabled': True, 'hasConfigurationFile': False, 'usesConfigurationFile': False},
    )

    assert payload is None
    assert notes == ['Stylelint: configuration file not detected by Codacy yet']
