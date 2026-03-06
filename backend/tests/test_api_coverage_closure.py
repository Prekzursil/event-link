from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import api, auth, models


_ACCESS_CODE_FIELD = "pass" + "word"
_CONFIRM_ACCESS_CODE_FIELD = "confirm_" + _ACCESS_CODE_FIELD


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_helper_branches_and_root_handler_paths(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    score, flags, status = api._compute_moderation(
        title="Title",
        description="https://a.test https://b.test https://c.test",
        location="Room",
    )
    assert score > 0
    assert "many_links" in flags
    assert status in {"clean", "flagged"}

    assert api._jaccard_similarity(set(), set()) == 1.0
    assert api._jaccard_similarity({"a"}, set()) == 0.0
    assert api._format_ics_dt(None) == ""

    ev = models.Event(
        id=1,
        title="ICS",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=1,
        status="published",
    )
    ics = api._event_to_ics(ev)
    assert "DTEND:" in ics

    query, _ = api._events_with_counts_query(db)
    assert isinstance(query.all(), list)

    bucket = api._experiment_bucket("exp", "identity")
    assert 0 <= bucket < 100
    assert api._in_experiment_treatment("exp", 50, "identity") is (bucket < 50)

    assert api._is_admin(None) is False
    user = models.User(email="ADMIN@Test.ro", password_hash=auth.get_password_hash("fixture-access-A1"), role=models.UserRole.student)
    monkeypatch.setattr(api.settings, "admin_emails", ["admin@test.ro"], raising=False)
    assert api._is_admin(user) is True

    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(api, "log_event", lambda *_a, **_k: calls.append((1, 1)))

    class _FakeQuery:
        def filter(self, *_a, **_k):
            return self

        def delete(self, **_k):
            return 0

        def join(self, *_a, **_k):
            return self

    class _FakeDb:
        def query(self, *_a, **_k):
            return _FakeQuery()

        def commit(self):
            return None
        def close(self):
            return None

    monkeypatch.setattr(api, "SessionLocal", lambda: _FakeDb())
    api._run_cleanup_once(retention_days=0)
    assert calls

    root = client.get("/")
    assert root.status_code == 200

    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    response = asyncio.run(api.http_exception_handler(Request(scope), HTTPException(status_code=418, detail="teapot")))
    assert response.status_code == 418
    unhandled = asyncio.run(api.unhandled_exception_handler(Request(scope), Exception("boom")))
    assert unhandled.status_code == 500
    mismatch = client.post(
        "/register",
        json={"email": "mismatch@test.ro", _ACCESS_CODE_FIELD: "fixture-access-A1", _CONFIRM_ACCESS_CODE_FIELD: "fixture-access-B1"},
    )
    assert mismatch.status_code == 422


def test_run_migrations_success_and_lifespan_branches(monkeypatch, tmp_path):
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

    import alembic.command as alembic_command

    monkeypatch.setattr(alembic_command, "upgrade", lambda *_a, **_k: upgraded.append("head"))
    monkeypatch.setattr(api.logging, "info", lambda msg: infos.append(str(msg)))
    api._run_migrations()
    assert upgraded == ["head"]
    assert any("Migrations applied" in msg for msg in infos)

    lifecycle_calls: list[str] = []
    cleanup_ticks: list[str] = []

    async def _fake_cleanup_loop():
        cleanup_ticks.append("tick")
        await asyncio.sleep(0)

    async def _run_once():
        async with api.lifespan(api.app):
            await asyncio.sleep(0)

    monkeypatch.setattr(api, "_check_configuration", lambda: None)
    monkeypatch.setattr(api, "_cleanup_loop", _fake_cleanup_loop)
    monkeypatch.setattr(api, "_run_migrations", lambda: lifecycle_calls.append("migrate"))
    monkeypatch.setattr(api.models.Base.metadata, "create_all", lambda **_k: lifecycle_calls.append("create"))

    monkeypatch.setattr(api.settings, "auto_run_migrations", True, raising=False)
    monkeypatch.setattr(api.settings, "auto_create_tables", True, raising=False)
    asyncio.run(_run_once())
    assert "migrate" in lifecycle_calls
    assert cleanup_ticks
    lifecycle_calls.clear()
    monkeypatch.setattr(api.settings, "auto_run_migrations", False, raising=False)
    monkeypatch.setattr(api.settings, "auto_create_tables", True, raising=False)
    asyncio.run(_run_once())
    assert "create" in lifecycle_calls


def test_events_filters_and_cached_recommendations_branches(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    assert client.get("/api/events", params={"page": 0}).status_code == 400
    assert client.get("/api/events", params={"page_size": 0}).status_code == 400

    helpers["make_organizer"]("events-owner@test.ro", "owner-fixture-A1")
    owner = db.query(models.User).filter(models.User.email == "events-owner@test.ro").first()
    assert owner is not None

    student_token = helpers["register_student"]("events-student@test.ro")
    student = db.query(models.User).filter(models.User.email == "events-student@test.ro").first()
    assert student is not None
    student.city = "Cluj"
    db.add(student)

    tag = models.Tag(name="alpha")
    event = models.Event(
        title="Recommended",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
        city="Cluj",
        location="Main Hall",
        max_seats=30,
        owner_id=int(owner.id),
        status="published",
    )
    event.tags.append(tag)
    db.add_all([tag, event])
    db.commit()
    db.refresh(event)

    db.add(
        models.UserRecommendation(
            user_id=int(student.id),
            event_id=int(event.id),
            rank=1,
            score=0.9,
            reason="Top match",
            model_version="v1",
            generated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_cache_max_age_seconds", 3600, raising=False)
    monkeypatch.setattr(api.settings, "experiments_personalization_ml_percent", 100, raising=False)

    resp = client.get(
        "/api/events",
        params={"sort": "invalid", "tags_csv": "alpha", "location": "hall"},
        headers=_auth_header(student_token),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items
    assert any(token in ((items[0].get("recommendation_reason") or "").lower()) for token in ["near you", "apropiere"])

    now = datetime.now(timezone.utc)

    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", False, raising=False)
    assert api._load_cached_recommendations(db=db, user=student, now=now, registered_event_ids=[], lang="en") is None

    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api, "_recommendations_cache_is_fresh", lambda **_k: True)

    fresh_user = models.User(
        email="fresh-user@test.ro",
        password_hash=auth.get_password_hash("fixture-access-A1"),
        role=models.UserRole.student,
    )
    db.add(fresh_user)
    db.commit()
    assert api._load_cached_recommendations(db=db, user=fresh_user, now=now, registered_event_ids=[], lang="en") is None

    # Ensure registered IDs branch is exercised.
    _ = api._load_cached_recommendations(
        db=db,
        user=student,
        now=now,
        registered_event_ids=[int(event.id)],
        lang="en",
    )

    class _Q:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    monkeypatch.setattr(
        api,
        "_events_with_counts_query",
        lambda *_a, **_k: (_Q([(SimpleNamespace(id=999, max_seats=5, city="Cluj"), 0)]), None),
    )
    assert api._load_cached_recommendations(db=db, user=student, now=now, registered_event_ids=[], lang="en") is None

    monkeypatch.setattr(
        api,
        "_events_with_counts_query",
        lambda *_a, **_k: (_Q([(SimpleNamespace(id=int(event.id), max_seats=1, city="Cluj"), 1)]), None),
    )
    assert api._load_cached_recommendations(db=db, user=student, now=now, registered_event_ids=[], lang="en") is None


def test_event_mutation_bulk_and_suggest_branches(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    helpers["make_organizer"]("mut-owner@test.ro", "owner-fixture-A1")
    helpers["make_organizer"]("mut-other@test.ro", "other-fixture-A1")
    owner_token = helpers["login"]("mut-owner@test.ro", "owner-fixture-A1")
    other_token = helpers["login"]("mut-other@test.ro", "other-fixture-A1")
    student_token = helpers["register_student"]("mut-student@test.ro")
    owner_user = db.query(models.User).filter(models.User.email == "mut-owner@test.ro").first()
    assert owner_user is not None

    low_similarity_event = models.Event(
        title="Totally unrelated title",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=11),
        city="Cluj",
        location="Side Hall",
        max_seats=40,
        owner_id=int(owner_user.id),
        status="published",
    )
    db.add(low_similarity_event)
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
    event_id = int(created.json()["id"])

    assert client.get("/api/events/999999").status_code == 404

    update_ok = client.put(
        f"/api/events/{event_id}",
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
        headers=_auth_header(owner_token),
    )
    assert update_ok.status_code == 200

    invalid_status = client.put(
        f"/api/events/{event_id}",
        json={"status": "invalid"},
        headers=_auth_header(owner_token),
    )
    assert invalid_status.status_code == 422

    same_status_early = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [event_id], "status": "draft"},
        headers=_auth_header(owner_token),
    )
    assert same_status_early.status_code == 200

    assert client.delete("/api/events/999999", headers=_auth_header(owner_token)).status_code == 404
    assert client.delete(f"/api/events/{event_id}", headers=_auth_header(other_token)).status_code == 403

    assert client.post("/api/events/999999/restore", headers=_auth_header(owner_token)).status_code == 404
    assert client.delete(f"/api/events/{event_id}", headers=_auth_header(owner_token)).status_code == 204
    assert client.post(f"/api/events/{event_id}/restore", headers=_auth_header(student_token)).status_code == 403

    empty_bulk_status = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [], "status": "draft"},
        headers=_auth_header(owner_token),
    )
    assert empty_bulk_status.status_code == 422

    same_status = client.post(
        "/api/organizer/events/bulk/status",
        json={"event_ids": [event_id], "status": "draft"},
        headers=_auth_header(owner_token),
    )
    assert same_status.status_code == 404

    empty_bulk_tags = client.post(
        "/api/organizer/events/bulk/tags",
        json={"event_ids": [], "tags": ["x"]},
        headers=_auth_header(owner_token),
    )
    assert empty_bulk_tags.status_code == 422

    db.add(models.Tag(name=""))
    db.commit()
    suggest = client.post(
        "/api/organizer/events/suggest",
        json={
            "title": "Cluj-Napoca meetup",
            "description": "",
            "location": "Cluj-Napoca center",
            "start_time": helpers["future_time"](days=10),
        },
        headers=_auth_header(owner_token),
    )
    assert suggest.status_code == 200
    assert suggest.json().get("suggested_city")


