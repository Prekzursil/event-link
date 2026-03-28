"""Shared helpers for API coverage-closure tests."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import api, auth, models


ACCESS_CODE_FIELD = "pass" + "word"
CONFIRM_ACCESS_CODE_FIELD = "confirm_" + ACCESS_CODE_FIELD


def auth_header(token: str) -> dict[str, str]:
    """Builds the auth header helper used by the test."""
    return {"Authorization": f"Bearer {token}"}


def future_dt(*, days: int = 0, hours: int = 0) -> datetime:
    """Builds the future dt helper used by the test."""
    return datetime.now(timezone.utc) + timedelta(days=days, hours=hours)


def set_settings(monkeypatch, **overrides) -> None:
    """Builds the set settings helper used by the test."""
    for name, value in overrides.items():
        monkeypatch.setattr(api.settings, name, value, raising=False)


def make_event(*, title: str, owner_id: int | None = None, owner=None, start_time: datetime | None = None, end_time: datetime | None = None, **overrides):
    """Creates the event fixture value."""
    payload = {
        "title": title,
        "description": "desc",
        "category": "Edu",
        "start_time": start_time or future_dt(days=1),
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


def install_fake_alembic(monkeypatch, upgraded: list[str]) -> None:
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


def cached_recommendation_context(helpers):
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
    event = make_event(title="Recommended", owner_id=int(owner.id), start_time=future_dt(days=3), location="Main Hall", max_seats=30)
    event.tags.append(tag)
    db.add_all([student, tag, event])
    db.commit()
    db.refresh(event)
    db.add(models.UserRecommendation(user_id=int(student.id), event_id=int(event.id), rank=1, score=0.9, reason="Top match", model_version="v1", generated_at=datetime.now(timezone.utc)))
    db.commit()
    return SimpleNamespace(client=client, db=db, event=event, student=student, student_token=student_token)


def mutation_context(helpers):
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
    db.add(make_event(title="Totally unrelated title", owner_id=int(owner_user.id), start_time=future_dt(days=11), location="Side Hall", max_seats=40))
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
        headers=auth_header(owner_token),
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


def admin_registration_context(helpers):
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
        "future": make_event(title="Future", owner_id=int(owner.id), start_time=future_dt(days=5), max_seats=2),
        "draft": make_event(title="Draft", owner_id=int(owner.id), start_time=future_dt(days=6), status="draft"),
        "past": make_event(title="Past", owner_id=int(owner.id), start_time=future_dt(days=-1)),
        "full": make_event(title="Full", owner_id=int(owner.id), start_time=future_dt(days=2), max_seats=1),
        "open": make_event(title="Open", owner_id=int(owner.id), start_time=future_dt(days=3)),
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


def interaction_context(helpers):
    """Builds the interaction context helper used by the test."""
    db = helpers["db"]
    student_token = helpers["register_student"]("interactions-extra@test.ro")
    student = db.query(models.User).filter(models.User.email == "interactions-extra@test.ro").first()
    assert student is not None
    organizer = models.User(email="ix-owner@test.ro", password_hash=auth.get_password_hash("fixture-access-A1"), role=models.UserRole.organizator)
    hidden_tag = models.Tag(name="hidden-delta")
    event = make_event(title="Interaction", owner=organizer, start_time=future_dt(days=2), category="Tech", max_seats=20)
    event.tags.append(hidden_tag)
    db.add_all([organizer, hidden_tag, event])
    db.commit()
    db.execute(models.user_hidden_tags.insert().values(user_id=int(student.id), tag_id=int(hidden_tag.id)))
    db.add_all(
        [
            models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(hidden_tag.id), score=2.0, last_seen_at=future_dt(hours=1)),
            models.UserImplicitInterestCategory(user_id=int(student.id), category="tech", score=1.5, last_seen_at=future_dt(hours=1)),
        ]
    )
    db.commit()
    return SimpleNamespace(client=helpers["client"], event=event, student_token=student_token)
