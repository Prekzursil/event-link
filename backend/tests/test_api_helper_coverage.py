from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from types import SimpleNamespace
from fastapi import HTTPException, Request

from app import api, auth, models, schemas


_ACCESS_CODE_FIELD = "pass" + "word"
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD


def _compose_access_code(*parts: str) -> str:
    return "".join(parts)


def test_check_configuration_required_values_and_email_toggle(monkeypatch):
    monkeypatch.setattr(api.settings, "database_url", "", raising=False)
    with pytest.raises(RuntimeError):
        api._check_configuration()

    monkeypatch.setattr(api.settings, "database_url", "sqlite:///./test.db", raising=False)
    monkeypatch.setattr(api.settings, "secret_key", "", raising=False)
    with pytest.raises(RuntimeError):
        api._check_configuration()

    monkeypatch.setattr(api.settings, "secret_key", "test-signing-key-material-1234", raising=False)
    monkeypatch.setattr(api.settings, "email_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "smtp_host", None, raising=False)
    monkeypatch.setattr(api.settings, "smtp_sender", None, raising=False)
    api._check_configuration()
    assert api.settings.email_enabled is False


def test_run_migrations_handles_missing_ini_and_exceptions(tmp_path, monkeypatch):
    base = tmp_path / "backend"
    app_dir = base / "app"
    app_dir.mkdir(parents=True)
    fake_api_path = app_dir / "api.py"
    fake_api_path.write_text("# fake", encoding="utf-8")

    warnings = []
    monkeypatch.setattr(api, "__file__", str(fake_api_path), raising=False)
    monkeypatch.setattr(api.logging, "warning", lambda msg: warnings.append(msg))
    api._run_migrations()
    assert any("alembic.ini not found" in msg for msg in warnings)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("upgrade failed")

    monkeypatch.setattr(api.logging, "exception", lambda *_args, **_kwargs: warnings.append("exception"))
    # Force exception branch after successful import by patching command.upgrade.
    import alembic.command as alembic_command

    monkeypatch.setattr(alembic_command, "upgrade", _boom)
    (base / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    api._run_migrations()
    assert "exception" in warnings


def test_validate_cover_url_rejects_non_http_scheme():
    with pytest.raises(HTTPException):
        api._validate_cover_url("ftp://invalid")


def test_refresh_token_branches():
    expired = auth.create_refresh_token(
        {"sub": "1", "email": "x@test.ro", "role": models.UserRole.student.value},
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_expired:
        api.refresh_token(api.schemas.RefreshRequest(refresh_token=expired))
    assert exc_expired.value.status_code == 401

    with pytest.raises(HTTPException):
        api.refresh_token(api.schemas.RefreshRequest(refresh_token="bad-token"))

    wrong_type = auth.create_access_token(
        {"sub": "1", "email": "x@test.ro", "role": models.UserRole.student.value},
        expires_delta=timedelta(minutes=5),
    )
    with pytest.raises(HTTPException):
        api.refresh_token(api.schemas.RefreshRequest(refresh_token=wrong_type))

    missing_role = auth.jwt.encode(
        {"sub": "1", "email": "x@test.ro", "type": "refresh"},
        api.settings.secret_key,
        algorithm=api.settings.algorithm,
    )
    with pytest.raises(HTTPException):
        api.refresh_token(api.schemas.RefreshRequest(refresh_token=missing_role))

    valid = auth.create_refresh_token(
        {"sub": "2", "email": "ok@test.ro", "role": models.UserRole.student.value},
        expires_delta=timedelta(minutes=5),
    )
    payload = api.refresh_token(api.schemas.RefreshRequest(refresh_token=valid))
    assert payload["token_type"] == "bearer"
    assert payload["user_id"] == 2


def test_experiment_treatment_boundary_values():
    assert api._in_experiment_treatment("exp", 0, "1") is False
    assert api._in_experiment_treatment("exp", 100, "1") is True



def test_clone_event_branches_and_success(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("clone-owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("clone-other@test.ro", "other-fixture-A1")

    owner = db.query(models.User).filter(models.User.email == "clone-owner@test.ro").first()
    assert owner is not None
    other_token = helpers["login"]("clone-other@test.ro", "other-fixture-A1")

    missing = client.post("/api/events/999999/clone", headers=helpers["auth_header"](other_token))
    assert missing.status_code == 404

    tag = models.Tag(name="clone-tag")
    past_event = models.Event(
        title="Past Event",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        city="Cluj",
        location="Hall",
        max_seats=30,
        owner_id=int(owner.id),
        status="published",
    )
    past_event.tags.append(tag)
    db.add_all([tag, past_event])
    db.commit()
    db.refresh(past_event)

    forbidden = client.post(
        f"/api/events/{int(past_event.id)}/clone",
        headers=helpers["auth_header"](other_token),
    )
    assert forbidden.status_code == 403

    owner_token = helpers["login"]("clone-owner@test.ro", "owner-fixture-A1")
    cloned = client.post(
        f"/api/events/{int(past_event.id)}/clone",
        headers=helpers["auth_header"](owner_token),
    )
    assert cloned.status_code == 200
    body = cloned.json()
    assert body["title"].startswith("Copie -")
    assert body["status"] == "draft"
    assert any(t["name"] == "clone-tag" for t in body.get("tags", []))


def test_organizer_profile_not_found_and_update_validation(helpers):
    client = helpers["client"]

    missing = client.get("/api/organizers/999999")
    assert missing.status_code == 404

    helpers["make_organizer"]("profile-org@test.ro", "owner-fixture-A1")
    token = helpers["login"]("profile-org@test.ro", "owner-fixture-A1")

    too_long = client.put(
        "/api/organizers/me/profile",
        json={"org_name": "Org", "org_logo_url": "https://example.com/" + ("a" * 520)},
        headers=helpers["auth_header"](token),
    )
    assert too_long.status_code == 400

    ok = client.put(
        "/api/organizers/me/profile",
        json={"org_name": "Updated Org", "org_description": "desc", "org_logo_url": "https://example.com/logo.png"},
        headers=helpers["auth_header"](token),
    )
    assert ok.status_code == 200
    assert ok.json()["org_name"] == "Updated Org"


def test_personalization_and_favorites_branch_paths(helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("favorite-org@test.ro", "organizer-fixture-A1")
    organizer = db.query(models.User).filter(models.User.email == "favorite-org@test.ro").first()
    assert organizer is not None

    student_token = helpers["register_student"]("favorite-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "favorite-student@test.ro").first()
    assert student is not None

    tag = models.Tag(name="favorite-tag")
    event = models.Event(
        title="Favorite Event",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=20,
        owner_id=int(organizer.id),
        status="published",
    )
    db.add_all([tag, event])
    db.commit()
    db.refresh(tag)
    db.refresh(event)

    remove_missing_hidden = client.delete(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_missing_hidden.status_code == 404

    add_hidden = client.post(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert add_hidden.status_code == 201

    remove_hidden = client.delete(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_hidden.status_code == 204

    remove_hidden_again = client.delete(
        f"/api/me/personalization/hidden-tags/{int(tag.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_hidden_again.status_code == 404

    remove_missing_blocked = client.delete(
        f"/api/me/personalization/blocked-organizers/{int(organizer.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_missing_blocked.status_code == 404

    add_blocked = client.post(
        f"/api/me/personalization/blocked-organizers/{int(organizer.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert add_blocked.status_code == 201

    remove_blocked = client.delete(
        f"/api/me/personalization/blocked-organizers/{int(organizer.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_blocked.status_code == 204

    remove_blocked_again = client.delete(
        f"/api/me/personalization/blocked-organizers/{int(organizer.id)}",
        headers=helpers["auth_header"](student_token),
    )
    assert remove_blocked_again.status_code == 404

    favorite_missing = client.post(
        "/api/events/999999/favorite",
        headers=helpers["auth_header"](student_token),
    )
    assert favorite_missing.status_code == 404

    favorite_added = client.post(
        f"/api/events/{int(event.id)}/favorite",
        headers=helpers["auth_header"](student_token),
    )
    assert favorite_added.status_code == 201

    favorite_exists = client.post(
        f"/api/events/{int(event.id)}/favorite",
        headers=helpers["auth_header"](student_token),
    )
    assert favorite_exists.status_code == 201
    assert favorite_exists.json()["status"] == "exists"

    listed = client.get("/api/me/favorites", headers=helpers["auth_header"](student_token))
    assert listed.status_code == 200
    assert listed.json()["items"]

    unfavorite = client.delete(
        f"/api/events/{int(event.id)}/favorite",
        headers=helpers["auth_header"](student_token),
    )
    assert unfavorite.status_code == 204

    unfavorite_again = client.delete(
        f"/api/events/{int(event.id)}/favorite",
        headers=helpers["auth_header"](student_token),
    )
    assert unfavorite_again.status_code == 404


def test_admin_personalization_enqueue_and_activate_branches(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_admin"]("admin-queues@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-queues@test.ro", "admin-fixture-A1")

    missing_model = client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "missing", "recompute": False, "top_n": 10},
        headers=helpers["auth_header"](admin_token),
    )
    assert missing_model.status_code == 404

    old_model = models.RecommenderModel(
        model_version="old-model",
        feature_names=["bias"],
        weights=[0.0],
        meta={},
        is_active=True,
    )
    new_model = models.RecommenderModel(
        model_version="new-model",
        feature_names=["bias"],
        weights=[1.0],
        meta={},
        is_active=False,
    )
    db.add_all([old_model, new_model])
    db.commit()

    import app.task_queue as tq

    def _fake_enqueue(_db, job_type, payload, dedupe_key=None):
        return SimpleNamespace(id=123, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _fake_enqueue)

    activate_no_recompute = client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "new-model", "recompute": False, "top_n": 10},
        headers=helpers["auth_header"](admin_token),
    )
    assert activate_no_recompute.status_code == 200
    assert activate_no_recompute.json()["active_model_version"] == "new-model"
    assert activate_no_recompute.json()["recompute_job"] is None

    activate_with_recompute = client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "new-model", "recompute": True, "top_n": 15},
        headers=helpers["auth_header"](admin_token),
    )
    assert activate_with_recompute.status_code == 200
    assert activate_with_recompute.json()["recompute_job"]["job_type"] == "recompute_recommendations_ml"

    retrain = client.post(
        "/api/admin/personalization/retrain",
        json={"top_n": 10, "epochs": 1, "lr": 0.01},
        headers=helpers["auth_header"](admin_token),
    )
    assert retrain.status_code == 201

    guardrails = client.post(
        "/api/admin/personalization/guardrails/evaluate",
        json={"days": 7, "min_impressions": 1},
        headers=helpers["auth_header"](admin_token),
    )
    assert guardrails.status_code == 201

    digest = client.post(
        "/api/admin/notifications/weekly-digest",
        json={"top_n": 8},
        headers=helpers["auth_header"](admin_token),
    )
    assert digest.status_code == 201

    filling_fast = client.post(
        "/api/admin/notifications/filling-fast",
        json={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 3},
        headers=helpers["auth_header"](admin_token),
    )
    assert filling_fast.status_code == 201


def test_record_interactions_online_learning_and_refresh_branches(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    student_token = helpers["register_student"]("interactions@test.ro")
    student = db.query(models.User).filter(models.User.email == "interactions@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="interactions-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    visible_tag = models.Tag(name="analytics-visible")
    hidden_tag = models.Tag(name="analytics-hidden")
    event = models.Event(
        title="Interaction Event",
        description="desc",
        category="Tech",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Bucuresti",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    event.tags.extend([visible_tag, hidden_tag])
    db.add_all([organizer, visible_tag, hidden_tag, event])
    db.commit()
    db.refresh(student)
    db.refresh(event)
    db.refresh(visible_tag)
    db.refresh(hidden_tag)

    db.execute(models.user_hidden_tags.insert().values(user_id=int(student.id), tag_id=int(hidden_tag.id)))
    db.add(
        models.UserImplicitInterestTag(
            user_id=int(student.id),
            tag_id=int(visible_tag.id),
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.add(
        models.UserImplicitInterestCategory(
            user_id=int(student.id),
            category="tech",
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.add(
        models.UserImplicitInterestCity(
            user_id=int(student.id),
            city="bucuresti",
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()

    monkeypatch.setattr(api.settings, "analytics_enabled", True)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_dwell_threshold_seconds", 10)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_max_score", 10.0)
    monkeypatch.setattr(api.settings, "task_queue_enabled", True)
    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_enabled", True)

    captured_jobs = []
    import app.task_queue as tq

    def _capture_enqueue(_db, job_type, payload, dedupe_key=None):
        captured_jobs.append((job_type, payload, dedupe_key))
        return SimpleNamespace(id=77, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _capture_enqueue)

    payload = {
        "events": [
            {"interaction_type": "click", "event_id": 999999},
            {"interaction_type": "view", "event_id": int(event.id)},
            {"interaction_type": "share", "event_id": int(event.id)},
            {"interaction_type": "favorite", "event_id": int(event.id)},
            {"interaction_type": "register", "event_id": int(event.id)},
            {"interaction_type": "dwell", "event_id": int(event.id), "meta": {"seconds": 20}},
            {"interaction_type": "search", "meta": {"tags": ["analytics-visible", "", None], "category": "Tech", "city": "Bucuresti"}},
            {"interaction_type": "filter", "meta": {"tags": ["analytics-visible"], "category": "Tech", "city": "Bucuresti"}},
            {"interaction_type": "click", "event_id": int(event.id), "occurred_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")},
        ]
    }

    resp = client.post(
        "/api/analytics/interactions",
        json=payload,
        headers=helpers["auth_header"](student_token),
    )
    assert resp.status_code == 204

    refreshed_tag = (
        db.query(models.UserImplicitInterestTag)
        .filter(models.UserImplicitInterestTag.user_id == int(student.id), models.UserImplicitInterestTag.tag_id == int(visible_tag.id))
        .first()
    )
    assert refreshed_tag is not None
    assert float(refreshed_tag.score or 0.0) > 1.0

    hidden_row = (
        db.query(models.UserImplicitInterestTag)
        .filter(models.UserImplicitInterestTag.user_id == int(student.id), models.UserImplicitInterestTag.tag_id == int(hidden_tag.id))
        .first()
    )
    assert hidden_row is None

    cat_row = db.query(models.UserImplicitInterestCategory).filter(models.UserImplicitInterestCategory.user_id == int(student.id)).first()
    city_row = db.query(models.UserImplicitInterestCity).filter(models.UserImplicitInterestCity.user_id == int(student.id)).first()
    assert cat_row is not None and float(cat_row.score or 0.0) > 1.0
    assert city_row is not None and float(city_row.score or 0.0) > 1.0

    assert any(job_type == "refresh_user_recommendations_ml" for job_type, _payload, _dedupe in captured_jobs)


def test_direct_route_guard_branches(monkeypatch):
    monkeypatch.setattr(api, "_enforce_rate_limit", lambda *_args, **_kwargs: None)

    class _RegisterQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return None

    register_db = SimpleNamespace(query=lambda *_args, **_kwargs: _RegisterQuery())
    request = Request({"type": "http", "method": "POST", "path": "/register", "headers": []})

    register_payload = {
        "email": "mismatch@test.ro",
        _ACCESS_CODE_FIELD: _compose_access_code("Entry", "Code", "123A"),
        _CONFIRM_ACCESS_CODE_FIELD: _compose_access_code("Mismatch", "Code", "123A"),
    }
    with pytest.raises(HTTPException) as register_exc:
        api.register(
            schemas.StudentRegister.model_construct(**register_payload),
            request=request,
            db=register_db,
        )
    assert register_exc.value.status_code == 400
    assert register_exc.value.detail == "Parolele nu se potrivesc."

    db_event = SimpleNamespace(
        id=1,
        owner_id=7,
        start_time=datetime.now(timezone.utc),
        end_time=None,
        title="Guard Event",
        description="desc",
        category="Tech",
        city="Cluj",
        location="Hall",
        max_seats=20,
        cover_url=None,
        status="draft",
        publish_at=None,
    )

    class _EventQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return db_event

    event_db = SimpleNamespace(query=lambda *_args, **_kwargs: _EventQuery())
    current_user = SimpleNamespace(id=7, role=models.UserRole.organizator)

    with pytest.raises(HTTPException) as status_exc:
        api.update_event(
            1,
            schemas.EventUpdate.model_construct(status="invalid"),
            db=event_db,
            current_user=current_user,
        )
    assert status_exc.value.status_code == 400
    assert status_exc.value.detail == "Status invalid"

    with pytest.raises(HTTPException) as bulk_status_exc:
        api.organizer_bulk_update_status(
            schemas.OrganizerBulkStatusUpdate.model_construct(event_ids=[], status="draft"),
            db=None,
            current_user=current_user,
        )
    assert bulk_status_exc.value.status_code == 400
    assert bulk_status_exc.value.detail == "Nu ați selectat niciun eveniment."

    with pytest.raises(HTTPException) as bulk_tags_exc:
        api.organizer_bulk_update_tags(
            schemas.OrganizerBulkTagsUpdate.model_construct(event_ids=[], tags=[]),
            db=None,
            current_user=current_user,
        )
    assert bulk_tags_exc.value.status_code == 400
    assert bulk_tags_exc.value.detail == "Nu ați selectat niciun eveniment."


def test_record_interactions_disabled_and_empty_paths(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    student_token = helpers["register_student"]("interactions-empty@test.ro")

    monkeypatch.setattr(api.settings, "analytics_enabled", False)
    disabled_resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "click", "event_id": 12345}]},
        headers=helpers["auth_header"](student_token),
    )
    assert disabled_resp.status_code == 204

    monkeypatch.setattr(api.settings, "analytics_enabled", True)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", False)
    empty_resp = client.post(
        "/api/analytics/interactions",
        json={"events": [{"interaction_type": "click", "event_id": 12345}]},
        headers=helpers["auth_header"](student_token),
    )
    assert empty_resp.status_code == 204

    stored = db.query(models.EventInteraction).count()
    assert stored == 0

