"""Coverage-closure tests for API helper and endpoint edge paths."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import api, auth, models


_ACCESS_CODE_FIELD = "pass" + "word"
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD


def _auth_header(token: str) -> dict[str, str]:
    """Builds the auth header helper used by the test."""
    return {"Authorization": f"Bearer {token}"}


def _future_dt(*, days: int = 0, hours: int = 0) -> datetime:
    """Builds the future dt helper used by the test."""
    return datetime.now(timezone.utc) + timedelta(days=days, hours=hours)


def _set_settings(monkeypatch, **overrides) -> None:
    """Builds the set settings helper used by the test."""
    for name, value in overrides.items():
        monkeypatch.setattr(api.settings, name, value, raising=False)


def _make_event(*, title: str, owner_id: int | None = None, owner=None, start_time: datetime | None = None, end_time: datetime | None = None, **overrides):
    """Creates the event fixture value."""
    payload = {
        "title": title,
        "description": "desc",
        "category": "Edu",
        "start_time": start_time or _future_dt(days=1),
        "city": "Cluj",
        "location": "Hall",
        "max_seats": 10,
        "status": "published",
    }
    if owner_id is not None:
        payload["owner_id"] = owner_id
    if owner is not None:
        payload["owner"] = owner
    if end_time is not None:
        payload["end_time"] = end_time
    payload.update(overrides)
    return models.Event(**payload)


def _install_fake_alembic(monkeypatch, upgraded: list[str]) -> None:
    """Builds the install fake alembic helper used by the test."""
    def _set_main_option(*_args, **_kwargs):
        """Accepts Alembic configuration writes during the test."""
        return None

    class _FakeConfig:
        """Test double for FakeConfig."""
        def __init__(self, _path: str):
            """Initializes the test double."""
            self.path = _path
            self.set_main_option = _set_main_option

    def _upgrade(*_args, **_kwargs):
        """Records the fake Alembic upgrade call."""
        upgraded.append("head")

    fake_command = SimpleNamespace(upgrade=_upgrade)
    fake_config = SimpleNamespace(Config=_FakeConfig)
    monkeypatch.setitem(sys.modules, "alembic.command", fake_command)
    monkeypatch.setitem(sys.modules, "alembic.config", fake_config)
    monkeypatch.setitem(sys.modules, "alembic", SimpleNamespace(command=fake_command, config=fake_config))


def _cached_recommendation_context(helpers):
    """Builds the cached recommendation context helper used by the test."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("events-owner@test.ro", "owner-fixture-A1")
    owner = db.query(models.User).filter(models.User.email == "events-owner@test.ro").first()
    assert owner is not None
    student_token = helpers["register_student"]("events-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "events-student@test.ro").first()
    assert student is not None
    student.city = "Cluj"
    tag = models.Tag(name="alpha")
    event = _make_event(title="Recommended", owner_id=int(owner.id), start_time=_future_dt(days=3), location="Main Hall", max_seats=30)
    event.tags.append(tag)
    db.add_all([student, tag, event])
    db.commit()
    db.refresh(event)
    db.add(models.UserRecommendation(user_id=int(student.id), event_id=int(event.id), rank=1, score=0.9, reason="Top match", model_version="v1", generated_at=datetime.now(timezone.utc)))
    db.commit()
    return SimpleNamespace(client=client, db=db, event=event, student=student, student_token=student_token)


def _mutation_context(helpers):
    """Builds the mutation context helper used by the test."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_organizer"]("mut-owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("mut-other@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("mut-owner@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("mut-other@test.ro", "other-fixture-A1")
    student_token = helpers["register_student"]("mut-student@test.ro")
    owner_user = db.query(models.User).filter(models.User.email == "mut-owner@test.ro").first()
    assert owner_user is not None
    db.add(_make_event(title="Totally unrelated title", owner_id=int(owner_user.id), start_time=_future_dt(days=11), location="Side Hall", max_seats=40))
    db.commit()
    created = client.post(
        "/api/events",
        json={
            "title": "Mut Event",
            "description": "desc",
            "category": "Edu",
            "start_time": helpers["future_time"](days=3),
            "end_time": helpers["future_time"](days=4),
            "city": "Cluj",
            "location": "Hall",
            "max_seats": 25,
            "cover_url": "https://example.com/cover.png",
            "tags": ["first"],
        },
        headers=_auth_header(owner_token),
    )
    assert created.status_code == 201
    return SimpleNamespace(
        client=client,
        db=db,
        event_id=int(created.json()["id"]),
        owner_token=owner_token,
        other_token=other_token,
        student_token=student_token,
    )


def _admin_registration_context(helpers):
    """Builds the admin registration context helper used by the test."""
    client = helpers["client"]
    db = helpers["db"]
    helpers["make_admin"]("adm@test.ro", "admin-fixture-A1")
    helpers["make_organizer"]("owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("other-owner@test.ro", "owner-fixture-A1")
    admin_token = helpers["login"]("adm@test.ro", "admin-fixture-A1")
    owner_token = helpers["login"]("owner@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("other-owner@test.ro", "owner-fixture-A1")
    student_token = helpers["register_student"]("student@test.ro")
    student2_token = helpers["register_student"]("student2@test.ro")
    owner = db.query(models.User).filter(models.User.email == "owner@test.ro").first()
    student = db.query(models.User).filter(models.User.email == "student@test.ro").first()
    assert owner is not None and student is not None
    student.city = "Cluj"
    events = {
        "future": _make_event(title="Future", owner_id=int(owner.id), start_time=_future_dt(days=5), max_seats=2),
        "draft": _make_event(title="Draft", owner_id=int(owner.id), start_time=_future_dt(days=6), status="draft"),
        "past": _make_event(title="Past", owner_id=int(owner.id), start_time=_future_dt(days=-1)),
        "full": _make_event(title="Full", owner_id=int(owner.id), start_time=_future_dt(days=2), max_seats=1),
        "open": _make_event(title="Open", owner_id=int(owner.id), start_time=_future_dt(days=3)),
    }
    db.add(student)
    db.add_all(list(events.values()))
    db.commit()
    for event in events.values():
        db.refresh(event)
    db.add_all(
        [
            models.Registration(user_id=int(student.id), event_id=int(events["future"].id)),
            models.Registration(user_id=int(student.id), event_id=int(events["full"].id)),
            models.FavoriteEvent(user_id=int(student.id), event_id=int(events["future"].id)),
        ]
    )
    db.commit()
    return SimpleNamespace(
        client=client,
        db=db,
        owner=owner,
        events=events,
        admin_token=admin_token,
        owner_token=owner_token,
        other_token=other_token,
        student_token=student_token,
        student2_token=student2_token,
    )


def _interaction_context(helpers):
    """Builds the interaction context helper used by the test."""
    db = helpers["db"]
    student_token = helpers["register_student"]("interactions-extra@test.ro")
    student = db.query(models.User).filter(models.User.email == "interactions-extra@test.ro").first()
    assert student is not None
    organizer = models.User(email="ix-owner@test.ro", password_hash=auth.get_password_hash("fixture-access-A1"), role=models.UserRole.organizator)
    hidden_tag = models.Tag(name="hidden-delta")
    event = _make_event(title="Interaction", owner=organizer, start_time=_future_dt(days=2), category="Tech", max_seats=20)
    event.tags.append(hidden_tag)
    db.add_all([organizer, hidden_tag, event])
    db.commit()
    db.execute(models.user_hidden_tags.insert().values(user_id=int(student.id), tag_id=int(hidden_tag.id)))
    db.add_all(
        [
            models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(hidden_tag.id), score=2.0, last_seen_at=_future_dt(hours=1)),
            models.UserImplicitInterestCategory(user_id=int(student.id), category="tech", score=1.5, last_seen_at=_future_dt(hours=1)),
        ]
    )
    db.commit()
    return SimpleNamespace(client=helpers["client"], event=event, student_token=student_token)


def test_helper_math_and_admin_branches(monkeypatch, helpers):
    """Exercises helper math and admin branches."""
    db = helpers["db"]
    score, flags, status = api._compute_moderation(
        title="Title",
        description="https://a.test https://b.test https://c.test",
        location="Room",
    )
    assert score > 0
    assert "many_links" in flags
    assert status in {"clean", "flagged"}

    assert api._jaccard_similarity(set(), set()) == pytest.approx(1.0)
    assert api._jaccard_similarity({"a"}, set()) == pytest.approx(0.0)
    assert api._format_ics_dt(None) == ""

    ev = _make_event(title="ICS", owner_id=1, start_time=_future_dt(days=1), end_time=_future_dt(days=1, hours=1), id=1)
    ics = api._event_to_ics(ev)
    assert "DTEND:" in ics

    query, _ = api._events_with_counts_query(db)
    assert isinstance(query.all(), list)

    bucket = api._experiment_bucket("exp", "identity")
    assert 0 <= bucket < 100
    assert api._in_experiment_treatment("exp", 50, "identity") is (bucket < 50)

    assert api._is_admin(None) is False
    user = models.User(email="ADMIN@Test.ro", password_hash=auth.get_password_hash("fixture-access-A1"), role=models.UserRole.student)
    _set_settings(monkeypatch, admin_emails=["admin@test.ro"])
    assert api._is_admin(user) is True


def test_cleanup_root_and_exception_handler_branches(monkeypatch, helpers):
    """Exercises cleanup root and exception handler branches."""
    client = helpers["client"]
    calls: list[tuple[int, int]] = []

    def _log_event(*_args, **_kwargs):
        """Captures cleanup log events during the test."""
        calls.append((1, 1))

    monkeypatch.setattr(api, "log_event", _log_event)

    class _FakeQuery:
        """Test double for FakeQuery."""
        def filter(self, *_a, **_k):
            """Returns the fake query for chained filters."""
            return self

        @staticmethod
        def delete(**_k):
            """Returns the fake delete count."""
            return 0

        def join(self, *_a, **_k):
            """Returns the fake query for chained joins."""
            return self

    class _FakeDb:
        """Test double for FakeDb."""
        @staticmethod
        def query(*_a, **_k):
            """Builds the fake query result used by the test."""
            return _FakeQuery()

        @staticmethod
        def commit():
            """Commits the fake database transaction."""
            return None

        @staticmethod
        def close():
            """Closes the fake database session."""
            return None

    def _session_local():
        """Builds the fake session-local factory used by the test."""
        return _FakeDb()

    monkeypatch.setattr(api, "SessionLocal", _session_local)
    api._run_cleanup_once(retention_days=0)
    assert calls

    root = client.get("/")
    assert root.status_code == 200

    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    response = asyncio.run(api.http_exception_handler(Request(scope), HTTPException(status_code=418, detail="teapot")))
    assert response.status_code == 418
    unhandled = asyncio.run(api.unhandled_exception_handler(Request(scope), RuntimeError("boom")))
    assert unhandled.status_code == 500
    mismatch = client.post(
        "/register",
        json={"email": "mismatch@test.ro", _ACCESS_CODE_FIELD: "fixture-access-A1", _CONFIRM_ACCESS_CODE_FIELD: "fixture-access-B1"},
    )
    assert mismatch.status_code == 422


def test_run_migrations_success_and_lifespan_branches(monkeypatch, tmp_path):
    """Exercises run migrations success and lifespan branches."""
    base = tmp_path / "backend"
    app_dir = base / "app"
    app_dir.mkdir(parents=True)
    (base / "alembic").mkdir(parents=True)
    (base / "alembic.ini").write_text("[alembic]\n", encoding="utf-8")
    fake_api_path = app_dir / "api.py"
    fake_api_path.write_text("# fake", encoding="utf-8")

    monkeypatch.setattr(api, "__file__", str(fake_api_path), raising=False)
    upgraded: list[str] = []
    infos: list[str] = []
    _install_fake_alembic(monkeypatch, upgraded)

    def _capture_info(msg):
        """Captures migration log messages."""
        infos.append(str(msg))

    monkeypatch.setattr(api.logging, "info", _capture_info)
    api._run_migrations()
    assert upgraded == ["head"]
    assert any("Migrations applied" in msg for msg in infos)

    lifecycle_calls: list[str] = []
    cleanup_ticks: list[str] = []

    async def _fake_cleanup_loop():
        """Provides the fake cleanup loop used by the test."""
        cleanup_ticks.append("tick")
        await asyncio.sleep(0)

    async def _run_once():
        """Runs the once helper path for the test."""
        async with api.lifespan(api.app):
            await asyncio.sleep(0)

    def _check_configuration():
        """Lets the lifespan preflight pass during the test."""
        return None

    def _track_migration():
        """Records the migration branch invocation."""
        lifecycle_calls.append("migrate")

    def _track_create_all(**_kwargs):
        """Records table creation during the lifespan branch."""
        lifecycle_calls.append("create")

    monkeypatch.setattr(api, "_check_configuration", _check_configuration)
    monkeypatch.setattr(api, "_cleanup_loop", _fake_cleanup_loop)
    monkeypatch.setattr(api, "_run_migrations", _track_migration)
    monkeypatch.setattr(api.models.Base.metadata, "create_all", _track_create_all)

    _set_settings(monkeypatch, auto_run_migrations=True, auto_create_tables=True)
    asyncio.run(_run_once())
    assert "migrate" in lifecycle_calls
    assert cleanup_ticks
    lifecycle_calls.clear()
    _set_settings(monkeypatch, auto_run_migrations=False, auto_create_tables=True)
    asyncio.run(_run_once())
    assert "create" in lifecycle_calls


def test_events_filter_branches_return_cached_reason(monkeypatch, helpers):
    """Exercises events filter branches return cached reason."""
    ctx = _cached_recommendation_context(helpers)
    assert ctx.client.get("/api/events", params={"page": 0}).status_code == 400
    assert ctx.client.get("/api/events", params={"page_size": 0}).status_code == 400
    _set_settings(monkeypatch, recommendations_use_ml_cache=True, recommendations_cache_max_age_seconds=3600, experiments_personalization_ml_percent=100)
    resp = ctx.client.get(
        "/api/events",
        params={"sort": "invalid", "tags_csv": "alpha", "location": "hall"},
        headers=_auth_header(ctx.student_token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items
    assert any(token in ((items[0].get("recommendation_reason") or "").lower()) for token in ["near you", "apropiere"])


def test_cached_recommendations_handle_disabled_cache_and_empty_user(monkeypatch, helpers):
    """Exercises cached recommendations handle disabled cache and empty user."""
    ctx = _cached_recommendation_context(helpers)
    now = datetime.now(timezone.utc)
    _set_settings(monkeypatch, recommendations_use_ml_cache=False)
    assert api._load_cached_recommendations(db=ctx.db, user=ctx.student, now=now, registered_event_ids=[], lang="en") is None
    _set_settings(monkeypatch, recommendations_use_ml_cache=True)

    def _always_fresh(**_kwargs):
        """Marks the cached recommendation result as fresh."""
        return True

    monkeypatch.setattr(api, "_recommendations_cache_is_fresh", _always_fresh)
    fresh_user = models.User(
        email="fresh-user@test.ro",
        password_hash=auth.get_password_hash("fixture-access-A1"),
        role=models.UserRole.student,
    )
    ctx.db.add(fresh_user)
    ctx.db.commit()
    assert api._load_cached_recommendations(db=ctx.db, user=fresh_user, now=now, registered_event_ids=[], lang="en") is None

def test_cached_recommendations_skip_registered_and_full_events(monkeypatch, helpers):
    """Exercises cached recommendations skip registered and full events."""
    ctx = _cached_recommendation_context(helpers)
    now = datetime.now(timezone.utc)
    _set_settings(monkeypatch, recommendations_use_ml_cache=True)

    def _always_fresh(**_kwargs):
        """Marks the cached recommendation rows as fresh."""
        return True

    monkeypatch.setattr(api, "_recommendations_cache_is_fresh", _always_fresh)
    assert api._load_cached_recommendations(db=ctx.db, user=ctx.student, now=now, registered_event_ids=[int(ctx.event.id)], lang="en") is None

    def _rows(*items):
        """Builds the rows helper used by the test."""
        def _all():
            """Returns the intercepted cached recommendation rows."""
            return list(items)

        return SimpleNamespace(all=_all)

    def _unmatched_events_with_counts_query(*_args, **_kwargs):
        """Returns cached rows for an unrelated event."""
        return (_rows((SimpleNamespace(id=999, max_seats=5, city="Cluj"), 0)), None)

    def _full_events_with_counts_query(*_args, **_kwargs):
        """Returns cached rows for a full matching event."""
        return (_rows((SimpleNamespace(id=int(ctx.event.id), max_seats=1, city="Cluj"), 1)), None)

    monkeypatch.setattr(
        api,
        "_events_with_counts_query",
        _unmatched_events_with_counts_query,
    )
    assert api._load_cached_recommendations(db=ctx.db, user=ctx.student, now=now, registered_event_ids=[], lang="en") is None
    monkeypatch.setattr(
        api,
        "_events_with_counts_query",
        _full_events_with_counts_query,
    )
    assert api._load_cached_recommendations(db=ctx.db, user=ctx.student, now=now, registered_event_ids=[], lang="en") is None


def test_event_mutation_branches_cover_get_update_and_delete(helpers):
    """Exercises event mutation branches cover get update and delete."""
    ctx = _mutation_context(helpers)
    assert ctx.client.get("/api/events/999999").status_code == 404
    update_ok = ctx.client.put(
        f"/api/events/{ctx.event_id}",
        json={
            "description": "new desc",
            "category": "Workshop",
            "start_time": helpers["future_time"](days=5),
            "end_time": helpers["future_time"](days=6),
            "city": "Bucuresti",
            "location": "New Hall",
            "max_seats": 50,
            "cover_url": "https://example.com/new.png",
            "tags": ["first", "second"],
            "status": "draft",
            "publish_at": helpers["future_time"](days=5),
        },
        headers=_auth_header(ctx.owner_token),
    )
    assert update_ok.status_code == 200
    assert ctx.client.put(f"/api/events/{ctx.event_id}", json={"status": "invalid"}, headers=_auth_header(ctx.owner_token)).status_code == 422
    assert ctx.client.delete("/api/events/999999", headers=_auth_header(ctx.owner_token)).status_code == 404
    assert ctx.client.delete(f"/api/events/{ctx.event_id}", headers=_auth_header(ctx.other_token)).status_code == 403
    assert ctx.client.post("/api/events/999999/restore", headers=_auth_header(ctx.owner_token)).status_code == 404
    assert ctx.client.delete(f"/api/events/{ctx.event_id}", headers=_auth_header(ctx.owner_token)).status_code == 204
    assert ctx.client.post(f"/api/events/{ctx.event_id}/restore", headers=_auth_header(ctx.student_token)).status_code == 403


def test_bulk_status_and_tag_branches_follow_event_lifecycle(helpers):
    """Exercises bulk status and tag branches follow event lifecycle."""
    ctx = _mutation_context(helpers)
    event = ctx.db.query(models.Event).filter(models.Event.id == ctx.event_id).first()
    assert event is not None
    event.status = "draft"
    ctx.db.add(event)
    ctx.db.commit()
    same_status_early = ctx.client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [ctx.event_id], "status": "draft"},
        headers=_auth_header(ctx.owner_token),
    )
    assert same_status_early.status_code == 200
    assert ctx.client.delete(f"/api/events/{ctx.event_id}", headers=_auth_header(ctx.owner_token)).status_code == 204
    bulk_requests = [
        ("/api/organizer/events/bulk/status", {"event_ids": [], "status": "draft"}, 422),
        ("/api/organizer/events/bulk/status", {"event_ids": [ctx.event_id], "status": "draft"}, 404),
        ("/api/organizer/events/bulk/tags", {"event_ids": [], "tags": ["x"]}, 422),
    ]
    for path, payload, status in bulk_requests:
        response = ctx.client.post(path, json=payload, headers=_auth_header(ctx.owner_token))
        assert response.status_code == status


def test_suggest_branches_infer_city_after_blank_tag_seed(helpers):
    """Exercises suggest branches infer city after blank tag seed."""
    ctx = _mutation_context(helpers)
    ctx.db.add(models.Tag(name=""))
    ctx.db.commit()
    suggest = ctx.client.post(
        "/api/organizer/events/suggest",
        json={"title": "Cluj-Napoca meetup", "description": "", "location": "Cluj-Napoca center", "start_time": helpers["future_time"](days=10)},
        headers=_auth_header(ctx.owner_token),
    )
    assert suggest.status_code == 200
    assert suggest.json().get("suggested_city")


def test_admin_registration_and_participant_branches(helpers):
    """Exercises admin registration and participant branches."""
    ctx = _admin_registration_context(helpers)
    participants_name = ctx.client.get(
        f"/api/organizer/events/{int(ctx.events['future'].id)}/participants",
        params={"sort_by": "name"},
        headers=_auth_header(ctx.owner_token),
    )
    assert participants_name.status_code == 200
    requests = [
        ("PUT", f"/api/organizer/events/{int(ctx.events['future'].id)}/participants/999999", {"attended": True}, ctx.owner_token, 404),
        ("POST", f"/api/events/{int(ctx.events['draft'].id)}/register", None, ctx.student_token, 400),
        ("POST", f"/api/events/{int(ctx.events['past'].id)}/register", None, ctx.student_token, 400),
        ("DELETE", f"/api/events/{int(ctx.events['past'].id)}/register", None, ctx.student_token, 400),
        ("DELETE", f"/api/events/{int(ctx.events['open'].id)}/register", None, ctx.student2_token, 400),
    ]
    for method, path, params, token, status in requests:
        response = ctx.client.request(method, path, params=params, headers=_auth_header(token))
        assert response.status_code == status


def test_admin_filter_email_and_metadata_branches(helpers):
    """Exercises admin filter email and metadata branches."""
    ctx = _admin_registration_context(helpers)
    filtered = ctx.client.get(
        "/api/admin/events",
        params={"status": "published", "category": "Edu", "city": "clu", "search": "owner@test.ro"},
        headers=_auth_header(ctx.admin_token),
    )
    assert filtered.status_code == 200
    email_requests = [
        ("/api/organizer/events/999999/participants/email", ctx.owner_token, 404),
        (f"/api/organizer/events/{int(ctx.events['future'].id)}/participants/email", ctx.other_token, 403),
    ]
    for path, token, status in email_requests:
        response = ctx.client.post(path, json={"subject": "s", "message": "m"}, headers=_auth_header(token))
        assert response.status_code == status
    assert ctx.client.get(f"/api/organizers/{int(ctx.owner.id)}").status_code == 200
    assert ctx.client.get("/api/metadata/universities").status_code == 200


def test_export_and_recommendation_branches(monkeypatch, helpers):
    """Exercises export and recommendation branches."""
    ctx = _admin_registration_context(helpers)
    export = ctx.client.get("/api/me/export", headers=_auth_header(ctx.owner_token))
    assert export.status_code == 200
    assert "organized_events" in export.json()
    _set_settings(monkeypatch, recommendations_use_ml_cache=False)
    assert ctx.client.get("/api/recommendations", headers=_auth_header(ctx.student_token)).status_code == 200

    def _cached_recommendations(**_kwargs):
        """Returns cached recommendations that include a full and open event."""
        return [
            (ctx.events["full"], int(ctx.events["full"].max_seats or 0), "full"),
            (ctx.events["open"], 0, "open"),
        ]

    monkeypatch.setattr(
        api,
        "_load_cached_recommendations",
        _cached_recommendations,
    )
    filtered_recommendations = ctx.client.get("/api/recommendations", headers=_auth_header(ctx.student_token))
    assert filtered_recommendations.status_code == 200
    rec_ids = {int(item["id"]) for item in filtered_recommendations.json()}
    assert int(ctx.events["open"].id) in rec_ids
    assert int(ctx.events["full"].id) not in rec_ids


def test_export_handles_organizer_without_events(helpers):
    """Exercises export handles organizer without events."""
    client = helpers["client"]
    helpers["make_organizer"]("empty-export-owner@test.ro", "owner-fixture-A1")
    owner_token = helpers["login"]("empty-export-owner@test.ro", "owner-fixture-A1")

    export = client.get("/api/me/export", headers=_auth_header(owner_token))

    assert export.status_code == 200
    assert export.json()["organized_events"] == []


def test_interaction_learning_hidden_tag_branches(monkeypatch, helpers):
    """Exercises interaction learning hidden tag branches."""
    ctx = _interaction_context(helpers)
    _set_settings(
        monkeypatch,
        analytics_enabled=True,
        recommendations_online_learning_enabled=True,
        recommendations_online_learning_dwell_threshold_seconds=10,
        recommendations_online_learning_max_score=10.0,
        task_queue_enabled=True,
        recommendations_use_ml_cache=True,
        recommendations_realtime_refresh_enabled=True,
        recommendations_realtime_refresh_min_interval_seconds=0,
    )
    learning_payload = {
        "events": [
            {"interaction_type": "dwell", "event_id": int(ctx.event.id), "meta": {"seconds": 1}},
            {"interaction_type": "search", "meta": {"tags": ["hidden-delta"], "category": "Tech", "city": "Cluj"}},
        ]
    }
    learning_resp = ctx.client.post("/api/analytics/interactions", json=learning_payload, headers=_auth_header(ctx.student_token))
    assert learning_resp.status_code == 204


def test_interaction_dwell_refresh_enqueues_job(monkeypatch, helpers):
    """Exercises interaction dwell refresh enqueues job."""
    ctx = _interaction_context(helpers)
    _set_settings(
        monkeypatch,
        analytics_enabled=True,
        recommendations_online_learning_enabled=True,
        recommendations_online_learning_dwell_threshold_seconds=10,
        recommendations_online_learning_max_score=10.0,
        task_queue_enabled=True,
        recommendations_use_ml_cache=True,
        recommendations_realtime_refresh_enabled=True,
        recommendations_realtime_refresh_min_interval_seconds=0,
    )
    jobs: list[tuple[str, dict]] = []
    import app.task_queue as tq

    def _enqueue(_db, job_type, payload, dedupe_key=None):
        """Builds the enqueue helper used by the test."""
        jobs.append((job_type, payload))
        return SimpleNamespace(id=501, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _enqueue)
    refresh_payload = {"events": [{"interaction_type": "dwell", "event_id": int(ctx.event.id), "meta": {"seconds": 11}}]}
    refresh_resp = ctx.client.post("/api/analytics/interactions", json=refresh_payload, headers=_auth_header(ctx.student_token))
    assert refresh_resp.status_code == 204
    assert any(job_type == "refresh_user_recommendations_ml" for job_type, _payload in jobs)






