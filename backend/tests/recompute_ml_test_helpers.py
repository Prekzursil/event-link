"""Shared helpers for recommendation recomputation tests."""
from __future__ import annotations

import importlib.util
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import models


_HASH_FIELD = "pass" + "word_hash"


def _make_user(**kwargs):
    """Creates the user fixture value."""
    return models.User(**{_HASH_FIELD: "hash", **kwargs})


def _load_script_module():
    """Loads the script module helper resource."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "recompute_recommendations_ml.py"
    module_name = f"recompute_recommendations_ml_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ValueError("failed to load script module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_main(module, monkeypatch, *args: str) -> int:
    """Runs the main helper path for the test."""
    monkeypatch.setattr(sys, "argv", [str(Path(module.__file__)), *args])
    return module.main()


def _make_event(owner, *, title: str, now: datetime, days: int, **overrides):
    """Creates the event fixture value."""
    hours = int(overrides.pop("hours", 0))
    end_hours = overrides.pop("end_hours", None)
    start_time = now + timedelta(days=days, hours=hours)
    payload = {
        "title": title,
        "description": "desc",
        "category": "Workshop",
        "start_time": start_time,
        "city": "Cluj",
        "location": "Hall",
        "max_seats": 10,
        "owner": owner,
        "status": "published",
    }
    payload.update(overrides)
    if end_hours is not None:
        payload["end_time"] = start_time + timedelta(hours=int(end_hours))
    return models.Event(**payload)


def _refresh_all(db_session, *instances) -> None:
    """Refreshes the all fixture rows."""
    for instance in instances:
        db_session.refresh(instance)


def _build_seed_training_entities(now: datetime):
    """Builds the seed training entities fixture data."""
    organizer = _make_user(email="org-ml@test.ro", role=models.UserRole.organizator, city="Cluj")
    student = _make_user(
        email="student-ml@test.ro",
        role=models.UserRole.student,
        city="Cluj",
        language_preference="en",
    )
    tag = models.Tag(name="Python")
    events = {
        "positive": _make_event(owner=organizer, title="Positive Event", now=now, days=5, location="Hall A", end_hours=2),
        "candidate": _make_event(owner=organizer, title="Candidate Event", now=now, days=8, location="Hall B", max_seats=15, end_hours=2),
        "filtered_status": _make_event(owner=organizer, title="Draft Event", now=now, days=9, location="Hall C", max_seats=12, status="draft"),
        "filtered_publish": _make_event(owner=organizer, title="Future Publish", now=now, days=10, location="Hall D", max_seats=12, publish_at=now + timedelta(days=1)),
        "filtered_past": _make_event(owner=organizer, title="Past Event", now=now, days=-1, location="Hall E", max_seats=12),
        "filtered_full": _make_event(owner=organizer, title="Full Event", now=now, days=12, location="Hall F", max_seats=1),
    }
    return organizer, student, tag, events


def _persist_seed_training_entities(db_session, organizer, student, tag, events) -> None:
    """Persists the seed training entities fixture rows."""
    events["positive"].tags.append(tag)
    events["candidate"].tags.append(tag)
    student.interest_tags.append(tag)
    db_session.add_all([organizer, student, tag, *events.values()])
    db_session.commit()
    _refresh_all(db_session, student, events["positive"], events["candidate"], events["filtered_full"])


def _build_seed_training_interactions(now: datetime, student, tag, events):
    """Builds the seed training interactions fixture data."""
    return [
        models.Registration(user_id=int(student.id), event_id=int(events["positive"].id), attended=True),
        models.Registration(user_id=int(student.id), event_id=int(events["filtered_full"].id), attended=False),
        models.FavoriteEvent(user_id=int(student.id), event_id=int(events["positive"].id)),
        models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(tag.id), score=0.9, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(student.id), category="Workshop", score=0.8, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(student.id), city="Cluj", score=0.7, last_seen_at=now),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["candidate"].id), interaction_type="impression", meta={"position": 1}),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["candidate"].id), interaction_type="click", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["candidate"].id), interaction_type="dwell", meta={"seconds": 30}),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["candidate"].id), interaction_type="share", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["candidate"].id), interaction_type="register", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(events["positive"].id), interaction_type="unregister", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta={"tags": ["Python"], "category": "Workshop", "city": "Cluj"}),
    ]


def _seed_training_rows(db_session):
    """Seeds the training rows fixture rows."""
    now = datetime.now(timezone.utc)
    organizer, student, tag, events = _build_seed_training_entities(now)
    _persist_seed_training_entities(db_session, organizer, student, tag, events)
    db_session.add_all(_build_seed_training_interactions(now, student, tag, events))
    db_session.commit()
    return student, events["candidate"]


def _warning_path_query_error(args: tuple[object, ...], state: dict[str, bool]) -> str | None:
    """Returns the warning for path query error."""
    for column, key, message in (
        (models.UserImplicitInterestCategory.user_id, "category", "category boom"),
        (models.UserImplicitInterestCity.user_id, "city", "city boom"),
    ):
        if args and args[0] is column and not state[key]:
            state[key] = True
            return message

    if _is_interaction_warning_query(args) and not state["interaction"]:
        state["interaction"] = True
        return "interaction boom"
    return None


def _is_interaction_warning_query(args: tuple[object, ...]) -> bool:
    """Checks whether the intercepted query matches the interaction warning path."""
    return (
        len(args) == 3
        and args[0] is models.EventInteraction.user_id
        and args[1] is models.EventInteraction.interaction_type
        and args[2] is models.EventInteraction.meta
    )


def _build_helper_user_and_events(module, now: datetime):
    """Builds the helper user and events fixture data."""
    user = module._UserFeatures(
        city="cluj",
        interest_tag_weights={"python": 1.0},
        history_tags={"python"},
        history_categories={"workshop"},
        history_organizer_ids={7},
        category_weights={"seminar": 0.4},
        city_weights={"iasi": 0.6},
    )
    event = module._EventFeatures(
        tags={"python"},
        category="workshop",
        city="cluj",
        owner_id=7,
        start_time=now + timedelta(days=3),
        seats_taken=4,
        max_seats=10,
        status="published",
        publish_at=None,
    )
    other_event = module._EventFeatures(
        tags={"go"},
        category="seminar",
        city="iasi",
        owner_id=8,
        start_time=now + timedelta(days=4),
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )
    return user, event, other_event
