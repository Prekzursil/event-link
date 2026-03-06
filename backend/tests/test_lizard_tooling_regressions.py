from __future__ import annotations

from pathlib import Path

import lizard

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_LIMITS = {
    REPO_ROOT / 'scripts' / 'security_helpers.py': {
        'normalize_https_url': {'nloc_max': 50, 'ccn_max': 8},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'check_codacy_zero.py': {
        'main': {'nloc_max': 50},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'check_deepscan_zero.py': {
        'main': {'nloc_max': 50},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'check_required_checks.py': {
        'main': {'nloc_max': 50},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'check_sentry_zero.py': {
        'main': {'nloc_max': 50},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'check_sonar_zero.py': {
        'main': {'nloc_max': 50},
    },
    REPO_ROOT / 'scripts' / 'quality' / 'sync_codacy_repo_tools.py': {
        '_run_sync': {'nloc_max': 50},
    },
}


def _function_map(path: Path):
    analysis = lizard.analyze_file(str(path))
    return {function.name: function for function in analysis.function_list}


def test_selected_python_tooling_functions_stay_under_lizard_limits() -> None:
    offenders: list[str] = []

    for path, expected_functions in TARGET_LIMITS.items():
        functions = _function_map(path)
        for function_name, limits in expected_functions.items():
            function = functions[function_name]
            nloc_max = limits.get('nloc_max')
            ccn_max = limits.get('ccn_max')
            if nloc_max is not None and function.nloc > nloc_max:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{function_name}:nloc={function.nloc}>{nloc_max}")
            if ccn_max is not None and function.cyclomatic_complexity > ccn_max:
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{function_name}:ccn={function.cyclomatic_complexity}>{ccn_max}"
                )

    assert offenders == [], offenders
