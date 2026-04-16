"""Tests for the ml v3 weighted signals behavior."""
import math
from datetime import datetime, timedelta, timezone

import pytest

from app import api as api_module, auth, models


def _set_setting(obj, name: str, value):  # noqa: ANN001
    """Sets the setting value."""
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def _weighted_learning_entities(db):
    """Implements the weighted learning entities helper."""
    organizer = models.User(
        email="org-weighted@test.ro",
        password_hash=auth.get_password_hash("organizer-fixture-A1"),
        role=models.UserRole.organizator,
    )
    tag = models.Tag(name="rock")
    event = models.Event(
        title="Rock Night",
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        owner=organizer,
        status="published",
        category="music",
        city="cluj",
    )
    event.tags.append(tag)
    db.add_all([organizer, tag, event])
    db.commit()
    db.refresh(event)
    return tag, event


def _seed_weighted_tag_score(db, *, student_id: int, tag_id: int) -> None:
    """Implements the seed weighted tag score helper."""
    now = datetime.now(timezone.utc)
    db.add(
        models.UserImplicitInterestTag(
            user_id=student_id,
            tag_id=tag_id,
            score=8.0,
            last_seen_at=now - timedelta(hours=2),
        )
    )
    db.commit()


def _with_weighted_learning_settings():
    """Returns an instance wrapped with weighted learning settings."""
    return {
        "recommendations_online_learning_enabled": True,
        "recommendations_online_learning_decay_half_life_hours": 1,
        "recommendations_online_learning_max_score": 10.0,
    }


def _post_weighted_learning_interaction(helpers):
    """Implements the post weighted learning interaction helper."""
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-weighted@test.ro")
    student = db.query(models.User).filter(models.User.email == "student-weighted@test.ro").first()
    assert student is not None
    tag, event = _weighted_learning_entities(db)
    _seed_weighted_tag_score(db, student_id=int(student.id), tag_id=int(tag.id))

    originals = {}
    try:
        for name, value in _with_weighted_learning_settings().items():
            originals[name] = _set_setting(api_module.settings, name, value)
        resp = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp.status_code == 204
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)
    return db, student, tag


def test_online_learning_updates_weighted_tag_category_city_with_decay(helpers):
    """Verifies online learning updates weighted tag category city with decay behavior."""
    db, student, tag = _post_weighted_learning_interaction(helpers)

    updated = (
        db.query(models.UserImplicitInterestTag)
        .filter(models.UserImplicitInterestTag.user_id == student.id, models.UserImplicitInterestTag.tag_id == tag.id)
        .one()
    )
    expected = 8.0 * math.exp(-math.log(2.0) * 2.0) + 1.0
    assert updated.score == pytest.approx(expected, abs=0.2)

    category_row = (
        db.query(models.UserImplicitInterestCategory)
        .filter(
            models.UserImplicitInterestCategory.user_id == student.id,
            models.UserImplicitInterestCategory.category == "music",
        )
        .one()
    )
    assert category_row.score == pytest.approx(1.0, abs=0.01)

    city_row = (
        db.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == student.id, models.UserImplicitInterestCity.city == "cluj")
        .one()
    )
    assert city_row.score == pytest.approx(1.0, abs=0.01)