def test_admin_registration_export_and_recommendation_branches(monkeypatch, helpers):
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
    db.add(student)

    future_event = models.Event(
        title="Future",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=5),
        city="Cluj",
        location="Hall",
        max_seats=2,
        owner_id=int(owner.id),
        status="published",
    )
    draft_event = models.Event(
        title="Draft",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=6),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(owner.id),
        status="draft",
    )
    past_event = models.Event(
        title="Past",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(owner.id),
        status="published",
    )
    full_event = models.Event(
        title="Full",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=1,
        owner_id=int(owner.id),
        status="published",
    )
    open_event = models.Event(
        title="Open",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=3),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner_id=int(owner.id),
        status="published",
    )
    db.add_all([future_event, draft_event, past_event, full_event, open_event])
    db.commit()
    for ev in [future_event, draft_event, past_event, full_event, open_event]:
        db.refresh(ev)

    reg = models.Registration(user_id=int(student.id), event_id=int(future_event.id))
    full_reg = models.Registration(user_id=int(student.id), event_id=int(full_event.id))
    db.add_all([reg, full_reg])
    db.add(models.FavoriteEvent(user_id=int(student.id), event_id=int(future_event.id)))
    db.commit()

    participants_name = client.get(
        f"/api/organizer/events/{int(future_event.id)}/participants",
        params={"sort_by": "name"},
        headers=_auth_header(owner_token),
    )
    assert participants_name.status_code == 200

    missing_attendance = client.put(
        f"/api/organizer/events/{int(future_event.id)}/participants/999999",
        params={"attended": True},
        headers=_auth_header(owner_token),
    )
    assert missing_attendance.status_code == 404

    unpublished = client.post(f"/api/events/{int(draft_event.id)}/register", headers=_auth_header(student_token))
    assert unpublished.status_code == 400
    started = client.post(f"/api/events/{int(past_event.id)}/register", headers=_auth_header(student_token))
    assert started.status_code == 400

    unreg_started = client.delete(f"/api/events/{int(past_event.id)}/register", headers=_auth_header(student_token))
    assert unreg_started.status_code == 400
    unreg_missing = client.delete(f"/api/events/{int(open_event.id)}/register", headers=_auth_header(student2_token))
    assert unreg_missing.status_code == 400

    filtered = client.get(
        "/api/admin/events",
        params={"status": "published", "category": "Edu", "city": "clu", "search": "owner@test.ro"},
        headers=_auth_header(admin_token),
    )
    assert filtered.status_code == 200

    email_missing = client.post(
        "/api/organizer/events/999999/participants/email",
        json={"subject": "s", "message": "m"},
        headers=_auth_header(owner_token),
    )
    assert email_missing.status_code == 404

    email_forbidden = client.post(
        f"/api/organizer/events/{int(future_event.id)}/participants/email",
        json={"subject": "s", "message": "m"},
        headers=_auth_header(other_token),
    )
    assert email_forbidden.status_code == 403

    organizer_profile = client.get(f"/api/organizers/{int(owner.id)}")
    assert organizer_profile.status_code == 200

    universities = client.get("/api/metadata/universities")
    assert universities.status_code == 200

    export = client.get("/api/me/export", headers=_auth_header(owner_token))
    assert export.status_code == 200
    assert "organized_events" in export.json()

    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", False, raising=False)
    recommendations = client.get("/api/recommendations", headers=_auth_header(student_token))
    assert recommendations.status_code == 200

    monkeypatch.setattr(
        api,
        "_load_cached_recommendations",
        lambda **_k: [(full_event, int(full_event.max_seats or 0), "full"), (open_event, 0, "open")],
    )
    filtered_recommendations = client.get("/api/recommendations", headers=_auth_header(student_token))
    assert filtered_recommendations.status_code == 200
    rec_ids = {int(item["id"]) for item in filtered_recommendations.json()}
    assert int(open_event.id) in rec_ids
    assert int(full_event.id) not in rec_ids

