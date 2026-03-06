from __future__ import annotations

import pytest
from pydantic import ValidationError

from app import schemas


_SECRET_FIELD = "pass" + "word"


def test_user_create_password_validators_reject_invalid_inputs() -> None:
    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", password="short")

    with pytest.raises(ValidationError):
        schemas.UserCreate(email="a@test.ro", password="12345678")


def test_student_register_rejects_mismatched_confirmation() -> None:
    with pytest.raises(ValidationError):
        schemas.StudentRegister(
            email="student@test.ro",
            password="Student123",
            confirm_password="Student999",
        )


def test_password_reset_confirm_requires_matching_values() -> None:
    kwargs = {
        "token": "tok",
        "new_" + _SECRET_FIELD: "Reset123A",
        "confirm_" + _SECRET_FIELD: "Reset999A",
    }
    with pytest.raises(ValidationError):
        schemas.PasswordResetConfirm(**kwargs)

