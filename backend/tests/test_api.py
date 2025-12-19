from datetime import datetime, timedelta, timezone

from app import models


def test_student_registration_and_duplicate_email(helpers):
    client = helpers["client"]
    client.post(
        "/register",
        json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
    )
    duplicate = client.post(
        "/register",
        json={"email": "student@test.ro", "password": "password123", "confirm_password": "password123"},
    )
    assert duplicate.status_code == 400
    assert "deja folosit" in duplicate.json().get("detail", "")


def test_login_failure(helpers):
    client = helpers["client"]
    helpers["register_student"]("login@test.ro")
    bad = client.post("/login", json={"email": "login@test.ro", "password": "wrong"})
    assert bad.status_code == 401
    assert "incorect" in bad.json().get("detail", "")


def test_theme_preference_default_and_update(helpers):
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
    client = helpers["client"]
    token = helpers["register_student"]("theme-bad@test.ro")

    resp = client.put(
        "/api/me/theme",
        json={"theme_preference": "midnight"},
        headers=helpers["auth_header"](token),
    )
    assert resp.status_code == 422


def test_language_preference_default_and_update(helpers):
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
    client = helpers["client"]
    token = helpers["register_student"]("lang-bad@test.ro")

    resp = client.put(
        "/api/me/language",
        json={"language_preference": "fr"},
        headers=helpers["auth_header"](token),
    )
    assert resp.status_code == 422


def test_student_profile_updates_academic_fields(helpers):
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
    client = helpers["client"]
    token = helpers["register_student"]("profile-bad@test.ro")

    bad = client.put(
        "/api/me/profile",
        json={"study_level": "master", "study_year": 3},
        headers=helpers["auth_header"](token),
    )
    assert bad.status_code == 400


def test_event_creation_and_capacity_enforced(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    start_time = helpers["future_time"]()
    payload = {
        "title": "Test Event",
        "description": "Descriere",
        "category": "Test",
        "start_time": start_time,
        "end_time": None,
        "city": "București",
        "location": "Online",
        "max_seats": 1,
        "tags": ["test"],
    }
    create_resp = client.post(
        "/api/events",
        json=payload,
        headers=helpers["auth_header"](organizer_token),
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    student1_token = helpers["register_student"]("s1@test.ro")
    reg1 = client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student1_token),
    )
    assert reg1.status_code == 201

    student2_token = helpers["register_student"]("s2@test.ro")
    reg2 = client.post(
        f"/api/events/{event_id}/register",
        headers=helpers["auth_header"](student2_token),
    )
    assert reg2.status_code == 409
    assert "plin" in reg2.json().get("detail", "")


def test_student_cannot_create_event(helpers):
    client = helpers["client"]
    student_token = helpers["register_student"]("stud@test.ro")
    payload = {
        "title": "Invalid",
        "description": "Desc",
        "category": "Test",
        "start_time": helpers["future_time"](),
        "end_time": None,
        "city": "București",
        "location": "Online",
        "max_seats": 10,
        "tags": [],
    }
    resp = client.post("/api/events", json=payload, headers=helpers["auth_header"](student_token))
    assert resp.status_code == 403


