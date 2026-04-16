"""Tests for the api admin restore behavior."""

from __future__ import annotations

from app import models
from api_test_support import (
    DEFAULT_ADMIN_CODE,
    DEFAULT_ORG_CODE,
    DEFAULT_STUDENT_CODE,
    SECRET_FIELD,
)


def test_delete_soft_deletes_event_and_registrations(helpers):
    """Verifies delete soft deletes event and registrations behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("softdel-org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("softdel-org@test.ro", DEFAULT_ORG_CODE)
    create_resp = client.post(
        "/api/events",
        json={
            "title": "Delete Me",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    )
    event_id = create_resp.json()["id"]

    student_token = helpers["register_student"]("softdel-stud@test.ro")
    client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )

    delete_resp = client.delete(
        f"/api/events/{event_id}", headers=helpers["auth_header"](organizer_token)
    )
    assert delete_resp.status_code == 204

    db = helpers["db"]
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is not None
    assert event.deleted_by_user_id is not None

    remaining_regs = db.query(models.Registration).count()
    active_regs = (
        db.query(models.Registration)
        .filter(models.Registration.deleted_at.is_(None))
        .count()
    )
    assert remaining_regs == 1
    assert active_regs == 0

    reg = db.query(models.Registration).first()
    assert reg is not None
    assert reg.deleted_at is not None
    assert reg.deleted_by_user_id is not None

    audit = (
        db.query(models.AuditLog).filter(models.AuditLog.action == "soft_deleted").all()
    )
    assert len(audit) >= 2


def test_restore_event_restores_event_and_registrations(helpers):
    """Verifies restore event restores event and registrations behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("restore-owner@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("restore-owner@test.ro", DEFAULT_ORG_CODE)
    create_resp = client.post(
        "/api/events",
        json={
            "title": "Restore Me",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    )
    event_id = create_resp.json()["id"]

    student_token = helpers["register_student"]("restore-stud@test.ro")
    client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )

    delete_resp = client.delete(
        f"/api/events/{event_id}", headers=helpers["auth_header"](organizer_token)
    )
    assert delete_resp.status_code == 204

    visible = client.get(
        "/api/organizer/events", headers=helpers["auth_header"](organizer_token)
    ).json()
    assert all(e["id"] != event_id for e in visible)
    include_deleted = client.get(
        "/api/organizer/events",
        params={"include_deleted": "true"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    assert any(e["id"] == event_id for e in include_deleted)

    restore_resp = client.post(
        f"/api/events/{event_id}/restore",
        headers=helpers["auth_header"](organizer_token),
    )
    assert restore_resp.status_code == 200
    assert restore_resp.json()["status"] == "restored"
    assert restore_resp.json()["restored_registrations"] == 1

    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is None

    reg = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id)
        .first()
    )
    assert reg is not None
    assert reg.deleted_at is None


def test_restore_event_forbidden_for_other_organizer(helpers):
    """Verifies restore event forbidden for other organizer behavior."""
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("other@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("other@test.ro", "other-fixture-A1")
    event_id = client.post(
        "/api/events",
        json={
            "title": "Restore perms",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()["id"]

    client.delete(
        f"/api/events/{event_id}", headers=helpers["auth_header"](owner_token)
    )
    resp = client.post(
        f"/api/events/{event_id}/restore", headers=helpers["auth_header"](other_token)
    )
    assert resp.status_code == 403


def test_admin_can_restore_registration(helpers):
    """Verifies admin can restore registration behavior."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("org@test.ro", DEFAULT_ORG_CODE)
    organizer_token = helpers["login"]("org@test.ro", DEFAULT_ORG_CODE)
    event_id = client.post(
        "/api/events",
        json={
            "title": "Admin restore reg",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()["id"]

    student_token = helpers["register_student"]("admin-restore-stud@test.ro")
    client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )
    client.delete(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )

    student = (
        db.query(models.User)
        .filter(models.User.email == "admin-restore-stud@test.ro")
        .first()
    )
    assert student is not None

    helpers["make_admin"]("admin@test.ro", DEFAULT_ADMIN_CODE)
    admin_token = helpers["login"]("admin@test.ro", DEFAULT_ADMIN_CODE)
    restore = client.post(
        f"/api/admin/events/{event_id}/registrations/{student.id}/restore",
        headers=helpers["auth_header"](admin_token),
    )
    assert restore.status_code == 200

    reg = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == student.id,
        )
        .first()
    )
    assert reg is not None
    assert reg.deleted_at is None


def test_admin_can_list_and_update_users(helpers):
    """Verifies admin can list and update users behavior."""
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-users@test.ro", DEFAULT_ADMIN_CODE)
    admin_token = helpers["login"]("admin-users@test.ro", DEFAULT_ADMIN_CODE)

    helpers["register_student"]("user-to-update@test.ro")
    user = (
        db.query(models.User)
        .filter(models.User.email == "user-to-update@test.ro")
        .first()
    )
    assert user is not None

    listed = client.get("/api/admin/users", headers=helpers["auth_header"](admin_token))
    assert listed.status_code == 200
    assert any(
        item["email"] == "user-to-update@test.ro" for item in listed.json()["items"]
    )

    promote = client.patch(
        f"/api/admin/users/{user.id}",
        json={"role": "organizator"},
        headers=helpers["auth_header"](admin_token),
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "organizator"

    deactivate = client.patch(
        f"/api/admin/users/{user.id}",
        json={"is_active": False},
        headers=helpers["auth_header"](admin_token),
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    relog = client.post(
        "/login",
        json={"email": "user-to-update@test.ro", SECRET_FIELD: DEFAULT_STUDENT_CODE},
    )
    assert relog.status_code == 403


def test_admin_can_edit_and_delete_any_event(helpers):
    """Verifies admin can edit and delete any event behavior."""
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    owner_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")
    event_id = client.post(
        "/api/events",
        json={
            "title": "Owned event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()["id"]

    helpers["make_admin"]("admin-events@test.ro", DEFAULT_ADMIN_CODE)
    admin_token = helpers["login"]("admin-events@test.ro", DEFAULT_ADMIN_CODE)
    admin_user = (
        db.query(models.User)
        .filter(models.User.email == "admin-events@test.ro")
        .first()
    )
    assert admin_user is not None

    updated = client.put(
        f"/api/events/{event_id}",
        json={"title": "Admin edited"},
        headers=helpers["auth_header"](admin_token),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Admin edited"

    deleted = client.delete(
        f"/api/events/{event_id}", headers=helpers["auth_header"](admin_token)
    )
    assert deleted.status_code == 204

    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is not None
    assert event.deleted_by_user_id == admin_user.id


def test_admin_can_view_participants_and_update_attendance(helpers):
    """Verifies admin can view participants and update attendance behavior."""
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("participants-owner@test.ro", "owner-fixture-A1")
    owner_token = helpers["login"]("participants-owner@test.ro", "owner-fixture-A1")
    event_id = client.post(
        "/api/events",
        json={
            "title": "Participants",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 2,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()["id"]

    student_token = helpers["register_student"]("participants-stud@test.ro")
    client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student_token),
    )
    student = (
        db.query(models.User)
        .filter(models.User.email == "participants-stud@test.ro")
        .first()
    )
    assert student is not None

    helpers["make_admin"]("participants-admin@test.ro", DEFAULT_ADMIN_CODE)
    admin_token = helpers["login"]("participants-admin@test.ro", DEFAULT_ADMIN_CODE)

    listed = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](admin_token),
    )
    assert listed.status_code == 200
    assert any(
        p["email"] == "participants-stud@test.ro" for p in listed.json()["participants"]
    )

    updated = client.put(
        f"/api/organizer/events/{event_id}/participants/{student.id}",
        params={"attended": True},
        headers=helpers["auth_header"](admin_token),
    )
    assert updated.status_code == 204

    reg = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == student.id,
            models.Registration.deleted_at.is_(None),
        )
        .first()
    )
    assert reg is not None
    assert reg.attended is True


def test_admin_stats_endpoint_smoke(helpers):
    """Verifies admin stats endpoint smoke behavior."""
    client = helpers["client"]

    helpers["make_admin"]("admin-stats@test.ro", DEFAULT_ADMIN_CODE)
    admin_token = helpers["login"]("admin-stats@test.ro", DEFAULT_ADMIN_CODE)

    resp = client.get("/api/admin/stats", headers=helpers["auth_header"](admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "total_users" in body
    assert "total_events" in body
    assert "total_registrations" in body
    assert "registrations_by_day" in body
    assert "top_tags" in body
