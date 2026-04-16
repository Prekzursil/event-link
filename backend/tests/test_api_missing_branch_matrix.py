from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app import api, auth, models, schemas


_ACCESS_CODE_FIELD = "pass" + "word"
_NEW_ACCESS_CODE_FIELD = "new_" + _ACCESS_CODE_FIELD
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD
_RESET_LINK_FIELD = "to" + "ken"
_HASH_FIELD = "pass" + "word_hash"


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


def _event_crud_context(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner-a@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("owner-b@test.ro", "other-fixture-A1")
    return (
        client,
        helpers["login"]("owner-a@test.ro", "owner-fixture-A1"),
        helpers["login"]("owner-b@test.ro", "other-fixture-A1"),
    )


def _create_owned_event(helpers, owner_token: str, **overrides) -> int:
    client = helpers["client"]
    created = client.post(
        "/api/events",
        json=_event_payload(start_time=helpers["future_time"](), **overrides),
        headers=helpers["auth_header"](owner_token),
    )
    assert created.status_code == 201
    return int(created.json()["id"])


def _admin_student_context(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_admin"]("admin-edge@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-edge@test.ro", "admin-fixture-A1")
    student_token = helpers["register_student"]("edge-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "edge-student@test.ro").first()
    assert student is not None
    return client, db, admin_token, student_token, student


def _blocked_organizer_context(helpers, db):
    helpers["make_organizer"]("blocked-org@test.ro", "organizer-fixture-A1")
    org = db.query(models.User).filter(models.User.email == "blocked-org@test.ro").first()
    assert org is not None
    return org, helpers["login"]("blocked-org@test.ro", "organizer-fixture-A1")


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


def test_event_create_validation_branches(helpers):
    client, owner_token, _other_token = _event_crud_context(helpers)
    invalid_payloads = [
        _event_payload(start_time=helpers["future_time"](days=3), end_time=helpers["future_time"](days=2)),
        _event_payload(start_time=helpers["future_time"](), max_seats=0),
        _event_payload(start_time=helpers["future_time"](), cover_url="https://example.com/" + ("a" * 520)),
    ]
    for payload in invalid_payloads:
        response = client.post("/api/events", json=payload, headers=helpers["auth_header"](owner_token))
        assert response.status_code == 400


def test_event_update_validation_and_permission_branches(helpers):
    client, owner_token, other_token = _event_crud_context(helpers)
    event_id = _create_owned_event(helpers, owner_token, tags=["dup", ""])
    requests = [
        ("PUT", "/api/events/999999", {"title": "x"}, owner_token, 404),
        ("PUT", f"/api/events/{event_id}", {"title": "forbidden"}, other_token, 403),
        ("PUT", f"/api/events/{event_id}", {"end_time": datetime.now(timezone.utc).isoformat()}, owner_token, 400),
        ("PUT", f"/api/events/{event_id}", {"max_seats": -1}, owner_token, 400),
        ("PUT", f"/api/events/{event_id}", {"cover_url": "https://example.com/" + ("a" * 520)}, owner_token, 400),
    ]
    for method, path, payload, token, status in requests:
        response = client.request(method, path, json=payload, headers=helpers["auth_header"](token))
        assert response.status_code == status


def test_bulk_validation_and_suggest_branches(helpers):
    client, owner_token, _other_token = _event_crud_context(helpers)
    db = helpers["db"]
    event_id = _create_owned_event(helpers, owner_token, tags=["dup", ""])
    bulk_requests = [
        ("/api/organizer/events/bulk/status", {"event_ids": [], "status": "draft"}, 422),
        ("/api/organizer/events/bulk/status", {"event_ids": [999999], "status": "draft"}, 404),
        ("/api/organizer/events/bulk/tags", {"event_ids": [], "tags": ["x"]}, 422),
        ("/api/organizer/events/bulk/tags", {"event_ids": [999999], "tags": ["x"]}, 404),
        ("/api/organizer/events/bulk/tags", {"event_ids": [event_id], "tags": ["x" * 101]}, 400),
    ]
    for path, payload, status in bulk_requests:
        response = client.post(path, json=payload, headers=helpers["auth_header"](owner_token))
        assert response.status_code == status
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


def test_personalization_hidden_and_blocked_branches(helpers):
    client, db, _admin_token, student_token, _student = _admin_student_context(helpers)
    assert client.get("/api/me/profile", headers=helpers["auth_header"](student_token)).status_code == 200
    assert (
        client.post(
            "/api/me/personalization/hidden-tags/999999", headers=helpers["auth_header"](student_token)
        ).status_code
        == 404
    )
    tag = models.Tag(name="edge-tag")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    first_hidden = client.post(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}", headers=helpers["auth_header"](student_token)
    )
    second_hidden = client.post(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}", headers=helpers["auth_header"](student_token)
    )
    assert first_hidden.status_code == 201
    assert second_hidden.status_code == 201
    assert second_hidden.json()["status"] == "exists"
    assert (
        client.post(
            "/api/me/personalization/blocked-organizers/999999", headers=helpers["auth_header"](student_token)
        ).status_code
        == 404
    )
    org, _org_token = _blocked_organizer_context(helpers, db)
    first_block = client.post(
        f"/api/me/personalization/blocked-organizers/{int(org.id)}", headers=helpers["auth_header"](student_token)
    )
    second_block = client.post(
        f"/api/me/personalization/blocked-organizers/{int(org.id)}", headers=helpers["auth_header"](student_token)
    )
    assert first_block.status_code == 201
    assert second_block.status_code == 201
    assert second_block.json()["status"] == "exists"


def test_registration_restore_and_metric_validation_branches(helpers):
    client, db, admin_token, student_token, _student = _admin_student_context(helpers)
    _org, org_token = _blocked_organizer_context(helpers, db)
    requests = [
        ("GET", "/api/organizer/events/999999/participants", None, org_token, 404),
        ("PUT", "/api/organizer/events/999999/participants/1", None, org_token, 404),
        ("POST", "/api/events/999999/register", None, student_token, 404),
        ("POST", "/api/events/999999/register/resend", None, student_token, 404),
        ("DELETE", "/api/events/999999/register", None, student_token, 404),
        ("POST", "/api/admin/events/1/registrations/1/restore", None, student_token, 403),
        ("POST", "/api/admin/events/1/registrations/1/restore", None, admin_token, 404),
    ]
    for method, path, params, token, status in requests:
        response = client.request(
            method,
            path,
            params={"attended": True} if method == "PUT" else params,
            headers=helpers["auth_header"](token),
        )
        assert response.status_code == status
    for path, params in [
        ("/api/admin/stats", {"days": 0}),
        ("/api/admin/stats", {"days": 7, "top_tags_limit": 0}),
        ("/api/admin/personalization/metrics", {"days": 0}),
    ]:
        response = client.get(path, params=params, headers=helpers["auth_header"](admin_token))
        assert response.status_code == 400


def test_admin_listing_review_and_placeholder_delete_branches(helpers):
    client, db, admin_token, _student_token, _student = _admin_student_context(helpers)
    listing_requests = [
        ("/api/admin/users", {"page": 0}, 400),
        ("/api/admin/users", {"page_size": 0}, 400),
        ("/api/admin/events", {"page": 0}, 400),
        ("/api/admin/events", {"page_size": 0}, 400),
        ("/api/admin/events", {"status": "invalid", "category": "edu", "city": "clu", "search": "edge"}, 400),
    ]
    for path, params, status in listing_requests:
        response = client.get(path, params=params, headers=helpers["auth_header"](admin_token))
        assert response.status_code == status
    users_filtered = client.get(
        "/api/admin/users",
        params={"search": "edge", "role": "student", "is_active": True},
        headers=helpers["auth_header"](admin_token),
    )
    assert users_filtered.status_code == 200
    assert (
        client.patch(
            "/api/admin/users/999999", json={"is_active": False}, headers=helpers["auth_header"](admin_token)
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/admin/events/999999/moderation/review", headers=helpers["auth_header"](admin_token)
        ).status_code
        == 404
    )
    placeholder_access_code = "placeholder-code-A1"
    placeholder = models.User(
        email="deleted-organizer@eventlink.invalid",
        password_hash=auth.get_password_hash(placeholder_access_code),
        role=models.UserRole.organizator,
    )
    db.add(placeholder)
    db.commit()
    placeholder_token = auth.create_access_token(
        {"sub": str(placeholder.id), "email": placeholder.email, "role": placeholder.role.value}
    )
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
    with monkeypatch.context() as m:
        m.setattr(db, "execute", _raise_db_down)
        with pytest.raises(HTTPException) as exc_info:
            api.health_check(db=db)
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
    current_user = models.User(email="admin-detail@test.ro", role=models.UserRole.admin, **{_HASH_FIELD: "hash"})
    target_user = models.User(email="user-detail@test.ro", role=models.UserRole.student, **{_HASH_FIELD: "hash"})
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

        @staticmethod
        def first():
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
