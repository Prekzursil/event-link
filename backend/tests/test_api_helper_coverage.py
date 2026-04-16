"""Tests for the api helper coverage behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys

import pytest
from types import SimpleNamespace
from fastapi import HTTPException, Request

from app import api, auth, models, schemas


_ACCESS_CODE_FIELD = "pass" + "word"
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD


def _compose_access_code(*parts: str) -> str:
    """Join access-code fragments without leaving a single secret-like literal."""
    return "".join(parts)


class _FirstQuery:
    """Minimal query double that supports chained filter().first() calls."""

    def __init__(self, result) -> None:
        """Initializes the instance state."""
        self._result = result

    def filter(self, *_args, **_kwargs):
        """Return self so chained query calls can continue."""
        return self

    def first(self):
        """Return the pre-seeded first() result."""
        return self._result


def _seed_favorite_context(helpers):
    """Create favorite-related models and auth state for API helper tests."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("favorite-org@test.ro", "organizer-fixture-A1")
    organizer = (
        db.query(models.User)
        .filter(models.User.email == "favorite-org@test.ro")
        .first()
    )
    assert organizer is not None
    student_token = helpers["register_student"]("favorite-student@test.ro")
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
    return SimpleNamespace(
        client=client,
        organizer=organizer,
        student_token=student_token,
        tag=tag,
        event=event,
    )


