from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import HTTPException

from app import auth, config, database, models


class _DummySession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_verify_password_handles_invalid_hash() -> None:
    assert auth.verify_password("plain", "not-a-valid-bcrypt-hash") is False


def test_create_access_and_refresh_token_include_expected_type() -> None:
    access = auth.create_access_token({"sub": "1", "email": "u@test.ro", "role": models.UserRole.student.value}, timedelta(minutes=5))
    refresh = auth.create_refresh_token({"sub": "1", "email": "u@test.ro", "role": models.UserRole.student.value}, timedelta(minutes=10))

    access_payload = auth.jwt.decode(access, config.settings.secret_key, algorithms=[config.settings.algorithm])
    refresh_payload = auth.jwt.decode(refresh, config.settings.secret_key, algorithms=[config.settings.algorithm])

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert refresh_payload["exp"] > access_payload["exp"]


def test_get_current_user_requires_token(db_session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=None, db=db_session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_inactive_user(db_session) -> None:
    user = models.User(
        email="inactive-auth@test.ro",
        password_hash=auth.get_password_hash("fixture-token-123"),
        role=models.UserRole.student,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = auth.create_access_token({"sub": str(user.id), "email": user.email, "role": user.role.value})
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 403


def test_get_optional_user_returns_none_for_invalid_token(db_session) -> None:
    assert auth.get_optional_user(token="bad-token", db=db_session) is None


def test_role_guards_and_is_admin_paths() -> None:
    student = models.User(email="student-role@test.ro", password_hash=auth.get_password_hash("student-token"), role=models.UserRole.student)
    organizer = models.User(email="org-role@test.ro", password_hash=auth.get_password_hash("organizer-token"), role=models.UserRole.organizator)
    admin = models.User(email="admin-role@test.ro", password_hash=auth.get_password_hash("admin-token"), role=models.UserRole.admin)

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
    user = models.User(email="special-admin@test.ro", password_hash=auth.get_password_hash("student-token"), role=models.UserRole.student)
    old = list(config.settings.admin_emails)
    monkeypatch.setattr(config.settings, "admin_emails", ["special-admin@test.ro", "other@test.ro"])
    try:
        assert auth.is_admin(user) is True
    finally:
        monkeypatch.setattr(config.settings, "admin_emails", old)


def test_settings_parsers_support_csv_json_and_invalid() -> None:
    assert config.Settings.parse_allowed_origins("") == config.DEFAULT_ALLOWED_ORIGINS
    assert config.Settings.parse_allowed_origins("http://a.test, http://b.test") == ["http://a.test", "http://b.test"]
    assert config.Settings.parse_allowed_origins('["http://a.test","http://b.test"]') == ["http://a.test", "http://b.test"]
    assert config.Settings.parse_admin_emails("") == []
    assert config.Settings.parse_admin_emails("A@T.RO,b@t.ro") == ["a@t.ro", "b@t.ro"]
    assert config.Settings.parse_admin_emails('["Admin@T.RO"]') == ["admin@t.ro"]

    with pytest.raises(ValueError):
        config.Settings.parse_allowed_origins(123)
    with pytest.raises(ValueError):
        config.Settings.parse_admin_emails(123)


def test_get_db_closes_session(monkeypatch) -> None:
    dummy = _DummySession()
    monkeypatch.setattr(database, "SessionLocal", lambda: dummy)

    gen = database.get_db()
    yielded = next(gen)
    assert yielded is dummy

    with pytest.raises(StopIteration):
        next(gen)

    assert dummy.closed is True

def test_get_current_user_rejects_missing_role_in_token(db_session) -> None:
    user = models.User(
        email="missing-role@test.ro",
        password_hash=auth.get_password_hash("Student123A"),
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
    token = auth.create_access_token(
        {"sub": "99", "email": "expired@test.ro", "role": models.UserRole.student.value},
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(token=token, db=db_session)
    assert exc_info.value.status_code == 401
    assert "Token expirat" in exc_info.value.detail
