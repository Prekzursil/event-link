import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / 'scripts' / 'quality' / 'sync_codacy_repo_tools.py'
    sys.path.insert(0, str(module_path.parent))
    try:
        spec = importlib.util.spec_from_file_location('sync_codacy_repo_tools', module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_planned_tool_payload_disables_legacy_tools():
    module = _load_module()

    payload, notes = module._planned_tool_payload('ESLint', {'isEnabled': True})

    assert payload == {'enabled': False}
    assert notes == ['ESLint: configuration file not detected by Codacy yet']


def test_planned_tool_payload_enables_configuration_file_when_available():
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'ESLint9',
        {'isEnabled': True, 'hasConfigurationFile': True, 'usesConfigurationFile': False},
    )

    assert payload == {'useConfigurationFile': True}
    assert notes == []


def test_planned_tool_payload_enables_legacy_config_when_legacy_tool_is_present() -> None:
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'ESLint',
        {'isEnabled': True, 'hasConfigurationFile': True, 'usesConfigurationFile': False},
    )

    assert payload == {'enabled': False, 'useConfigurationFile': True}
    assert notes == []


def test_planned_tool_payload_notes_missing_configuration_files():
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'Stylelint',
        {'isEnabled': True, 'hasConfigurationFile': False, 'usesConfigurationFile': False},
    )

    assert payload is None
    assert notes == ['Stylelint: configuration file not detected by Codacy yet']


def test_planned_tool_payload_enables_prospector_configuration_file_when_available() -> None:
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        'Prospector',
        {'isEnabled': True, 'hasConfigurationFile': True, 'usesConfigurationFile': False},
    )

    assert payload == {'useConfigurationFile': True}
    assert notes == []


def test_request_codacy_preserves_query_string():
    module = _load_module()
    request_args = {}

    def fake_request_https_json(raw_url, *, method='GET', headers=None, body=None, timeout=30, allowed_hosts=None, allowed_host_suffixes=None):
        request_args['raw_url'] = raw_url
        request_args['method'] = method
        request_args['headers'] = headers
        request_args['body'] = body
        request_args['timeout'] = timeout
        request_args['allowed_hosts'] = allowed_hosts
        request_args['allowed_host_suffixes'] = allowed_host_suffixes
        return None, {'x-test': '1'}, 204

    module.request_https_json = fake_request_https_json

    status, payload, raw = module._request_codacy(
        method='PATCH',
        path='api/v3/example/patterns?search=PyLint_W1618',
        token='token',
        body={'enabled': False},
    )

    assert status == 204
    assert payload is None
    assert raw == ''
    assert request_args['raw_url'].endswith('/patterns?search=PyLint_W1618')
    assert request_args['method'] == 'PATCH'
    assert request_args['allowed_hosts'] == {'api.codacy.com'}


def test_append_markdown_section_uses_none_marker_for_empty_values():
    module = _load_module()
    lines = ['# Title']

    module._append_markdown_section(lines, 'Tool Changes', [])

    assert lines == ['# Title', '', '## Tool Changes', module.NONE_MARKDOWN_ITEM]


def test_run_sync_collects_changes_in_dry_run_without_reanalysis():
    module = _load_module()
    reanalyze_calls: list[str] = []

    def fake_list_tools(**_kwargs):
        return [
            {
                'name': 'ESLint',
                'uuid': 'eslint-uuid',
                'settings': {'isEnabled': True},
            },
            {
                'name': 'Pylint',
                'uuid': 'pylint-uuid',
                'settings': {'isEnabled': True},
            },
        ]

    module._list_tools = fake_list_tools
    module._configure_tool = lambda **_kwargs: (_kwargs)
    module._disable_pattern = lambda **_kwargs: (_kwargs)
    module._reanalyze_commit = lambda **_kwargs: reanalyze_calls.append(_kwargs['commit_sha'])

    payload = module._run_sync(
        provider='gh',
        owner='Prekzursil',
        repo='event-link',
        token='token',
        commit_sha='0123456789abcdef0123456789abcdef01234567',
        dry_run=True,
    )

    assert payload['status'] == 'pass'
    assert payload['tool_changes'] == [{'tool': 'ESLint', 'payload': {'enabled': False}}]
    assert payload['pattern_changes'] == [{'tool': 'Pylint', 'pattern_id': 'PyLint_W1618'}]
    assert payload['failures'] == []
    assert reanalyze_calls == []