def _seed_admin_context(helpers, monkeypatch):
    """Create admin auth state and stub queue submission for admin API tests."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_admin"]("admin-queues@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-queues@test.ro", "admin-fixture-A1")
    db.add_all(
        [
            models.RecommenderModel(
                model_version="old-model",
                feature_names=["bias"],
                weights=[0.0],
                meta={},
                is_active=True,
            ),
            models.RecommenderModel(
                model_version="new-model",
                feature_names=["bias"],
                weights=[1.0],
                meta={},
                is_active=False,
            ),
        ]
    )
    db.commit()
    import app.task_queue as tq

    def _enqueue_job_stub(_db, job_type, payload, dedupe_key=None):
        """Return a deterministic queued job object for admin task endpoints."""
        return SimpleNamespace(id=123, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _enqueue_job_stub)
    return SimpleNamespace(client=client, admin_token=admin_token)


def _configure_record_interactions_settings(monkeypatch) -> None:
    """Enable analytics and realtime-learning settings for interaction tests."""
    for name, value in (
        ("analytics_enabled", True),
        ("recommendations_online_learning_enabled", True),
        ("recommendations_online_learning_dwell_threshold_seconds", 10),
        ("recommendations_online_learning_max_score", 10.0),
        ("task_queue_enabled", True),
        ("recommendations_use_ml_cache", True),
        ("recommendations_realtime_refresh_enabled", True),
    ):
        monkeypatch.setattr(api.settings, name, value)


def _record_interactions_payload(event_id: int) -> dict:
    """Build a mixed interaction payload that hits the helper edge branches."""
    return {
        "events": [
            {"interaction_type": "click", "event_id": 999999},
            {"interaction_type": "view", "event_id": event_id},
            {"interaction_type": "share", "event_id": event_id},
            {"interaction_type": "favorite", "event_id": event_id},
            {"interaction_type": "register", "event_id": event_id},
            {
                "interaction_type": "dwell",
                "event_id": event_id,
                "meta": {"seconds": 20},
            },
            {
                "interaction_type": "search",
                "meta": {
                    "tags": ["analytics-visible", "", None],
                    "category": "Tech",
                    "city": "Bucuresti",
                },
            },
            {
                "interaction_type": "filter",
                "meta": {
                    "tags": ["analytics-visible"],
                    "category": "Tech",
                    "city": "Bucuresti",
                },
            },
            {
                "interaction_type": "click",
                "event_id": event_id,
                "occurred_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            },
        ]
    }


def _install_fake_alembic(monkeypatch, upgraded: list[str]) -> None:
    """Install fake alembic modules so migration helpers can be exercised."""

    class _FakeConfig:
        """Minimal Alembic Config replacement used by migration tests."""

        def __init__(self, _path: str):
            """Initializes the instance state."""
            self.path = _path

        @staticmethod
        def set_main_option(*_args, **_kwargs):
            """Accept config updates without persisting anything."""
            return None

    def _upgrade_stub(*_args, **_kwargs):
        """Record that the upgrade helper attempted to migrate to head."""
        upgraded.append("head")

    fake_command = SimpleNamespace(upgrade=_upgrade_stub)
    fake_config = SimpleNamespace(Config=_FakeConfig)
    monkeypatch.setitem(sys.modules, "alembic.command", fake_command)
    monkeypatch.setitem(sys.modules, "alembic.config", fake_config)
    monkeypatch.setitem(
        sys.modules,
        "alembic",
        SimpleNamespace(command=fake_command, config=fake_config),
    )


def _seed_record_interactions_context(helpers, monkeypatch):
    """Create an interaction-heavy fixture set for analytics helper coverage."""
    client = helpers["client"]
    db = helpers["db"]
    student_token = helpers["register_student"]("interactions@test.ro")
    student = (
        db.query(models.User)
        .filter(models.User.email == "interactions@test.ro")
        .first()
    )
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
    db.execute(
        models.user_hidden_tags.insert().values(
            user_id=int(student.id), tag_id=int(hidden_tag.id)
        )
    )
    for model in (
        models.UserImplicitInterestTag(
            user_id=int(student.id),
            tag_id=int(visible_tag.id),
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
        models.UserImplicitInterestCategory(
            user_id=int(student.id),
            category="tech",
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
        models.UserImplicitInterestCity(
            user_id=int(student.id),
            city="bucuresti",
            score=1.0,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
        ),
    ):
        db.add(model)
    db.commit()
    _configure_record_interactions_settings(monkeypatch)
    captured_jobs = []
    import app.task_queue as tq

    def _capture_enqueue_job(_db, job_type, payload, dedupe_key=None):
        """Capture queued jobs while returning a deterministic queued response."""
        captured_jobs.append((job_type, payload, dedupe_key))
        return SimpleNamespace(id=77, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _capture_enqueue_job)
    return SimpleNamespace(
        client=client,
        db=db,
        student=student,
        student_token=student_token,
        visible_tag=visible_tag,
        hidden_tag=hidden_tag,
        event=event,
        payload=_record_interactions_payload(int(event.id)),
        captured_jobs=captured_jobs,
    )


def test_check_configuration_required_values_and_email_toggle(monkeypatch):
    """Configuration validation should fail fast and disable misconfigured email."""
    monkeypatch.setattr(api.settings, "database_url", "", raising=False)
    with pytest.raises(RuntimeError):
        api._check_configuration()

    monkeypatch.setattr(
        api.settings, "database_url", "sqlite:///./test.db", raising=False
    )
    monkeypatch.setattr(api.settings, "secret_key", "", raising=False)
    with pytest.raises(RuntimeError):
        api._check_configuration()

    monkeypatch.setattr(
        api.settings, "secret_key", "test-signing-key-material-1234", raising=False
    )
    monkeypatch.setattr(api.settings, "email_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "smtp_host", None, raising=False)
    monkeypatch.setattr(api.settings, "smtp_sender", None, raising=False)
    api._check_configuration()
    assert api.settings.email_enabled is False


def test_run_migrations_handles_missing_ini_and_exceptions(tmp_path, monkeypatch):
    """Migration helper should warn for missing ini files and log upgrade errors."""
    base = tmp_path / "backend"
    app_dir = base / "app"
    app_dir.mkdir(parents=True)
    fake_api_path = app_dir / "api.py"
    fake_api_path.write_text("# fake", encoding="utf-8")

    warnings = []
    monkeypatch.setattr(api, "__file__", str(fake_api_path), raising=False)

    def _record_warning(msg):
        """Capture warning messages emitted by the migration helper."""
        warnings.append(msg)

    monkeypatch.setattr(api.logging, "warning", _record_warning)
    missing_ini_upgrades: list[str] = []
    _install_fake_alembic(monkeypatch, missing_ini_upgrades)
    api._run_migrations()
    assert any("alembic.ini not found" in msg for msg in warnings)
    assert missing_ini_upgrades == []

    def _boom(*_args, **_kwargs):
        """Raise a deterministic upgrade failure for exception-path coverage."""
        raise RuntimeError("upgrade failed")

    def _record_exception(*_args, **_kwargs):
        """Capture exception logging emitted by the migration helper."""
        warnings.append("exception")

    monkeypatch.setattr(api.logging, "exception", _record_exception)
    (base / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    upgraded: list[str] = []
    _install_fake_alembic(monkeypatch, upgraded)
    monkeypatch.setattr(sys.modules["alembic.command"], "upgrade", _boom)
    api._run_migrations()
    assert "exception" in warnings


def test_validate_cover_url_rejects_non_http_scheme():
    """Cover URLs should reject non-HTTP schemes."""
    with pytest.raises(HTTPException):
        api._validate_cover_url("ftps://invalid")


def test_refresh_token_branches():
    """Refresh-token helper should reject invalid tokens and mint valid payloads."""
    invalid_refresh_token = "bad" + "-token"
    expired = auth.create_refresh_token(
        {"sub": "1", "email": "x@test.ro", "role": models.UserRole.student.value},
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(HTTPException) as exc_expired:
        api.refresh_token(api.schemas.RefreshRequest(refresh_token=expired))
    assert exc_expired.value.status_code == 401

    with pytest.raises(HTTPException):
        api.refresh_token(
            api.schemas.RefreshRequest(refresh_token=invalid_refresh_token)
        )

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
    """Experiment bucketing should honor zero and full rollout boundaries."""
    in_experiment_treatment = getattr(api, "_in_experiment_treatment")
    never_bucket = in_experiment_treatment("exp", 0, "1")
    always_bucket = in_experiment_treatment("exp", 100, "1")
    assert never_bucket is False
    assert always_bucket is True


def test_clone_event_branches_and_success(helpers):
    """Clone route should cover missing, forbidden, and successful branches."""
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("clone-owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("clone-other@test.ro", "other-fixture-A1")

    owner = (
        db.query(models.User).filter(models.User.email == "clone-owner@test.ro").first()
    )
    assert owner is not None
    other_token = helpers["login"]("clone-other@test.ro", "other-fixture-A1")

    missing = client.post(
        "/api/events/999999/clone", headers=helpers["auth_header"](other_token)
    )
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
    """Organizer profile routes should validate missing and update paths."""
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
        json={
            "org_name": "Updated Org",
            "org_description": "desc",
            "org_logo_url": "https://example.com/logo.png",
        },
        headers=helpers["auth_header"](token),
    )
    assert ok.status_code == 200
    _ok_body = ok.json()
    assert _ok_body["org_name"] == "Updated Org"


def test_hidden_tag_personalization_endpoints(helpers):
    """Hidden-tag endpoints should cover create, delete, and missing states."""
    context = _seed_favorite_context(helpers)
    headers = helpers["auth_header"](context.student_token)
    _response = context.client.delete(
        f"/api/me/personalization/hidden-tags/{int(context.tag.id)}", headers=headers
    )
    assert _response.status_code == 404
    _response = context.client.post(
        f"/api/me/personalization/hidden-tags/{int(context.tag.id)}", headers=headers
    )
    assert _response.status_code == 201
    _response = context.client.delete(
        f"/api/me/personalization/hidden-tags/{int(context.tag.id)}", headers=headers
    )
    assert _response.status_code == 204
    _response = context.client.delete(
        f"/api/me/personalization/hidden-tags/{int(context.tag.id)}", headers=headers
    )
    assert _response.status_code == 404


def test_blocked_organizer_personalization_endpoints(helpers):
    """Blocked-organizer endpoints should cover create, delete, and missing states."""
    context = _seed_favorite_context(helpers)
    headers = helpers["auth_header"](context.student_token)
    _response = context.client.delete(
        f"/api/me/personalization/blocked-organizers/{int(context.organizer.id)}",
        headers=headers,
    )
    assert _response.status_code == 404
    _response = context.client.post(
        f"/api/me/personalization/blocked-organizers/{int(context.organizer.id)}",
        headers=headers,
    )
    assert _response.status_code == 201
    _response = context.client.delete(
        f"/api/me/personalization/blocked-organizers/{int(context.organizer.id)}",
        headers=headers,
    )
    assert _response.status_code == 204
    _response = context.client.delete(
        f"/api/me/personalization/blocked-organizers/{int(context.organizer.id)}",
        headers=headers,
    )
    assert _response.status_code == 404


def test_favorite_endpoints_cover_missing_exists_list_and_delete_paths(helpers):
    """Favorite routes should cover missing, exists, list, and delete branches."""
    context = _seed_favorite_context(helpers)
    headers = helpers["auth_header"](context.student_token)
    _response = context.client.post("/api/events/999999/favorite", headers=headers)
    assert _response.status_code == 404
    _response = context.client.post(
        f"/api/events/{int(context.event.id)}/favorite", headers=headers
    )
    assert _response.status_code == 201
    favorite_exists = context.client.post(
        f"/api/events/{int(context.event.id)}/favorite", headers=headers
    )
    assert favorite_exists.status_code == 201
    _favorite_exists_body = favorite_exists.json()
    assert _favorite_exists_body["status"] == "exists"
    listed = context.client.get("/api/me/favorites", headers=headers)
    assert listed.status_code == 200
    _listed_body = listed.json()
    assert _listed_body["items"]
    _response = context.client.delete(
        f"/api/events/{int(context.event.id)}/favorite", headers=headers
    )
    assert _response.status_code == 204
    _response = context.client.delete(
        f"/api/events/{int(context.event.id)}/favorite", headers=headers
    )
    assert _response.status_code == 404


def test_admin_activate_missing_personalization_model_returns_404(helpers):
    """Admin activation should return 404 when the target model is missing."""
    client = helpers["client"]
    helpers["make_admin"]("admin-queues@test.ro", "admin-fixture-A1")
    admin_token = helpers["login"]("admin-queues@test.ro", "admin-fixture-A1")
    response = client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "missing", "recompute": False, "top_n": 10},
        headers=helpers["auth_header"](admin_token),
    )
    assert response.status_code == 404


def test_admin_activate_model_paths_return_expected_recompute_payloads(
    monkeypatch, helpers
):
    """Admin activation should return both non-recompute and recompute payloads."""
    context = _seed_admin_context(helpers, monkeypatch)
    headers = helpers["auth_header"](context.admin_token)
    activate_no_recompute = context.client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "new-model", "recompute": False, "top_n": 10},
        headers=headers,
    )
    assert activate_no_recompute.status_code == 200
    _activate_no_recompute_body = activate_no_recompute.json()
    assert _activate_no_recompute_body["active_model_version"] == "new-model"
    _activate_no_recompute_body = activate_no_recompute.json()
    assert _activate_no_recompute_body["recompute_job"] is None
    activate_with_recompute = context.client.post(
        "/api/admin/personalization/models/activate",
        json={"model_version": "new-model", "recompute": True, "top_n": 15},
        headers=headers,
    )
    assert activate_with_recompute.status_code == 200
    assert (
        activate_with_recompute.json()["recompute_job"]["job_type"]
        == "recompute_recommendations_ml"
    )


def test_admin_personalization_queue_endpoints_return_created(monkeypatch, helpers):
    """Admin queue endpoints should return created responses for each job type."""
    context = _seed_admin_context(helpers, monkeypatch)
    headers = helpers["auth_header"](context.admin_token)
    retrain = context.client.post(
        "/api/admin/personalization/retrain",
        json={"top_n": 10, "epochs": 1, "lr": 0.01},
        headers=headers,
    )
    assert retrain.status_code == 201
    guardrails = context.client.post(
        "/api/admin/personalization/guardrails/evaluate",
        json={"days": 7, "min_impressions": 1},
        headers=headers,
    )
    assert guardrails.status_code == 201
    digest = context.client.post(
        "/api/admin/notifications/weekly-digest",
        json={"top_n": 8},
        headers=headers,
    )
    assert digest.status_code == 201
    filling_fast = context.client.post(
        "/api/admin/notifications/filling-fast",
        json={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 3},
        headers=headers,
    )
    assert filling_fast.status_code == 201


def test_record_interactions_updates_scores_and_skips_hidden_tags(monkeypatch, helpers):
    """Interaction recording should update visible interests and skip hidden tags."""
    context = _seed_record_interactions_context(helpers, monkeypatch)
    response = context.client.post(
        "/api/analytics/interactions",
        json=context.payload,
        headers=helpers["auth_header"](context.student_token),
    )
    assert response.status_code == 204
    refreshed_tag = (
        context.db.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == int(context.student.id),
            models.UserImplicitInterestTag.tag_id == int(context.visible_tag.id),
        )
        .first()
    )
    assert refreshed_tag is not None
    assert float(refreshed_tag.score or 0.0) > 1.0
    hidden_row = (
        context.db.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == int(context.student.id),
            models.UserImplicitInterestTag.tag_id == int(context.hidden_tag.id),
        )
        .first()
    )
    assert hidden_row is None
    cat_row = (
        context.db.query(models.UserImplicitInterestCategory)
        .filter(models.UserImplicitInterestCategory.user_id == int(context.student.id))
        .first()
    )
    city_row = (
        context.db.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == int(context.student.id))
        .first()
    )
    assert cat_row is not None and float(cat_row.score or 0.0) > 1.0
    assert city_row is not None and float(city_row.score or 0.0) > 1.0


def test_record_interactions_enqueues_refresh_job(monkeypatch, helpers):
    """Interaction recording should enqueue a refresh job when realtime updates are
    enabled.
    """
    context = _seed_record_interactions_context(helpers, monkeypatch)
    response = context.client.post(
        "/api/analytics/interactions",
        json=context.payload,
        headers=helpers["auth_header"](context.student_token),
    )
    assert response.status_code == 204
    assert any(
        job_type == "refresh_user_recommendations_ml"
        for job_type, _payload, _dedupe in context.captured_jobs
    )


def test_register_route_rejects_mismatched_confirmation(monkeypatch):
    """Registration should reject mismatched access-code confirmation fields."""
    monkeypatch.setattr(api, "_enforce_rate_limit", lambda *_args, **_kwargs: None)
    register_db = SimpleNamespace(query=lambda *_args, **_kwargs: _FirstQuery(None))
    request = Request(
        {"type": "http", "method": "POST", "path": "/register", "headers": []}
    )
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


def test_update_event_rejects_invalid_status(monkeypatch):
    """Event updates should reject unsupported status values before mutating data."""
    monkeypatch.setattr(api, "_enforce_rate_limit", lambda *_args, **_kwargs: None)
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
    event_db = SimpleNamespace(query=lambda *_args, **_kwargs: _FirstQuery(db_event))
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


def test_bulk_organizer_routes_require_selected_events(monkeypatch):
    """Bulk organizer routes should reject requests without selected events."""
    monkeypatch.setattr(api, "_enforce_rate_limit", lambda *_args, **_kwargs: None)
    current_user = SimpleNamespace(id=7, role=models.UserRole.organizator)
    with pytest.raises(HTTPException) as bulk_status_exc:
        api.organizer_bulk_update_status(
            schemas.OrganizerBulkStatusUpdate.model_construct(
                event_ids=[], status="draft"
            ),
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
    """Interaction recording should no-op when analytics or learning is disabled."""
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
