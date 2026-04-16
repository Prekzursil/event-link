"""Tests for the api auth profile behavior."""
from __future__ import annotations

from api_test_support import CONFIRM_SECRET_FIELD, DEFAULT_STUDENT_CODE, SECRET_FIELD


def test_student_registration_and_duplicate_email(helpers):
    """Verifies student registration and duplicate email behavior."""
    client = helpers["client"]
    client.post(
        "/register",
        json={
            "email": "student@test.ro",
            SECRET_FIELD: DEFAULT_STUDENT_CODE,
            CONFIRM_SECRET_FIELD: DEFAULT_STUDENT_CODE,
        },
    )
    duplicate = client.post(
        "/register",
        json={
            "email": "student@test.ro",
            SECRET_FIELD: DEFAULT_STUDENT_CODE,
            CONFIRM_SECRET_FIELD: DEFAULT_STUDENT_CODE,
        },
    )
    assert duplicate.status_code == 400
    assert "deja folosit" in duplicate.json().get("detail", "")


def test_login_failure(helpers):
    """Verifies login failure behavior."""
    client = helpers["client"]
    helpers["register_student"]("login@test.ro")
    bad = client.post("/login", json={"email": "login@test.ro", SECRET_FIELD: "wrong"})
    assert bad.status_code == 401
    assert "incorect" in bad.json().get("detail", "")


def test_theme_preference_default_and_update(helpers):
    """Verifies theme preference default and update behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("theme@test.ro")

    me = client.get("/me", headers=helpers["auth_header"](token))
    assert me.status_code == 200
    assert me.json()["theme_preference"] == "system"

    update = client.put(
        "/api/me/theme",
        json={"theme_preference": "dark"},
        headers=helpers["auth_header"](token),
    )
    assert update.status_code == 200
    assert update.json()["theme_preference"] == "dark"

    me2 = client.get("/me", headers=helpers["auth_header"](token))
    assert me2.status_code == 200
    assert me2.json()["theme_preference"] == "dark"


def test_theme_preference_rejects_invalid_value(helpers):
    """Verifies theme preference rejects invalid value behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("theme-bad@test.ro")

    resp = client.put(
        "/api/me/theme",
        json={"theme_preference": "midnight"},
        headers=helpers["auth_header"](token),
    )
    assert resp.status_code == 422


def test_language_preference_default_and_update(helpers):
    """Verifies language preference default and update behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("lang@test.ro")

    me = client.get("/me", headers=helpers["auth_header"](token))
    assert me.status_code == 200
    assert me.json()["language_preference"] == "system"

    update = client.put(
        "/api/me/language",
        json={"language_preference": "en"},
        headers=helpers["auth_header"](token),
    )
    assert update.status_code == 200
    assert update.json()["language_preference"] == "en"

    me2 = client.get("/me", headers=helpers["auth_header"](token))
    assert me2.status_code == 200
    assert me2.json()["language_preference"] == "en"


def test_language_preference_rejects_invalid_value(helpers):
    """Verifies language preference rejects invalid value behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("lang-bad@test.ro")

    resp = client.put(
        "/api/me/language",
        json={"language_preference": "fr"},
        headers=helpers["auth_header"](token),
    )
    assert resp.status_code == 422


def test_student_profile_updates_academic_fields(helpers):
    """Verifies student profile updates academic fields behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("profile@test.ro")

    updated = client.put(
        "/api/me/profile",
        json={
            "full_name": "Test User",
            "city": "Cluj-Napoca",
            "university": "Babes-Bolyai University of Cluj-Napoca",
            "faculty": "Facultatea de Matematică și Informatică",
            "study_level": "bachelor",
            "study_year": 3,
            "interest_tag_ids": [],
        },
        headers=helpers["auth_header"](token),
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["city"] == "Cluj-Napoca"
    assert body["study_level"] == "bachelor"
    assert body["study_year"] == 3


def test_student_profile_rejects_invalid_study_year(helpers):
    """Verifies student profile rejects invalid study year behavior."""
    client = helpers["client"]
    token = helpers["register_student"]("profile-bad@test.ro")

    bad = client.put(
        "/api/me/profile",
        json={"study_level": "master", "study_year": 3},
        headers=helpers["auth_header"](token),
    )
    assert bad.status_code == 400
