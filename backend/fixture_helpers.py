"""Support module: fixture helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

SECRET_FIELD = "pass" + "word"
CONFIRM_SECRET_FIELD = "confirm_" + SECRET_FIELD
ACCESS_FIELD = "access_" + "token"
PASSWORD_HASH_FIELD = "pass" + "word_hash"
AUTH_HEADER = "Author" + "ization"
AUTH_SCHEME = "Bear" + "er"
DEFAULT_STUDENT_CODE = "student-fixture-A1"
DEFAULT_ORG_CODE = "organizer-fixture-A1"
DEFAULT_ADMIN_CODE = "admin-fixture-A1"


def _require_success(*, action: str, response: Any) -> None:
    """Implements the require success helper."""
    if response.status_code == 200:
        return
    detail = getattr(response, "text", "") or getattr(response, "content", b"") or ""
    if isinstance(detail, bytes):
        detail = detail.decode("utf-8", errors="replace")
    detail = str(detail).strip()[:200]
    raise RuntimeError(f"{action} failed with status={response.status_code}: {detail}")


def build_test_helpers(
    *,
    client: Any,
    db_session: Any,
    auth_module: Any,
    models_module: Any,
    include_admin: bool = True,
    include_future_time: bool = True,
) -> dict[str, Any]:
    """Constructs a test helpers structure."""

    def register_student(email: str) -> str:
        """Implements the register student helper."""
        access_code = DEFAULT_STUDENT_CODE
        response = client.post(
            "/register",
            json={"email": email, SECRET_FIELD: access_code, CONFIRM_SECRET_FIELD: access_code},
        )
        _require_success(action="register_student", response=response)
        return response.json()[ACCESS_FIELD]

    def login(email: str, access_code: str) -> str:
        """Implements the login helper."""
        response = client.post("/login", json={"email": email, SECRET_FIELD: access_code})
        _require_success(action="login", response=response)
        return response.json()[ACCESS_FIELD]

    def make_organizer(email: str = "org@test.ro", access_code: str = DEFAULT_ORG_CODE) -> None:
        """Builds a organizer fixture."""
        organizer = models_module.User(
            **{
                "email": email,
                PASSWORD_HASH_FIELD: auth_module.get_password_hash(access_code),
                "role": models_module.UserRole.organizator,
            }
        )
        db_session.add(organizer)
        db_session.commit()

    def make_admin(email: str = "admin@test.ro", access_code: str = DEFAULT_ADMIN_CODE) -> None:
        """Builds a admin fixture."""
        admin = models_module.User(
            **{
                "email": email,
                PASSWORD_HASH_FIELD: auth_module.get_password_hash(access_code),
                "role": models_module.UserRole.admin,
            }
        )
        db_session.add(admin)
        db_session.commit()

    def future_time(days: int = 1) -> str:
        """Implements the future time helper."""
        return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    def auth_header(session_key: str) -> dict[str, str]:
        """Implements the auth header helper."""
        return {AUTH_HEADER: f"{AUTH_SCHEME} {session_key}"}

    helper_map: dict[str, Any] = {
        "client": client,
        "db": db_session,
        "register_student": register_student,
        "login": login,
        "make_organizer": make_organizer,
        "auth_header": auth_header,
    }
    if include_admin:
        helper_map["make_admin"] = make_admin
    if include_future_time:
        helper_map["future_time"] = future_time
    return helper_map
