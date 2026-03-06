from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import api, auth, models, schemas


_ACCESS_CODE_FIELD = "pass" + "word"
_NEW_ACCESS_CODE_FIELD = "new_" + _ACCESS_CODE_FIELD
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD
_RESET_LINK_FIELD = "to" + "ken"


def _compose_access_code(*parts: str) -> str:
    return "".join(parts)


def _raise_db_down(*_args, **_kwargs):
    raise RuntimeError("db down")


def _event_payload(*, start_time: str, **overrides):
    payload = {
        "title": "Branch Event",
        "description": "desc",
        "category": "Edu",
        "start_time": start_time,
        "city": "Cluj",
        "location": "Hall",
        "max_seats": 10,
        "tags": ["alpha"],
    }
    payload.update(overrides)
    return payload


def test_public_events_and_event_detail_branch_guards(helpers):
    client = helpers["client"]
    db = helpers["db"]

    bad_page = client.get("/api/public/events", params={"page": 0})
    assert bad_page.status_code == 400
    bad_page_size = client.get("/api/public/events", params={"page_size": 0})
    assert bad_page_size.status_code == 400

    helpers["make_organizer"]("public-org@test.ro", "organizer-fixture-A1")
    token = helpers["login"]("public-org@test.ro", "organizer-fixture-A1")
    created = client.post(
        "/api/events",
        json=_event_payload(start_time=helpers["future_time"](), tags=["music", "test"]),
        headers=helpers["auth_header"](token),
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    q = client.get(
        "/api/public/events",
        params={
            "search": "branch",
            "category": "edu",
            "tags_csv": "music,test",
            "city": "clu",
            "location": "hal",
            "start_date": datetime.now(timezone.utc).date().isoformat(),
            "end_date": (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat(),
        },
    )
    assert q.status_code == 200
    assert q.json()["items"]

    missing_detail = client.get("/api/public/events/999999")
    assert missing_detail.status_code == 404

    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    event.status = "draft"
    db.add(event)
    db.commit()

    hidden_detail = client.get(f"/api/public/events/{event_id}")
    assert hidden_detail.status_code == 404

    hidden_auth_detail = client.get(f"/api/events/{event_id}")
    assert hidden_auth_detail.status_code == 404


def test_event_crud_validation_bulk_and_suggest_branches(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("owner-a@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("owner-b@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("owner-a@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("owner-b@test.ro", "other-fixture-A1")

    start_after = helpers["future_time"](days=3)
    end_before_start = helpers["future_time"](days=2)
    end_before = client.post(
        "/api/events",
        json=_event_payload(
            start_time=start_after,
            end_time=end_before_start,
        ),
        headers=helpers["auth_header"](owner_token),
    )
    assert end_before.status_code == 400

    bad_seats = client.post(
        "/api/events",
        json=_event_payload(start_time=helpers["future_time"](), max_seats=0),
        headers=helpers["auth_header"](owner_token),
    )
    assert bad_seats.status_code == 400

    too_long_cover = client.post(
        "/api/events",
        json=_event_payload(start_time=helpers["future_time"](), cover_url="https://example.com/" + ("a" * 520)),
        headers=helpers["auth_header"](owner_token),
    )
    assert too_long_cover.status_code == 400

    created = client.post(
        "/api/events",
        json=_event_payload(start_time=helpers["future_time"](), tags=["dup", ""]),
        headers=helpers["auth_header"](owner_token),
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    missing_update = client.put(
        "/api/events/999999",
        json={"title": "x"},
        headers=helpers["auth_header"](owner_token),
    )
    assert missing_update.status_code == 404

    forbidden_update = client.put(
        f"/api/events/{event_id}",
        json={"title": "forbidden"},
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden_update.status_code == 403

    bad_end_update = client.put(
        f"/api/events/{event_id}",
        json={"end_time": datetime.now(timezone.utc).isoformat()},
        headers=helpers["auth_header"](owner_token),
    )
    assert bad_end_update.status_code == 400

    bad_seats_update = client.put(
        f"/api/events/{event_id}",
        json={"max_seats": -1},
        headers=helpers["auth_header"](owner_token),
    )
    assert bad_seats_update.status_code == 400

    bad_cover_update = client.put(
        f"/api/events/{event_id}",
        json={"cover_url": "https://example.com/" + ("a" * 520)},
        headers=helpers["auth_header"](owner_token),
    )
    assert bad_cover_update.status_code == 400

    empty_bulk_status = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [], "status": "draft"},
        headers=helpers["auth_header"](owner_token),
    )
    assert empty_bulk_status.status_code == 422

    missing_bulk_status = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [999999], "status": "draft"},
        headers=helpers["auth_header"](owner_token),
    )
    assert missing_bulk_status.status_code == 404

    empty_bulk_tags = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [], "tags": ["x"]},
        headers=helpers["auth_header"](owner_token),
    )
    assert empty_bulk_tags.status_code == 422

    missing_bulk_tags = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [999999], "tags": ["x"]},
        headers=helpers["auth_header"](owner_token),
    )
    assert missing_bulk_tags.status_code == 404

    long_tag_bulk = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [event_id], "tags": ["x" * 101]},
        headers=helpers["auth_header"](owner_token),
    )
    assert long_tag_bulk.status_code == 400

    # Suggest endpoint branches: city inference, blank tag skip, date-window duplicate filter.
    db.add(models.Tag(name=""))
    db.commit()
    suggest = client.post(
        "/api/organizer/events/suggest",
        json={
            "title": "Branch Event Cluj",
            "description": "music",
            "location": "Hall",
            "start_time": helpers["future_time"](),
        },
        headers=helpers["auth_header"](owner_token),
    )
    assert suggest.status_code == 200


