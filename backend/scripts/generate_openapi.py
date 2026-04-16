
# Deferred imports intentionally break cycles or avoid import-time side effects.
# pylint: disable=import-outside-toplevel
#!/usr/bin/env python3
"""Command-line helper: generate openapi."""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    """Implements the main helper."""
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]

    sys.path.insert(0, str(backend_root))

    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SECRET_KEY", "contract-signing-key-material-1234")
    os.environ.setdefault("EMAIL_ENABLED", "false")

    from app.api import app  # noqa: PLC0415

    schema = app.openapi()
    out_path = repo_root / "contracts" / "openapi.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
