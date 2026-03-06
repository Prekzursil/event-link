from __future__ import annotations

import pytest

from fixture_helpers import ACCESS_FIELD, build_test_helpers


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, str] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, str]:
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)

    def post(self, _path: str, json: dict[str, str]) -> _FakeResponse:
        return self._responses.pop(0)


class _FakeAuth:
    @staticmethod
    def get_password_hash(value: str) -> str:
        return f"hash:{value}"


class _FakeUserRole:
    organizator = "organizer"
    admin = "admin"


class _FakeUser:
    def __init__(self, **kwargs) -> None:
        self.payload = kwargs


class _FakeModels:
    pass


setattr(_FakeModels, "User", _FakeUser)
setattr(_FakeModels, "UserRole", _FakeUserRole)


class _FakeDb:
    def add(self, _obj) -> None:
        return None

    def commit(self) -> None:
        return None


def test_build_test_helpers_login_and_register_raise_on_non_200() -> None:
    helpers = build_test_helpers(
        client=_FakeClient([_FakeResponse(400, text="bad register"), _FakeResponse(401, text="bad login")]),
        db_session=_FakeDb(),
        auth_module=_FakeAuth(),
        models_module=_FakeModels(),
        include_admin=False,
        include_future_time=False,
    )

    with pytest.raises(RuntimeError, match="register_student failed with status=400"):
        helpers["register_student"]("student@test.ro")

    with pytest.raises(RuntimeError, match="login failed with status=401"):
        helpers["login"]("student@test.ro", "code")


def test_build_test_helpers_return_access_tokens_on_success() -> None:
    helpers = build_test_helpers(
        client=_FakeClient([
            _FakeResponse(200, {ACCESS_FIELD: "register-token"}),
            _FakeResponse(200, {ACCESS_FIELD: "login-token"}),
        ]),
        db_session=_FakeDb(),
        auth_module=_FakeAuth(),
        models_module=_FakeModels(),
        include_admin=False,
        include_future_time=False,
    )

    assert helpers["register_student"]("student@test.ro") == "register-token"
    assert helpers["login"]("student@test.ro", "code") == "login-token"


def test_build_test_helpers_make_accounts_and_decode_binary_error_detail() -> None:
    class _BinaryResponse(_FakeResponse):
        def __init__(self) -> None:
            super().__init__(500, text="")
            self.content = b"binary failure"

    added = []

    class _TrackingDb(_FakeDb):
        def add(self, obj) -> None:
            super().add(obj)
            added.append(obj)

    helpers = build_test_helpers(
        client=_FakeClient([_BinaryResponse()]),
        db_session=_TrackingDb(),
        auth_module=_FakeAuth(),
        models_module=_FakeModels(),
        include_admin=True,
        include_future_time=True,
    )

    helpers["make_organizer"]("org@test.ro", "org-code")
    helpers["make_admin"]("admin@test.ro", "admin-code")
    header = helpers["auth_header"]("token-123")
    assert header["Authorization"] == "Bearer token-123"
    assert added[0].payload["password_hash"] == "hash:org-code"
    assert added[1].payload["password_hash"] == "hash:admin-code"

    with pytest.raises(RuntimeError, match="binary failure"):
        helpers["login"]("broken@test.ro", "code")