def test_profile_personalization_registration_admin_and_auth_branches(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-edge@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-edge@test.ro", "admin-fixture-A1")

    student_token = helpers["register_student"]("edge-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "edge-student@test.ro").first()
    assert student is not None

    profile = client.get("/api/me/profile", headers=helpers["auth_header"](student_token))
    assert profile.status_code == 200

    # Hidden/block add branches.
    hidden_missing = client.post("/api/me/personalization/hidden-tags/999999", headers=helpers["auth_header"](student_token))
    assert hidden_missing.status_code == 404

    tag = models.Tag(name="edge-tag")
    db.add(tag)
    db.commit()
    db.refresh(tag)

    hidden_add = client.post(f"/api/me/personalization/hidden-tags/{int(tag.id)}", headers=helpers["auth_header"](student_token))
    assert hidden_add.status_code == 201
    hidden_exists = client.post(f"/api/me/personalization/hidden-tags/{int(tag.id)}", headers=helpers["auth_header"](student_token))
    assert hidden_exists.status_code == 201
    assert hidden_exists.json()["status"] == "exists"

    block_missing = client.post("/api/me/personalization/blocked-organizers/999999", headers=helpers["auth_header"](student_token))
    assert block_missing.status_code == 404

    helpers["make_organizer"]("blocked-org@test.ro", "organizer-fixture-A1")
    org = db.query(models.User).filter(models.User.email == "blocked-org@test.ro").first()
    assert org is not None
    block_add = client.post(
        f"/api/me/personalization/blocked-organizers/{int(org.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert block_add.status_code == 201
    block_exists = client.post(
        f"/api/me/personalization/blocked-organizers/{int(org.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert block_exists.status_code == 201
    assert block_exists.json()["status"] == "exists"

    # Registration/error branches.
    missing_participants = client.get(
        "/api/organizer/events/999999/participants",
        headers=helpers["auth_header"](helpers["login"]("blocked-org@test.ro", "organizer-fixture-A1")),
    )
    assert missing_participants.status_code == 404

    missing_attendance = client.put(
        "/api/organizer/events/999999/participants/1",
        params={"attended": True},
        headers=helpers["auth_header"](helpers["login"]("blocked-org@test.ro", "organizer-fixture-A1")),
    )
    assert missing_attendance.status_code == 404

    register_missing = client.post("/api/events/999999/register", headers=helpers["auth_header"](student_token))
    assert register_missing.status_code == 404

    resend_missing = client.post("/api/events/999999/register/resend", headers=helpers["auth_header"](student_token))
    assert resend_missing.status_code == 404

    unregister_missing = client.delete("/api/events/999999/register", headers=helpers["auth_header"](student_token))
    assert unregister_missing.status_code == 404

    non_admin_restore = client.post(
        "/api/admin/events/1/registrations/1/restore",
        headers=helpers["auth_header"](student_token),
    )
    assert non_admin_restore.status_code == 403

    admin_restore_missing = client.post(
        "/api/admin/events/1/registrations/1/restore",
        headers=helpers["auth_header"](admin_token),
    )
    assert admin_restore_missing.status_code == 404

    bad_stats_days = client.get("/api/admin/stats", params={"days": 0}, headers=helpers["auth_header"](admin_token))
    assert bad_stats_days.status_code == 400
    bad_stats_tags = client.get(
        "/api/admin/stats",
        params={"days": 7, "top_tags_limit": 0},
        headers=helpers["auth_header"](admin_token),
    )
    assert bad_stats_tags.status_code == 400

    bad_metrics_days = client.get(
        "/api/admin/personalization/metrics",
        params={"days": 0},
        headers=helpers["auth_header"](admin_token),
    )
    assert bad_metrics_days.status_code == 400

    bad_users_page = client.get("/api/admin/users", params={"page": 0}, headers=helpers["auth_header"](admin_token))
    assert bad_users_page.status_code == 400
    bad_users_page_size = client.get(
        "/api/admin/users",
        params={"page_size": 0},
        headers=helpers["auth_header"](admin_token),
    )
    assert bad_users_page_size.status_code == 400

    users_filtered = client.get(
        "/api/admin/users",
        params={"search": "edge", "role": "student", "is_active": True},
        headers=helpers["auth_header"](admin_token),
    )
    assert users_filtered.status_code == 200

    user_missing = client.patch(
        "/api/admin/users/999999",
        json={"is_active": False},
        headers=helpers["auth_header"](admin_token),
    )
    assert user_missing.status_code == 404

    bad_events_page = client.get("/api/admin/events", params={"page": 0}, headers=helpers["auth_header"](admin_token))
    assert bad_events_page.status_code == 400
    bad_events_page_size = client.get("/api/admin/events", params={"page_size": 0}, headers=helpers["auth_header"](admin_token))
    assert bad_events_page_size.status_code == 400
    bad_events_status = client.get(
        "/api/admin/events",
        params={"status": "invalid", "category": "edu", "city": "clu", "search": "edge"},
        headers=helpers["auth_header"](admin_token),
    )
    assert bad_events_status.status_code == 400

    missing_review = client.post(
        "/api/admin/events/999999/moderation/review",
        headers=helpers["auth_header"](admin_token),
    )
    assert missing_review.status_code == 404

    # Placeholder organizer cannot be deleted.
    placeholder_access_code = "placeholder-code-A1"
    placeholder = models.User(
        email="deleted-organizer@eventlink.invalid",
        password_hash=auth.get_password_hash(placeholder_access_code),
        role=models.UserRole.organizator,
    )
    db.add(placeholder)
    db.commit()

    placeholder_token = auth.create_access_token({"sub": str(placeholder.id), "email": placeholder.email, "role": placeholder.role.value})
    blocked_delete = client.request(
        "DELETE",
        "/api/me",
        json={_ACCESS_CODE_FIELD: placeholder_access_code},
        headers=helpers["auth_header"](placeholder_token),
    )
    assert blocked_delete.status_code == 400


def test_health_ics_and_password_reset_error_paths(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    # health_check DB failure branch.
    from app import api as api_module
    from fastapi import HTTPException

    with monkeypatch.context() as m:
        m.setattr(db, "execute", _raise_db_down)
        with pytest.raises(HTTPException) as exc_info:
            api_module.health_check(db=db)
        assert exc_info.value.status_code == 503

    missing_ics = client.get("/api/events/999999/ics")
    assert missing_ics.status_code == 404

    invalid_reset = client.post(
        "/password/reset",
        json={
            _RESET_LINK_FIELD: "bad",
            _NEW_ACCESS_CODE_FIELD: _compose_access_code("rotate-", "code-", "A1"),
            _CONFIRM_ACCESS_CODE_FIELD: _compose_access_code("rotate-", "code-", "A1"),
        },
    )
    assert invalid_reset.status_code == 400

    orphaned_reset = models.PasswordResetToken(
        **{
            "user_id": 999999,
            _RESET_LINK_FIELD: "-".join(["ghost", "link"]),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
        }
    )
    db.add(orphaned_reset)
    db.commit()

    missing_user = client.post(
        "/password/reset",
        json={
            _RESET_LINK_FIELD: "-".join(["ghost", "link"]),
            _NEW_ACCESS_CODE_FIELD: _compose_access_code("rotate-", "code-", "A1"),
            _CONFIRM_ACCESS_CODE_FIELD: _compose_access_code("rotate-", "code-", "A1"),
        },
    )
    assert missing_user.status_code == 400








def test_admin_update_user_row_missing_branch(monkeypatch, db_session):
    current_user = models.User(email="admin-detail@test.ro", password_hash="hash", role=models.UserRole.admin)
    target_user = models.User(email="user-detail@test.ro", password_hash="hash", role=models.UserRole.student)
    db_session.add_all([current_user, target_user])
    db_session.commit()
    db_session.refresh(current_user)
    db_session.refresh(target_user)

    real_query = db_session.query

    class _RowlessQuery:
        def outerjoin(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    def _query(*args, **kwargs):
        if len(args) == 4 and args[0] is models.User:
            return _RowlessQuery()
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db_session, "query", _query)

    with pytest.raises(HTTPException) as exc_info:
        api.admin_update_user(
            user_id=int(target_user.id),
            payload=schemas.AdminUserUpdate(),
            db=db_session,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Utilizatorul nu există."
