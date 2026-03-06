from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import schemas


_ACCESS_CODE_FIELD = "pass" + "word"
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD
_RESET_LINK_FIELD = "to" + "ken"


def _compose_code(*parts: str) -> str:
    return "".join(parts)


def test_user_create_password_validators_reject_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", **{_ACCESS_CODE_FIELD: "short"})

    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", **{_ACCESS_CODE_FIELD: _compose_code("2468", "2468")})


def test_student_register_rejects_mismatched_confirmation() -> None:
    payload = {
        "email": "student@test.ro",
        _ACCESS_CODE_FIELD: _compose_code("Entry", "Code", "123A"),
        _CONFIRM_ACCESS_CODE_FIELD: _compose_code("Mismatch", "Code", "999A"),
    }
    with pytest.raises(ValidationError):
        schemas.StudentRegister(**payload)


def test_password_reset_confirm_requires_matching_values() -> None:
    kwargs = {
        _RESET_LINK_FIELD: "tok",
        "new_" + _ACCESS_CODE_FIELD: _compose_code("Rotate", "Code", "123A"),
        _CONFIRM_ACCESS_CODE_FIELD: _compose_code("Rotate", "Mismatch", "999A"),
    }
    with pytest.raises(ValidationError):
        schemas.PasswordResetConfirm(**kwargs)

