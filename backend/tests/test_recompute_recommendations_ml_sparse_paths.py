"""Focused sparse-path coverage for recommendation recomputation training."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import models
from recompute_ml_test_helpers import (
    _load_script_module,
    _make_event,
    _run_main,
    _seed_training_rows,
)


class _SessionContext:
    """Test double for SessionContext."""

    def __init__(self, session):
        """Initializes the test double."""
        self._session = session

    def __enter__(self):
        """Returns the wrapped context value."""
        return self._session

    def __exit__(self, exc_type, exc, tb):
        """Leaves exception propagation unchanged."""
        return False


class _InterceptQuery:
    """Test double for InterceptQuery."""

    def __init__(self, rows):
        """Initializes the test double."""
        self._rows = rows

    def join(self, *_args, **_kwargs):
        """Returns the fake query for chained joins."""
        return self

    def filter(self, *_args, **_kwargs):
        """Returns the fake query for chained filters."""
        return self

    def all(self):
        """Returns the intercepted rows."""
        return list(self._rows)


def _install_session_local(monkeypatch, db_session) -> None:
    """Installs a session-local factory that reuses the active db session."""
    import app.database as database_module

    def _session_local():
        """Builds the fake session-local context factory."""
        return _SessionContext(db_session)

    monkeypatch.setattr(database_module, "SessionLocal", _session_local)


def _install_sparse_query_interceptor(monkeypatch, db_session, student_id: int, future_seen: datetime) -> None:
    """Intercepts the implicit-tag query to inject the sparse-path fixture row."""
    real_query = db_session.query

    def _query(*args, **kwargs):
        """Builds the query helper used by the test."""
        is_implicit_tag_query = (
            len(args) == 4
            and args[0] is models.UserImplicitInterestTag.user_id
            and args[1] is models.Tag.name
            and args[2] is models.UserImplicitInterestTag.score
            and args[3] is models.UserImplicitInterestTag.last_seen_at
        )
        if is_implicit_tag_query:
            return _InterceptQuery([(student_id, "Python", 0.4, future_seen)])
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db_session, "query", _query)


def _seed_sparse_positive_rows(db_session, *, now: datetime):
    """Seeds the sparse-positive rows and returns the updated student/candidate context."""
    student, candidate = _seed_training_rows(db_session)
    organizer = candidate.owner
    assert organizer is not None

    no_category_positive = _make_event(
        owner=organizer,
        title="No Category Positive",
        now=now,
        days=6,
        category=None,
        city="Cluj",
        location="Hall C",
        end_hours=2,
    )
    db_session.add(no_category_positive)
    db_session.commit()
    db_session.refresh(no_category_positive)
    return student, candidate, no_category_positive


def _refresh_sparse_interest_rows(db_session, *, student_id: int, now: datetime) -> datetime:
    """Refreshes the implicit-interest rows so the non-decayed branch is exercised."""
    python_tag = db_session.query(models.Tag).filter(models.Tag.name == "Python").first()
    assert python_tag is not None
    future_seen = now + timedelta(hours=2)
    rows = (
        db_session.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == student_id,
            models.UserImplicitInterestTag.tag_id == int(python_tag.id),
        )
        .first(),
        db_session.query(models.UserImplicitInterestCategory)
        .filter(
            models.UserImplicitInterestCategory.user_id == student_id,
            models.UserImplicitInterestCategory.category == "Workshop",
        )
        .first(),
        db_session.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == student_id, models.UserImplicitInterestCity.city == "Cluj")
        .first(),
    )
    assert all(row is not None for row in rows)
    for row in rows:
        row.last_seen_at = future_seen
    return future_seen


def _add_sparse_interactions(db_session, *, student_id: int, candidate_id: int, positive_id: int) -> None:
    """Adds sparse search and dwell rows that exercise the guarded training paths."""
    db_session.add_all(
        [
            models.Registration(user_id=student_id, event_id=positive_id, attended=True),
            models.EventInteraction(
                user_id=student_id,
                event_id=None,
                interaction_type="search",
                meta={"tags": ["Python"], "category": "   ", "city": "   "},
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="impression", meta="bad-meta"
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="impression", meta={"position": "x"}
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="impression", meta={"position": 1}
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="impression", meta={"position": 2}
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="dwell", meta="bad-meta"
            ),
            models.EventInteraction(
                user_id=student_id, event_id=candidate_id, interaction_type="dwell", meta={"seconds": 0}
            ),
        ]
    )
    db_session.commit()


def test_main_training_covers_sparse_meta_and_nondecayed_paths(monkeypatch, db_session) -> None:
    """Exercises main training covers sparse meta and nondecayed paths."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    _install_session_local(monkeypatch, db_session)
    student, candidate, no_category_positive = _seed_sparse_positive_rows(db_session, now=now)
    future_seen = _refresh_sparse_interest_rows(db_session, student_id=int(student.id), now=now)
    _install_sparse_query_interceptor(monkeypatch, db_session, int(student.id), future_seen)
    _add_sparse_interactions(
        db_session,
        student_id=int(student.id),
        candidate_id=int(candidate.id),
        positive_id=int(no_category_positive.id),
    )

    assert (
        _run_main(
            module,
            monkeypatch,
            "--dry-run",
            "--top-n",
            "2",
            "--eval-negatives",
            "0",
            "--user-id",
            str(student.id),
        )
        == 0
    )
