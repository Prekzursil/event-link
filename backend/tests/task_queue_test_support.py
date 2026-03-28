"""Shared helpers for task queue unit tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app import auth, models, task_queue


def mk_job(db_session, *, job_type: str, payload: dict | None = None, status: str = "queued", run_at=None):
    job = models.BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        status=status,
        attempts=0,
        max_attempts=3,
        run_at=run_at or datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def unexpected_enqueue(*_args, **_kwargs):
    raise AssertionError("enqueue_job should not run")


def raise_assertion(message: str) -> None:
    raise AssertionError(message)


def raise_queue_empty() -> None:
    raise task_queue.queue.Empty


def make_user(email: str, password: str, role: models.UserRole, **overrides):
    return models.User(
        email=email,
        password_hash=auth.get_password_hash(password),
        role=role,
        **overrides,
    )


def make_event(title: str, owner, *, when: datetime, max_seats: int | None, **overrides):
    return models.Event(
        title=title,
        description="desc",
        category="Edu",
        start_time=when,
        city="Cluj",
        location="Hall",
        max_seats=max_seats,
        owner=owner,
        status="published",
        **overrides,
    )


def interaction(*, user_id: int, event_id: int, kind: str, occurred_at: datetime, meta=None):
    payload = {
        "user_id": user_id,
        "event_id": event_id,
        "interaction_type": kind,
        "occurred_at": occurred_at,
    }
    if meta is not None:
        payload["meta"] = meta
    return models.EventInteraction(**payload)


def reset_guardrail_state(db_session) -> None:
    db_session.query(models.EventInteraction).delete()
    db_session.query(models.RecommenderModel).delete()
    db_session.commit()


def add_balanced_guardrail_rows(db_session, *, user_id: int, event_id: int, now: datetime) -> None:
    rows = []
    for sort in ("recommended", "time"):
        rows.extend(
            [
                interaction(user_id=user_id, event_id=event_id, kind="impression", occurred_at=now, meta={"source": "events_list", "sort": sort}),
                interaction(
                    user_id=user_id,
                    event_id=event_id,
                    kind="click",
                    occurred_at=now + timedelta(minutes=1),
                    meta={"source": "events_list", "sort": sort},
                ),
                interaction(user_id=user_id, event_id=event_id, kind="register", occurred_at=now + timedelta(minutes=5)),
            ]
        )
    db_session.add_all(rows)
    db_session.commit()


def seed_weekly_digest_fixture(db_session):
    now = datetime.now(timezone.utc)
    users = {
        name: make_user(email, "student-fixture-A1", models.UserRole.student, **overrides)
        for name, email, overrides in [
            ("active", "digest-active@test.ro", {"is_active": True, "email_digest_enabled": True, "language_preference": "system"}),
            ("inactive", "digest-inactive@test.ro", {"is_active": False, "email_digest_enabled": True, "language_preference": "system"}),
            ("disabled", "digest-disabled@test.ro", {"is_active": True, "email_digest_enabled": False, "language_preference": "system"}),
        ]
    }
    organizer = make_user("digest-org@test.ro", "organizer-fixture-A1", models.UserRole.organizator)
    event = make_event("Digest Event", organizer, when=now + timedelta(days=2), max_seats=20)
    db_session.add_all([*users.values(), organizer, event])
    db_session.commit()
    db_session.add(
        models.UserRecommendation(
            user_id=int(users["active"].id),
            event_id=int(event.id),
            score=0.87,
            rank=1,
            model_version="test",
            reason=None,
            generated_at=now,
        )
    )
    db_session.commit()
    return users, event


def seed_filling_fast_branch_matrix(db_session):
    now = datetime.now(timezone.utc)
    organizer = make_user("branch-org@test.ro", "organizer-fixture-A1", models.UserRole.organizator)
    hidden_tag = models.Tag(name="hidden-branch")
    events = {
        name: make_event(title, organizer, when=now + timedelta(days=days), max_seats=seats)
        for name, title, seats, days in [
            ("limit_first", "limit-first", 4, 2),
            ("limit_second", "limit-second", 4, 3),
            ("blocked", "blocked", 10, 2),
            ("hidden", "hidden", 10, 2),
            ("full", "full", 1, 2),
            ("abundant", "abundant", 100, 2),
            ("system", "system", 2, 2),
        ]
    }
    events["hidden"].tags.append(hidden_tag)
    users = {
        name: make_user(email, "student-fixture-A1", models.UserRole.student, **overrides)
        for name, email, overrides in [
            ("inactive", "inactive@test.ro", {"is_active": False, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("disabled", "disabled@test.ro", {"is_active": True, "email_filling_fast_enabled": False, "language_preference": "en"}),
            ("limited", "limited@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("blocked", "blocked@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("hidden", "hidden@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("full", "full@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("abundant", "abundant@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "en"}),
            ("system", "system@test.ro", {"is_active": True, "email_filling_fast_enabled": True, "language_preference": "system"}),
        ]
    }
    db_session.add_all([organizer, hidden_tag, *events.values(), *users.values()])
    db_session.commit()
    favorites = [
        ("inactive", "limit_first"),
        ("disabled", "limit_first"),
        ("limited", "limit_first"),
        ("limited", "limit_second"),
        ("blocked", "blocked"),
        ("hidden", "hidden"),
        ("full", "full"),
        ("abundant", "abundant"),
        ("system", "system"),
    ]
    db_session.add_all(
        models.FavoriteEvent(user_id=int(users[user_name].id), event_id=int(events[event_name].id))
        for user_name, event_name in favorites
    )
    db_session.add(models.Registration(user_id=int(users["full"].id), event_id=int(events["full"].id)))
    db_session.commit()
    return SimpleNamespace(organizer=organizer, hidden_tag=hidden_tag, users=users, events=events)


def patch_filling_fast_alerts(monkeypatch, setup, *, enqueued, langs) -> None:
    def _exclusions(*, user_id: int, **_kwargs):
        if int(user_id) == int(setup.users["blocked"].id):
            return set(), {int(setup.organizer.id)}
        if int(user_id) == int(setup.users["hidden"].id):
            return {int(setup.hidden_tag.id)}, set()
        return set(), set()

    monkeypatch.setattr(task_queue, "_load_personalization_exclusions", _exclusions)
    monkeypatch.setattr(task_queue, "enqueue_job", lambda _db, _jt, payload: enqueued.append(payload))

    import app.email_templates as tpl

    monkeypatch.setattr(
        tpl,
        "render_filling_fast_email",
        lambda user, event, *, available_seats, lang: langs.append((user.email, lang, available_seats, event.title)) or ("sub", "txt", "html"),
    )


def seed_guardrail_window_rows(db_session, *, user_id: int, event_id: int, now: datetime) -> None:
    db_session.add_all(
        [
            interaction(user_id=user_id, event_id=event_id, kind="impression", occurred_at=now, meta={"source": "events_list", "sort": "recommended"}),
            interaction(user_id=user_id, event_id=event_id, kind="impression", occurred_at=now, meta={"source": "events_list", "sort": "time"}),
            interaction(user_id=user_id, event_id=event_id, kind="click", occurred_at=now + timedelta(minutes=1), meta={"source": "other", "sort": "recommended"}),
            interaction(user_id=user_id, event_id=event_id, kind="click", occurred_at=now + timedelta(minutes=2), meta={"source": "events_list", "sort": "recommended"}),
            interaction(user_id=user_id, event_id=event_id, kind="register", occurred_at=now + timedelta(hours=5)),
        ]
    )
    db_session.commit()


def seed_guardrail_rollback_state(db_session, *, user_id: int, event_id: int, now: datetime):
    add_balanced_guardrail_rows(db_session, user_id=user_id, event_id=event_id, now=now)
    db_session.add(
        interaction(
            user_id=user_id,
            event_id=event_id,
            kind="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": "recommended"},
        )
    )
    previous = models.RecommenderModel(model_version="model-prev", feature_names=["bias"], weights=[0.0], meta={}, is_active=False)
    active = models.RecommenderModel(model_version="model-active", feature_names=["bias"], weights=[0.1], meta={}, is_active=True)
    db_session.add_all([previous, active])
    db_session.commit()
    return previous, active


class ChainQuery:
    def __init__(self, *, rows=None, first_result=None, subquery_result=None):
        self._rows = rows if rows is not None else []
        self._first_result = first_result
        self._subquery_result = subquery_result

    def filter(self, *_args, **_kwargs):
        return self

    def group_by(self, *_args, **_kwargs):
        return self

    def select_from(self, *_args, **_kwargs):
        return self

    def join(self, *_args, **_kwargs):
        return self

    def outerjoin(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def subquery(self):
        return self._subquery_result

    def all(self):
        return self._rows

    def first(self):
        return self._first_result


class FakeFillingFastDb:
    def __init__(self, *queries):
        self._queries = list(queries)

    def query(self, *_args, **_kwargs):
        return self._queries.pop(0)


def seed_guardrail_user_event(db_session):
    user = models.User(
        email="guardrail-branches@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
    )
    organizer = models.User(
        email="guardrail-org@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    event = models.Event(
        title="Guardrail Event",
        description="desc",
        category="Edu",
        start_time=datetime.now(timezone.utc) + timedelta(days=2),
        city="Cluj",
        location="Hall",
        max_seats=20,
        owner=organizer,
        status="published",
    )
    db_session.add_all([user, organizer, event])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(event)
    return user, event
