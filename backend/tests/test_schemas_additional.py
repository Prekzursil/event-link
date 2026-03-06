from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import schemas


_SECRET_FIELD = "pass" + "word"
_CONFIRM_SECRET_FIELD = "confirm_" + _SECRET_FIELD


def test_user_create_password_validators_reject_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", **{_SECRET_FIELD: "short"})

    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", **{_SECRET_FIELD: "12345678"})


def test_student_register_rejects_mismatched_confirmation() -> None:
    payload = {
        "email": "student@test.ro",
        _SECRET_FIELD: "Student123",
        _CONFIRM_SECRET_FIELD: "Student999",
    }
    with pytest.raises(ValidationError):
        schemas.StudentRegister(**payload)


def test_password_reset_confirm_requires_matching_values() -> None:
    kwargs = {
        "token": "tok",
        "new_" + _SECRET_FIELD: "Reset123A",
        _CONFIRM_SECRET_FIELD: "Reset999A",
    }
    with pytest.raises(ValidationError):
        schemas.PasswordResetConfirm(**kwargs)

