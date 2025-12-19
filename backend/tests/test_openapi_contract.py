import json
from pathlib import Path

from app.api import app


def test_openapi_contract_snapshot_is_up_to_date():
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "contracts" / "openapi.json"

    if not contract_path.exists():
        raise AssertionError(
            "Missing OpenAPI contract snapshot at contracts/openapi.json. "
            "Generate it with: backend/.venv/bin/python backend/scripts/generate_openapi.py"
        )

    expected = json.loads(contract_path.read_text(encoding="utf-8"))
    actual = app.openapi()

    assert expected == actual, (
        "OpenAPI contract snapshot is out of date. "
        "Update it with: backend/.venv/bin/python backend/scripts/generate_openapi.py"
    )
