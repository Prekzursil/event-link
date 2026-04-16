"""Support module: security import."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_security_helpers(caller_file: str) -> ModuleType:
    """Loads the security helpers resource."""
    script_dir = Path(caller_file).resolve().parent
    helper_root = (
        script_dir
        if (script_dir / "security_helpers.py").exists()
        else script_dir.parent
    )
    helper_path = helper_root / "security_helpers.py"
    if not helper_path.exists():
        raise RuntimeError(f"Unable to locate security_helpers.py from {caller_file}")

    spec = importlib.util.spec_from_file_location(
        "event_link_security_helpers", helper_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load security helpers module from {helper_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