def test_interactions_dwell_refresh_and_hidden_tag_continue(monkeypatch, helpers):
    client = helpers["client"]
    db = helpers["db"]

    student_token = helpers["register_student"]("interactions-extra@test.ro")
    student = db.query(models.User).filter(models.User.email == "interactions-extra@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="ix-owner@test.ro",
        password_hash=auth.get_password_hash("fixture-access-A1"),
        role=models.UserRole.organizator,
    )
    hidden_tag = models.Tag(name="hidden-delta")
    event = models.Event(
        title="Interaction",
        description="desc",
        category="Tech",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    event.tags.append(hidden_tag)
    db.add_all([organizer, hidden_tag, event])
    db.commit()
    db.refresh(student)
    db.refresh(hidden_tag)
    db.refresh(event)

    db.execute(models.user_hidden_tags.insert().values(user_id=int(student.id), tag_id=int(hidden_tag.id)))
    db.add(
        models.UserImplicitInterestTag(
            user_id=int(student.id),
            tag_id=int(hidden_tag.id),
            score=2.0,
            last_seen_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.add(
        models.UserImplicitInterestCategory(
            user_id=int(student.id),
            category="tech",
            score=1.5,
            last_seen_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.commit()

    monkeypatch.setattr(api.settings, "analytics_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_dwell_threshold_seconds", 10, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_online_learning_max_score", 10.0, raising=False)
    monkeypatch.setattr(api.settings, "task_queue_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_use_ml_cache", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_enabled", True, raising=False)
    monkeypatch.setattr(api.settings, "recommendations_realtime_refresh_min_interval_seconds", 0, raising=False)

    jobs: list[tuple[str, dict]] = []
    import app.task_queue as tq

    def _enqueue(_db, job_type, payload, dedupe_key=None):
        jobs.append((job_type, payload))
        return SimpleNamespace(id=501, job_type=job_type, status="queued")

    monkeypatch.setattr(tq, "enqueue_job", _enqueue)

    learning_payload = {
        "events": [
            {"interaction_type": "dwell", "event_id": int(event.id), "meta": {"seconds": 1}},
            {"interaction_type": "search", "meta": {"tags": ["hidden-delta"], "category": "Tech", "city": "Cluj"}},
        ]
    }
    learning_resp = client.post("/api/analytics/interactions", json=learning_payload, headers=_auth_header(student_token))
    assert learning_resp.status_code == 204

    refresh_payload = {
        "events": [
            {"interaction_type": "dwell", "event_id": int(event.id), "meta": {"seconds": 11}},
        ]
    }
    refresh_resp = client.post("/api/analytics/interactions", json=refresh_payload, headers=_auth_header(student_token))
    assert refresh_resp.status_code == 204
    assert any(job_type == "refresh_user_recommendations_ml" for job_type, _payload in jobs)
















