"""Tests for the auth config database behavior."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app import auth, config, database, models


class _DummySession:
    """Minimal session double that records whether close() was called."""

    def __init__(self) -> None:
        """Initializes the instance state."""
        self.closed = False

    def close(self) -> None:
        """Mark the session as closed."""
        self.closed = True


def test_verify_password_handles_invalid_hash() -> None:
    """verify_password should fail closed for malformed bcrypt hashes."""
    assert auth.verify_password("plain", "not-a-valid-bcrypt-hash") is False


def test_create_access_and_refresh_token_include_expected_type() -> None:
    """Access and refresh tokens should encode their token type."""
    access = auth.create_access_token(
        {"sub": "1", "email": "u@test.ro", "role": models.UserRole.student.value},
        timedelta(minutes=5),
    )
    refresh = auth.create_refresh_token(
        {"sub": "1", "email": "u@test.ro", "role": models.UserRole.student.value},
        timedelta(minutes=10),
    )

    access_payload = auth.jwt.decode(
        access, config.settings.secret_key, algorithms=[config.settings.algorithm]
    )
    refresh_payload = auth.jwt.decode(
        refresh, config.settings.secret_key, algorithms=[config.settings.algorithm]
    )

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]


def test_get_current_user_requires_token(db_session) -> None:
    """get_current_user should reject missing bearer tokens."""
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=None, db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_inactive_user(db_session) -> None:
    """Inactive users should be denied even when the token is otherwise valid."""
    user = models.User(
        email="inactive-auth@test.ro",
        password_hash=auth.get_password_hash("fixture-marker-A1"),
        role=models.UserRole.student,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = auth.create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 403


def test_get_optional_user_returns_none_for_invalid_token(db_session) -> None:
    """Optional auth should gracefully treat invalid tokens as anonymous."""
    invalid_access_token = "bad" + "-token"
    assert auth.get_optional_user(token=invalid_access_token, db=db_session) is None


def test_role_guards_and_is_admin_paths() -> None:
    """Role guard helpers should accept only the matching user role."""
    student = models.User(
        email="student-role@test.ro",
        password_hash=auth.get_password_hash("student-marker-A1"),
        role=models.UserRole.student,
    )
    organizer = models.User(
        email="org-role@test.ro",
        password_hash=auth.get_password_hash("organizer-marker-A1"),
        role=models.UserRole.organizator,
    )
    admin = models.User(
        email="admin-role@test.ro",
        password_hash=auth.get_password_hash("admin-marker-A1"),
        role=models.UserRole.admin,
    )

    assert auth.require_student(student) is student
    assert auth.require_organizer(organizer) is organizer
    assert auth.require_admin(admin) is admin

    with pytest.raises(HTTPException):
        auth.require_student(organizer)
    with pytest.raises(HTTPException):
        auth.require_organizer(student)
    with pytest.raises(HTTPException):
        auth.require_admin(student)


def test_is_admin_accepts_whitelisted_email(monkeypatch) -> None:
    """Configured admin e-mail allowlists should elevate matching users."""
    user = models.User(
        email="special-admin@test.ro",
        password_hash=auth.get_password_hash("student-marker-A1"),
        role=models.UserRole.student,
    )
    old = list(config.settings.admin_emails)
    monkeypatch.setattr(
        config.settings, "admin_emails", ["special-admin@test.ro", "other@test.ro"]
    )
    try:
        assert auth.is_admin(user) is True
    finally:
        monkeypatch.setattr(config.settings, "admin_emails", old)


def test_settings_parsers_support_csv_json_and_invalid() -> None:
    """Settings parsers should normalize CSV and JSON string inputs."""
    assert config.Settings.parse_allowed_origins("") == config.DEFAULT_ALLOWED_ORIGINS
    assert config.Settings.parse_allowed_origins("https://a.test, https://b.test") == [
        "https://a.test",
        "https://b.test",
    ]
    assert config.Settings.parse_allowed_origins(
        '["https://a.test","https://b.test"]'
    ) == [
        "https://a.test",
        "https://b.test",
    ]
    assert config.Settings.parse_allowed_origins('["https://a.test",""]') == [
        "https://a.test"
    ]
    assert config.Settings.parse_allowed_origins("123") == ["123"]
    assert config.Settings.parse_admin_emails("") == []
    assert config.Settings.parse_admin_emails("A@T.RO,b@t.ro") == ["a@t.ro", "b@t.ro"]
    assert config.Settings.parse_admin_emails('["Admin@T.RO"]') == ["admin@t.ro"]
    assert config.Settings.parse_admin_emails('["Admin@T.RO",""]') == ["admin@t.ro"]
    assert config.Settings.parse_admin_emails("123") == ["123"]

    with pytest.raises(ValueError):
        config.Settings.parse_allowed_origins(123)
    with pytest.raises(ValueError):
        config.Settings.parse_admin_emails(123)


def test_get_db_closes_session(monkeypatch) -> None:
    """get_db should yield one session and close it when exhausted."""
    dummy = _DummySession()

    def _build_dummy_session():
        """Return the session double used by this test."""
        return dummy

    monkeypatch.setattr(database, "SessionLocal", _build_dummy_session)

    gen = database.get_db()
    sentinel = object()
    yielded = next(gen, sentinel)
    assert yielded is dummy

    assert next(gen, sentinel) is sentinel

    assert dummy.closed is True


def test_get_current_user_rejects_missing_role_in_token(db_session) -> None:
    """Tokens missing the role claim should be rejected."""
    user = models.User(
        email="missing-role@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = auth.create_access_token({"sub": str(user.id), "email": user.email})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_expired_token(db_session) -> None:
    """Expired access tokens should surface the translated auth error."""
    token = auth.create_access_token(
        {
            "sub": "99",
            "email": "expired@test.ro",
            "role": models.UserRole.student.value,
        },
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401
    assert "Token expirat" in exc_info.value.detail