def test_edit_forbidden_for_non_owner(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("o1@test.ro", "pass1")
    helpers["make_organizer"]("o2@test.ro", "pass2")
    owner_token = helpers["login"]("o1@test.ro", "pass1")
    other_token = helpers["login"]("o2@test.ro", "pass2")

    create_resp = client.post(
        "/api/events",
        json={
            "title": "Owner Event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    )
    event_id = create_resp.json()["id"]

    update = client.put(
        f"/api/events/{event_id}",
        json={"title": "Hack"},
        headers=helpers["auth_header"](other_token),
    )
    assert update.status_code == 403


def test_delete_soft_deletes_event_and_registrations(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("softdel-org@test.ro", "organizer123")
    organizer_token = helpers["login"]("softdel-org@test.ro", "organizer123")
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
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))

    delete_resp = client.delete(f"/api/events/{event_id}", headers=helpers["auth_header"](organizer_token))
    assert delete_resp.status_code == 204

    db = helpers["db"]
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is not None
    assert event.deleted_by_user_id is not None

    remaining_regs = db.query(models.Registration).count()
    active_regs = db.query(models.Registration).filter(models.Registration.deleted_at.is_(None)).count()
    assert remaining_regs == 1
    assert active_regs == 0

    reg = db.query(models.Registration).first()
    assert reg is not None
    assert reg.deleted_at is not None
    assert reg.deleted_by_user_id is not None

    audit = db.query(models.AuditLog).filter(models.AuditLog.action == "soft_deleted").all()
    assert len(audit) >= 2


def test_restore_event_restores_event_and_registrations(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("restore-owner@test.ro", "organizer123")
    organizer_token = helpers["login"]("restore-owner@test.ro", "organizer123")
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
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))

    delete_resp = client.delete(f"/api/events/{event_id}", headers=helpers["auth_header"](organizer_token))
    assert delete_resp.status_code == 204

    visible = client.get("/api/organizer/events", headers=helpers["auth_header"](organizer_token)).json()
    assert all(e["id"] != event_id for e in visible)
    include_deleted = client.get(
        "/api/organizer/events",
        params={"include_deleted": "true"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    assert any(e["id"] == event_id for e in include_deleted)

    restore_resp = client.post(f"/api/events/{event_id}/restore", headers=helpers["auth_header"](organizer_token))
    assert restore_resp.status_code == 200
    assert restore_resp.json()["status"] == "restored"
    assert restore_resp.json()["restored_registrations"] == 1

    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is None

    reg = db.query(models.Registration).filter(models.Registration.event_id == event_id).first()
    assert reg is not None
    assert reg.deleted_at is None


def test_restore_event_forbidden_for_other_organizer(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "pass1")
    helpers["make_organizer"]("other@test.ro", "pass2")
    owner_token = helpers["login"]("owner@test.ro", "pass1")
    other_token = helpers["login"]("other@test.ro", "pass2")
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

    client.delete(f"/api/events/{event_id}", headers=helpers["auth_header"](owner_token))
    resp = client.post(f"/api/events/{event_id}/restore", headers=helpers["auth_header"](other_token))
    assert resp.status_code == 403


def test_admin_can_restore_registration(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("org@test.ro", "organizer123")
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
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
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))
    client.delete(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))

    student = db.query(models.User).filter(models.User.email == "admin-restore-stud@test.ro").first()
    assert student is not None

    helpers["make_admin"]("admin@test.ro", "adminpass")
    admin_token = helpers["login"]("admin@test.ro", "adminpass")
    restore = client.post(
        f"/api/admin/events/{event_id}/registrations/{student.id}/restore",
        headers=helpers["auth_header"](admin_token),
    )
    assert restore.status_code == 200

    reg = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == student.id)
        .first()
    )
    assert reg is not None
    assert reg.deleted_at is None


