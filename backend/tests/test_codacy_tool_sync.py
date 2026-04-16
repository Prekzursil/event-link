"""Tests for the codacy tool sync behavior."""

import importlib.util
import sys
from pathlib import Path


def _load_module():
    """Loads the module resource."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "quality" / "sync_codacy_repo_tools.py"
    sys.path.insert(0, str(module_path.parent))
    try:
        spec = importlib.util.spec_from_file_location(
            "sync_codacy_repo_tools", module_path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_planned_tool_payload_disables_legacy_tools():
    """Verifies planned tool payload disables legacy tools behavior."""
    module = _load_module()

    payload, notes = module._planned_tool_payload("ESLint", {"isEnabled": True})

    assert payload == {"enabled": False}
    assert notes == [
        "ESLint: configuration file not detected by Codacy; skipping config-file mode request"
    ]


def test_planned_tool_payload_disables_lizard_for_test_noise_control():
    """Verifies planned tool payload disables lizard for test noise control behavior."""
    module = _load_module()

    payload, notes = module._planned_tool_payload("Lizard", {"isEnabled": True})

    assert payload == {"enabled": False}
    assert notes == []


def test_planned_tool_payload_enables_configuration_file_when_available():
    """Verifies planned tool payload enables configuration file when available behavior."""
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        "ESLint9",
        {
            "isEnabled": True,
            "hasConfigurationFile": True,
            "usesConfigurationFile": False,
        },
    )

    assert payload == {"useConfigurationFile": True}
    assert notes == []


def test_planned_tool_payload_enables_legacy_config_when_legacy_tool_is_present() -> (
    None
):
    """Verifies planned tool payload enables legacy config when legacy tool is present
    behavior.
    """
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        "ESLint",
        {
            "isEnabled": True,
            "hasConfigurationFile": True,
            "usesConfigurationFile": False,
        },
    )

    assert payload == {"enabled": False, "useConfigurationFile": True}
    assert notes == []


def test_planned_tool_payload_skips_missing_configuration_files():
    """Verifies planned tool payload skips missing configuration files behavior."""
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        "Stylelint",
        {
            "isEnabled": True,
            "hasConfigurationFile": False,
            "usesConfigurationFile": False,
        },
    )

    assert payload is None
    assert notes == [
        "Stylelint: configuration file not detected by Codacy; skipping config-file mode request"
    ]


def test_planned_tool_payload_enables_prospector_configuration_file_when_available() -> (
    None
):
    """Verifies planned tool payload enables prospector configuration file when available
    behavior.
    """
    module = _load_module()

    payload, notes = module._planned_tool_payload(
        "Prospector",
        {
            "isEnabled": True,
            "hasConfigurationFile": True,
            "usesConfigurationFile": False,
        },
    )

    assert payload == {"useConfigurationFile": True}
    assert notes == []


def test_request_codacy_preserves_query_string():
    """Verifies request codacy preserves query string behavior."""
    module = _load_module()
    request_args = {}

    def fake_request_https_json(
        raw_url,
        *,
        method="GET",
        headers=None,
        body=None,
        timeout=30,
        allowed_hosts=None,
        allowed_host_suffixes=None,
    ):
        """Implements the fake request https json helper."""
        request_args["raw_url"] = raw_url
        request_args["method"] = method
        request_args["headers"] = headers
        request_args["body"] = body
        request_args["timeout"] = timeout
        request_args["allowed_hosts"] = allowed_hosts
        request_args["allowed_host_suffixes"] = allowed_host_suffixes
        return None, {"x-test": "1"}, 204

    module.request_https_json = fake_request_https_json

    status, payload, raw = module._request_codacy(
        method="PATCH",
        path="api/v3/example/patterns?search=PyLint_W1618",
        token="token",
        body={"enabled": False},
    )

    assert status == 204
    assert payload is None
    assert raw == ""
    assert request_args["raw_url"].endswith("/patterns?search=PyLint_W1618")
    assert request_args["method"] == "PATCH"
    assert request_args["allowed_hosts"] == {"api.codacy.com"}


def test_append_markdown_section_uses_none_marker_for_empty_values():
    """Verifies append markdown section uses none marker for empty values behavior."""
    module = _load_module()
    lines = ["# Title"]

    module._append_markdown_section(lines, "Tool Changes", [])

    assert lines == ["# Title", "", "## Tool Changes", module.NONE_MARKDOWN_ITEM]


def test_run_sync_collects_changes_in_dry_run_without_reanalysis():
    """Verifies run sync collects changes in dry run without reanalysis behavior."""
    module = _load_module()
    reanalyze_calls: list[str] = []

    def fake_list_tools(**_kwargs):
        """Implements the fake list tools helper."""
        return [
            {
                "name": "ESLint",
                "uuid": "eslint-uuid",
                "settings": {"isEnabled": True},
            },
            {
                "name": "Pylint",
                "uuid": "pylint-uuid",
                "settings": {"isEnabled": True},
            },
        ]

    module._list_tools = fake_list_tools
    module._configure_tool = lambda **_kwargs: _kwargs
    module._disable_pattern = lambda **_kwargs: _kwargs
    module._reanalyze_commit = lambda **_kwargs: reanalyze_calls.append(
        _kwargs["commit_sha"]
    )

    payload = module._run_sync(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        dry_run=True,
    )

    assert payload["status"] == "pass"
    assert payload["tool_changes"] == [
        {"tool": "ESLint", "payload": {"enabled": False}},
    ]
    assert payload["pattern_changes"] == [
        {"tool": "Pylint", "pattern_id": "PyLint_W1618"}
    ]
    assert payload["failures"] == []
    assert reanalyze_calls == []


def test_sync_tool_settings_retries_config_mode_when_standard_blocks_disable():
    """Verifies sync tool settings retries config mode when standard blocks disable
    behavior.
    """
    module = _load_module()

    tools_by_name = {
        "ESLint": {
            "name": "ESLint",
            "uuid": "eslint-uuid",
            "settings": {
                "isEnabled": True,
                "hasConfigurationFile": True,
                "usesConfigurationFile": False,
            },
        }
    }
    calls = []

    def fake_configure_tool(**kwargs):
        """Implements the fake configure tool helper."""
        calls.append(kwargs["payload"])
        if kwargs["payload"] == {"enabled": False, "useConfigurationFile": True}:
            raise RuntimeError(
                "Codacy tool patch failed for eslint-uuid: HTTP 409 "
                '{"actions": [], "error": "Conflict", "message": "Cannot disable a tool that is enabled by a standard"}'
            )
        assert kwargs["payload"] == {"useConfigurationFile": True}

    module._configure_tool = fake_configure_tool

    tool_changes, notes, failures = module._sync_tool_settings(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        tools_by_name=tools_by_name,
        dry_run=False,
    )

    assert tool_changes == [
        {"tool": "ESLint", "payload": {"enabled": False, "useConfigurationFile": True}}
    ]
    assert failures == []
    assert calls == [
        {"enabled": False, "useConfigurationFile": True},
        {"useConfigurationFile": True},
    ]
    assert notes == [
        "ESLint: managed by Codacy standard; retrying config-file mode without disable request"
    ]


def test_sync_tool_settings_skips_standard_managed_disable_conflicts_without_config_retry():
    """Verifies sync tool settings skips standard managed disable conflicts without config retry
    behavior.
    """
    module = _load_module()

    tools_by_name = {
        "JSHint (deprecated)": {
            "name": "JSHint (deprecated)",
            "uuid": "jshint-uuid",
            "settings": {"isEnabled": True},
        }
    }

    def fake_configure_tool(**_kwargs):
        """Implements the fake configure tool helper."""
        raise RuntimeError(
            "Codacy tool patch failed for jshint-uuid: HTTP 409 "
            '{"actions": [], "error": "Conflict", "message": "Cannot disable a tool that is enabled by a standard"}'
        )

    module._configure_tool = fake_configure_tool

    tool_changes, notes, failures = module._sync_tool_settings(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        tools_by_name=tools_by_name,
        dry_run=False,
    )

    assert tool_changes == [
        {"tool": "JSHint (deprecated)", "payload": {"enabled": False}}
    ]
    assert failures == []
    assert notes == [
        "JSHint (deprecated): managed by Codacy standard; skipping disable request"
    ]


def test_apply_reanalysis_if_clean_treats_forbidden_reanalysis_as_note() -> None:
    """Verifies apply reanalysis if clean treats forbidden reanalysis as note behavior."""
    module = _load_module()

    def fake_reanalyze_commit(**_kwargs):
        """Implements the fake reanalyze commit helper."""
        raise RuntimeError(
            "Codacy reanalyze failed for 0123456789abcdef0123456789abcdef01234567: "
            'HTTP 403 {"actions": [], "error": "Forbidden", "message": "Operation is not authorized"}'
        )

    module._reanalyze_commit = fake_reanalyze_commit

    notes: list[str] = []
    failures: list[str] = []

    module._apply_reanalysis_if_clean(
        provider="gh",
        owner="Prekzursil",
        repo="event-link",
        token="token",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        dry_run=False,
        notes=notes,
        failures=failures,
    )

    assert failures == []
    assert notes == [
        "Codacy reanalysis not authorized for this token; waiting for normal Codacy analysis"
    ]