def test_admin_can_list_and_update_users(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-users@test.ro", "adminpass")
    admin_token = helpers["login"]("admin-users@test.ro", "adminpass")

    helpers["register_student"]("user-to-update@test.ro")
    user = db.query(models.User).filter(models.User.email == "user-to-update@test.ro").first()
    assert user is not None

    listed = client.get("/api/admin/users", headers=helpers["auth_header"](admin_token))
    assert listed.status_code == 200
    assert any(item["email"] == "user-to-update@test.ro" for item in listed.json()["items"])

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

    relog = client.post("/login", json={"email": "user-to-update@test.ro", "password": "password123"})
    assert relog.status_code == 403


def test_admin_can_edit_and_delete_any_event(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("owner@test.ro", "ownerpass")
    owner_token = helpers["login"]("owner@test.ro", "ownerpass")
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

    helpers["make_admin"]("admin-events@test.ro", "adminpass")
    admin_token = helpers["login"]("admin-events@test.ro", "adminpass")
    admin_user = db.query(models.User).filter(models.User.email == "admin-events@test.ro").first()
    assert admin_user is not None

    updated = client.put(
        f"/api/events/{event_id}",
        json={"title": "Admin edited"},
        headers=helpers["auth_header"](admin_token),
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Admin edited"

    deleted = client.delete(f"/api/events/{event_id}", headers=helpers["auth_header"](admin_token))
    assert deleted.status_code == 204

    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    assert event is not None
    assert event.deleted_at is not None
    assert event.deleted_by_user_id == admin_user.id


def test_admin_can_view_participants_and_update_attendance(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("participants-owner@test.ro", "ownerpass")
    owner_token = helpers["login"]("participants-owner@test.ro", "ownerpass")
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
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))
    student = db.query(models.User).filter(models.User.email == "participants-stud@test.ro").first()
    assert student is not None

    helpers["make_admin"]("participants-admin@test.ro", "adminpass")
    admin_token = helpers["login"]("participants-admin@test.ro", "adminpass")

    listed = client.get(
        f"/api/organizer/events/{event_id}/participants",
        headers=helpers["auth_header"](admin_token),
    )
    assert listed.status_code == 200
    assert any(p["email"] == "participants-stud@test.ro" for p in listed.json()["participants"])

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
    client = helpers["client"]

    helpers["make_admin"]("admin-stats@test.ro", "adminpass")
    admin_token = helpers["login"]("admin-stats@test.ro", "adminpass")

    resp = client.get("/api/admin/stats", headers=helpers["auth_header"](admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "total_users" in body
    assert "total_events" in body
    assert "total_registrations" in body
    assert "registrations_by_day" in body
    assert "top_tags" in body


def test_reregister_after_unregister_restores_registration(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("rereg-org@test.ro", "organizer123")
    organizer_token = helpers["login"]("rereg-org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "ReReg",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 1,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("rereg-stud@test.ro")

    first = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert first.status_code == 201
    unregister = client.delete(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert unregister.status_code == 204

    second = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert second.status_code == 201

    regs = db.query(models.Registration).filter(models.Registration.event_id == event["id"]).all()
    assert len(regs) == 1
    assert regs[0].deleted_at is None


def test_events_list_filters_and_order(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python Workshop", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Party Night", "category": "Social", "start_time": helpers["future_time"](days=3)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**base_payload, "title": "Old Event", "start_time": helpers["future_time"](days=-1)},
        headers=helpers["auth_header"](organizer_token),
    )

    events = client.get("/api/events").json()
    assert [e1["id"], e2["id"]] == [e["id"] for e in events["items"]]
    assert events["total"] == 2

    search = client.get("/api/events", params={"search": "python"}).json()
    assert search["total"] == 1
    assert search["items"][0]["title"] == "Python Workshop"

    category = client.get("/api/events", params={"category": "social"}).json()
    assert category["total"] == 1
    assert category["items"][0]["title"] == "Party Night"

    start_filter = client.get(
        "/api/events", params={"start_date": datetime.now(timezone.utc).date().isoformat()}
    ).json()
    assert len(start_filter["items"]) >= 2

    end_filter = client.get(
        "/api/events", params={"end_date": datetime.now(timezone.utc).date().isoformat()}
    ).json()
    assert end_filter["total"] == 0

    paging = client.get("/api/events", params={"page_size": 1, "page": 1}).json()
    assert paging["page_size"] == 1
    assert len(paging["items"]) == 1
    assert paging["total"] == 2


def test_events_list_filters_by_city(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    c1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Cluj Event", "city": "Cluj-Napoca"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**base_payload, "title": "Buc Event", "city": "București"},
        headers=helpers["auth_header"](organizer_token),
    )

    filtered = client.get("/api/events", params={"city": "cluj"}).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["id"] == c1["id"]


def test_events_list_filters_by_tags_without_duplicates(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python + AI", "tags": ["python", "ai"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Python only", "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.get("/api/events", params=[("tags", "python"), ("tags", "ai")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [e["id"] for e in body["items"]]
    assert ids.count(e1["id"]) == 1
    assert ids.count(e2["id"]) == 1


def test_public_events_filters_by_tags_without_duplicates(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("public-tags-org@test.ro", "organizer123")
    organizer_token = helpers["login"]("public-tags-org@test.ro", "organizer123")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "start_time": helpers["future_time"](days=2),
    }
    e1 = client.post(
        "/api/events",
        json={**base_payload, "title": "Public Python + AI", "tags": ["python", "ai"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={**base_payload, "title": "Public Python only", "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    resp = client.get("/api/public/events", params=[("tags", "python"), ("tags", "ai")])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    ids = [e["id"] for e in body["items"]]
    assert ids.count(e1["id"]) == 1
    assert ids.count(e2["id"]) == 1


def test_public_events_api_exposes_published_only(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("public-org@test.ro", "organizer123")
    organizer_token = helpers["login"]("public-org@test.ro", "organizer123")
    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
        "start_time": helpers["future_time"](days=2),
    }
    published = client.post(
        "/api/events",
        json={**base_payload, "title": "Published"},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    draft = client.post(
        "/api/events",
        json={**base_payload, "title": "Draft", "status": "draft"},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    public_list = client.get("/api/public/events")
    assert public_list.status_code == 200
    items = public_list.json()["items"]
    assert any(e["id"] == published["id"] for e in items)
    assert all(e["id"] != draft["id"] for e in items)

    public_detail = client.get(f"/api/public/events/{published['id']}")
    assert public_detail.status_code == 200
    assert public_detail.json()["id"] == published["id"]

    draft_detail = client.get(f"/api/public/events/{draft['id']}")
    assert draft_detail.status_code == 404


def test_public_events_api_is_rate_limited(helpers):
    client = helpers["client"]
    from app import api as api_module
    from app.config import settings

    helpers["make_organizer"]("public-limit-org@test.ro", "organizer123")
    organizer_token = helpers["login"]("public-limit-org@test.ro", "organizer123")

    old_limit = settings.public_api_rate_limit
    old_window = settings.public_api_rate_window_seconds
    settings.public_api_rate_limit = 2
    settings.public_api_rate_window_seconds = 60
    api_module._RATE_LIMIT_STORE.clear()
    try:
        client.post(
            "/api/events",
            json={
                "title": "Rate limit",
                "description": "Desc",
                "category": "Tech",
                "start_time": helpers["future_time"](days=2),
                "city": "București",
                "location": "Loc",
                "max_seats": 10,
                "tags": [],
            },
            headers=helpers["auth_header"](organizer_token),
        )

        assert client.get("/api/public/events").status_code == 200
        assert client.get("/api/public/events").status_code == 200
        limited = client.get("/api/public/events")
        assert limited.status_code == 429
    finally:
        settings.public_api_rate_limit = old_limit
        settings.public_api_rate_window_seconds = old_window
        api_module._RATE_LIMIT_STORE.clear()


def test_event_validation_rules(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    bad_payload = {
        "title": "aa",
        "description": "Desc",
        "category": "C",
        "start_time": helpers["future_time"](days=1),
        "city": "București",
        "location": "L",
        "max_seats": -1,
        "tags": [],
        "cover_url": "http://example.com/" + "a" * 600,
    }
    resp = client.post("/api/events", json=bad_payload, headers=helpers["auth_header"](organizer_token))
    assert resp.status_code == 422


def test_recommendations_skip_full_and_past(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 1,
        "tags": ["python"],
    }
    full_event = client.post(
        "/api/events",
        json={**tag_payload, "title": "Full Event", "start_time": helpers["future_time"](days=1)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**tag_payload, "title": "Past Event", "start_time": helpers["future_time"](days=-1)},
        headers=helpers["auth_header"](organizer_token),
    )

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{full_event['id']}/register", headers=helpers["auth_header"](student_token))

    rec = client.get("/api/recommendations", headers=helpers["auth_header"](student_token)).json()
    titles = [e["title"] for e in rec]
    assert "Full Event" not in titles
    assert "Past Event" not in titles


def test_recommendations_boosts_user_city(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("org@test.ro", "organizer123")
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    base_payload = {
        "description": "Desc",
        "category": "Tech",
        "location": "Loc",
        "max_seats": 20,
        "tags": [],
    }
    local = client.post(
        "/api/events",
        json={**base_payload, "title": "Local", "city": "Cluj-Napoca", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    remote = client.post(
        "/api/events",
        json={**base_payload, "title": "Remote", "city": "București", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    # Make the remote event "popular"
    for i in range(3):
        tok = helpers["register_student"](f"pop{i}@test.ro")
        client.post(f"/api/events/{remote['id']}/register", headers=helpers["auth_header"](tok))

    student_token = helpers["register_student"]("city@test.ro")
    client.put(
        "/api/me/profile",
        json={"city": "Cluj-Napoca"},
        headers=helpers["auth_header"](student_token),
    )

    rec = client.get(
        "/api/recommendations",
        headers={**helpers["auth_header"](student_token), "Accept-Language": "ro"},
    ).json()
    assert len(rec) >= 2
    assert rec[0]["id"] == local["id"]
    assert "În apropiere" in (rec[0].get("recommendation_reason") or "")


def test_my_events_and_registration_state(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    e1 = client.post(
        "/api/events",
        json={
            "title": "Early",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    e2 = client.post(
        "/api/events",
        json={
            "title": "Late",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=5),
            "city": "București",
            "location": "Loc",
            "max_seats": 5,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{e2['id']}/register", headers=helpers["auth_header"](student_token))
    client.post(f"/api/events/{e1['id']}/register", headers=helpers["auth_header"](student_token))

    my_events = client.get("/api/me/events", headers=helpers["auth_header"](student_token)).json()
    assert [e1["id"], e2["id"]] == [e["id"] for e in my_events]

    detail = client.get(f"/api/events/{e1['id']}", headers=helpers["auth_header"](student_token)).json()
    assert detail["is_registered"]
    assert detail["seats_taken"] == 1


def test_recommended_uses_tags_and_excludes_registered(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    tag_payload = {
        "description": "Desc",
        "category": "Tech",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
    }
    python_event = client.post(
        "/api/events",
        json={**tag_payload, "title": "Python 1", "start_time": helpers["future_time"](days=2), "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    another_python = client.post(
        "/api/events",
        json={**tag_payload, "title": "Python 2", "start_time": helpers["future_time"](days=3), "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{python_event['id']}/register", headers=helpers["auth_header"](student_token))

    rec_resp = client.get("/api/recommendations", headers=helpers["auth_header"](student_token))
    assert rec_resp.status_code == 200
    rec = rec_resp.json()
    rec_ids = [e["id"] for e in rec]
    assert another_python["id"] in rec_ids
    assert python_event["id"] not in rec_ids


def test_recommendations_use_profile_interest_tags_when_no_history(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    payload = {
        "description": "Desc",
        "category": "Music",
        "city": "București",
        "location": "Loc",
        "max_seats": 50,
    }
    rock_event = client.post(
        "/api/events",
        json={**payload, "title": "Rock show", "start_time": helpers["future_time"](days=2), "tags": ["Rock"]},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    client.post(
        "/api/events",
        json={**payload, "title": "Other", "start_time": helpers["future_time"](days=3), "tags": ["python"]},
        headers=helpers["auth_header"](organizer_token),
    )

    student_token = helpers["register_student"]("interest@test.ro")

    tags = client.get("/api/tags").json()["items"]
    rock_tag_id = next(t["id"] for t in tags if t["name"] == "Rock")

    update = client.put(
        "/api/me/profile",
        json={"interest_tag_ids": [rock_tag_id]},
        headers=helpers["auth_header"](student_token),
    )
    assert update.status_code == 200

    rec = client.get(
        "/api/recommendations",
        headers={**helpers["auth_header"](student_token), "Accept-Language": "ro"},
    ).json()
    assert any(e["id"] == rock_event["id"] for e in rec)
    assert "Interesele tale" in (rec[0].get("recommendation_reason") or "")


def test_recommendations_use_ml_cache_when_present(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    payload = {
        "description": "Desc",
        "category": "Cat",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    first_by_time = client.post(
        "/api/events",
        json={**payload, "title": "Earlier", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    second_by_time = client.post(
        "/api/events",
        json={**payload, "title": "Later", "start_time": helpers["future_time"](days=3)},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("mlcache@test.ro")
    student = db.query(models.User).filter(models.User.email == "mlcache@test.ro").first()
    assert student

    db.add_all(
        [
            models.UserRecommendation(
                user_id=student.id,
                event_id=second_by_time["id"],
                score=0.9,
                rank=1,
                model_version="test",
                reason="cache-1",
            ),
            models.UserRecommendation(
                user_id=student.id,
                event_id=first_by_time["id"],
                score=0.8,
                rank=2,
                model_version="test",
                reason="cache-2",
            ),
        ]
    )
    db.commit()

    rec = client.get("/api/recommendations", headers=helpers["auth_header"](student_token)).json()
    assert len(rec) >= 2
    assert rec[0]["id"] == second_by_time["id"]
    assert rec[0].get("recommendation_reason") == "cache-1"


def test_recommendations_ignore_stale_ml_cache(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    payload = {
        "description": "Desc",
        "category": "Cat",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    first_by_time = client.post(
        "/api/events",
        json={**payload, "title": "Earlier", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    second_by_time = client.post(
        "/api/events",
        json={**payload, "title": "Later", "start_time": helpers["future_time"](days=3)},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("mlstale@test.ro")
    student = db.query(models.User).filter(models.User.email == "mlstale@test.ro").first()
    assert student

    old = datetime.now(timezone.utc) - timedelta(days=2)
    db.add(
        models.UserRecommendation(
            user_id=student.id,
            event_id=second_by_time["id"],
            score=0.9,
            rank=1,
            model_version="test",
            reason="cache-1",
            generated_at=old,
        )
    )
    db.commit()

    rec = client.get("/api/recommendations", headers=helpers["auth_header"](student_token)).json()
    assert len(rec) >= 1
    assert rec[0]["id"] == first_by_time["id"]


def test_analytics_interactions_recorded(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    event = client.post(
        "/api/events",
        json={
            "title": "Track",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=2),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("track@test.ro")
    resp = client.post(
        "/api/analytics/interactions",
        json={
            "events": [
                {"interaction_type": "impression", "event_id": event["id"], "meta": {"source": "events_list"}},
                {"interaction_type": "click", "event_id": event["id"], "meta": {"source": "events_list"}},
                {"interaction_type": "search", "meta": {"query": "Track", "city": "București"}},
            ]
        },
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 204

    rows = db.query(models.EventInteraction).order_by(models.EventInteraction.id).all()
    assert len(rows) == 3
    assert rows[0].interaction_type == "impression"
    assert rows[0].event_id == event["id"]
    assert rows[2].interaction_type == "search"
    assert rows[2].event_id is None


def test_events_list_sort_recommended_uses_ml_cache(helpers):
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")

    payload = {
        "description": "Desc",
        "category": "Cat",
        "city": "București",
        "location": "Loc",
        "max_seats": 10,
        "tags": [],
    }
    earlier = client.post(
        "/api/events",
        json={**payload, "title": "Earlier", "start_time": helpers["future_time"](days=2)},
        headers=helpers["auth_header"](organizer_token),
    ).json()
    later = client.post(
        "/api/events",
        json={**payload, "title": "Later", "start_time": helpers["future_time"](days=3)},
        headers=helpers["auth_header"](organizer_token),
    ).json()

    student_token = helpers["register_student"]("mlsort@test.ro")
    student = db.query(models.User).filter(models.User.email == "mlsort@test.ro").first()
    assert student

    now = datetime.now(timezone.utc)
    db.add_all(
        [
            models.UserRecommendation(
                user_id=student.id,
                event_id=later["id"],
                score=0.9,
                rank=1,
                model_version="test",
                reason="cache-first",
                generated_at=now,
            ),
            models.UserRecommendation(
                user_id=student.id,
                event_id=earlier["id"],
                score=0.8,
                rank=2,
                model_version="test",
                reason="cache-second",
                generated_at=now,
            ),
        ]
    )
    db.commit()

    resp = client.get("/api/events?sort=recommended&page_size=10", headers=helpers["auth_header"](student_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["id"] == later["id"]
    assert data["items"][0].get("recommendation_reason") == "cache-first"


def test_duplicate_registration_blocked(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Dup",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    first = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert first.status_code == 201
    second = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert second.status_code == 400
    assert "înscris" in second.json().get("detail", "").lower()


def test_resend_registration_email_requires_registration(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Resend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    not_registered = client.post(
        f"/api/events/{event['id']}/register/resend", headers=helpers["auth_header"](student_token)
    )
    assert not_registered.status_code == 400

    client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    ok = client.post(f"/api/events/{event['id']}/register/resend", headers=helpers["auth_header"](student_token))
    assert ok.status_code == 200


def test_unregister_restores_spot(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    organizer_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Unregister Test",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 1,
            "tags": [],
        },
        headers=helpers["auth_header"](organizer_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    reg = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert reg.status_code == 201

    unregister = client.delete(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))
    assert unregister.status_code == 204

    other_token = helpers["register_student"]("stud2@test.ro")
    reg2 = client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](other_token))
    assert reg2.status_code == 201


def test_mark_attendance_requires_owner(helpers):
    client = helpers["client"]
    helpers["make_organizer"]("owner@test.ro", "ownerpass")
    helpers["make_organizer"]("other@test.ro", "otherpass")
    owner_token = helpers["login"]("owner@test.ro", "ownerpass")
    other_token = helpers["login"]("other@test.ro", "otherpass")
    event = client.post(
        "/api/events",
        json={
            "title": "Attend",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](days=1),
            "city": "București",
            "location": "Loc",
            "max_seats": 3,
            "tags": [],
        },
        headers=helpers["auth_header"](owner_token),
    ).json()
    student_token = helpers["register_student"]("stud@test.ro")
    client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](student_token))

    forbidden = client.put(
        f"/api/organizer/events/{event['id']}/participants/1",
        params={"attended": True},
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden.status_code == 403

    student = helpers["db"].query(models.User).filter(models.User.email == "stud@test.ro").first()
    student_id = student.id  # type: ignore
    ok = client.put(
        f"/api/organizer/events/{event['id']}/participants/{student_id}",
        params={"attended": True},
        headers=helpers["auth_header"](owner_token),
    )
    assert ok.status_code == 204


def test_health_endpoint(helpers):
    client = helpers["client"]
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert body.get("database") == "ok"


def test_event_ics_and_calendar_feed(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    token = helpers["login"]("org@test.ro", "organizer123")
    start_time = helpers["future_time"]()
    payload = {
        "title": "ICS Event",
        "description": "Desc",
        "category": "Cat",
        "start_time": start_time,
        "end_time": None,
        "city": "București",
        "location": "Loc",
        "max_seats": 5,
        "tags": [],
    }
    create_resp = client.post(
        "/api/events",
        json=payload,
        headers=helpers["auth_header"](token),
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    ics_resp = client.get(f"/api/events/{event_id}/ics")
    assert ics_resp.status_code == 200
    assert "BEGIN:VCALENDAR" in ics_resp.text

    student_token = helpers["register_student"]("ics@test.ro")
    client.post(f"/api/events/{event_id}/register", headers=helpers["auth_header"](student_token))
    feed_resp = client.get("/api/me/calendar", headers=helpers["auth_header"](student_token))
    assert feed_resp.status_code == 200
    assert "ICS Event" in feed_resp.text


def test_password_reset_flow(helpers):
    client = helpers["client"]
    helpers["register_student"]("reset@test.ro")
    req = client.post("/password/forgot", json={"email": "reset@test.ro"})
    assert req.status_code == 200
    token_row = helpers["db"].query(models.PasswordResetToken).filter(models.PasswordResetToken.used.is_(False)).first()
    token = token_row.token  # type: ignore

    reset = client.post(
        "/password/reset",
        json={"token": token, "new_password": "newpass123", "confirm_password": "newpass123"},
    )
    assert reset.status_code == 200

    login_ok = client.post("/login", json={"email": "reset@test.ro", "password": "newpass123"})
    assert login_ok.status_code == 200


def test_participants_pagination(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Paginated",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 50,
            "tags": [],
        },
        headers=helpers["auth_header"](org_token),
    ).json()
    for idx in range(5):
        token = helpers["register_student"](f"p{idx}@test.ro")
        client.post(f"/api/events/{event['id']}/register", headers=helpers["auth_header"](token))

    resp = client.get(
        f"/api/organizer/events/{event['id']}/participants",
        params={"page": 2, "page_size": 2, "sort_by": "email", "sort_dir": "desc"},
        headers=helpers["auth_header"](org_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["page_size"] == 2
    assert len(body["participants"]) == 2
    emails = [p["email"] for p in body["participants"]]
    assert emails == sorted(emails, reverse=True)


def test_account_export_and_deletion_student(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Export Event",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": ["export"],
        },
        headers=helpers["auth_header"](org_token),
    ).json()

    student_token = helpers["register_student"]("export@test.ro")
    reg = client.post(
        f"/api/events/{event['id']}/register",
        headers=helpers["auth_header"](student_token),
    )
    assert reg.status_code == 201

    export_resp = client.get("/api/me/export", headers=helpers["auth_header"](student_token))
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert payload["user"]["email"] == "export@test.ro"
    assert payload["user"]["role"] == "student"
    assert len(payload["registrations"]) == 1
    assert payload["registrations"][0]["event"]["id"] == event["id"]

    bad_delete = client.request(
        "DELETE",
        "/api/me",
        json={"password": "wrong"},
        headers=helpers["auth_header"](student_token),
    )
    assert bad_delete.status_code == 400

    ok_delete = client.request(
        "DELETE",
        "/api/me",
        json={"password": "password123"},
        headers=helpers["auth_header"](student_token),
    )
    assert ok_delete.status_code == 200

    me_after = client.get("/me", headers=helpers["auth_header"](student_token))
    assert me_after.status_code == 401


def test_organizer_account_deletion_reassigns_events(helpers):
    client = helpers["client"]
    helpers["make_organizer"]()
    org_token = helpers["login"]("org@test.ro", "organizer123")
    event = client.post(
        "/api/events",
        json={
            "title": "Orphaned",
            "description": "Desc",
            "category": "Cat",
            "start_time": helpers["future_time"](),
            "city": "București",
            "location": "Loc",
            "max_seats": 10,
            "tags": [],
        },
        headers=helpers["auth_header"](org_token),
    ).json()

    delete_resp = client.request(
        "DELETE",
        "/api/me",
        json={"password": "organizer123"},
        headers=helpers["auth_header"](org_token),
    )
    assert delete_resp.status_code == 200

    placeholder = helpers["db"].query(models.User).filter(models.User.email == "deleted-organizer@eventlink.invalid").first()
    assert placeholder is not None
    event_row = helpers["db"].query(models.Event).filter(models.Event.id == event["id"]).first()
    assert event_row is not None
    assert event_row.owner_id == placeholder.id
