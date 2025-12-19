import math
from datetime import datetime, timedelta, timezone

import pytest

from app import api as api_module, auth, models


def _set_setting(obj, name: str, value):  # noqa: ANN001
    original = getattr(obj, name)
    setattr(obj, name, value)
    return original


def test_online_learning_updates_weighted_tag_category_city_with_decay(helpers):
    client = helpers["client"]
    db = helpers["db"]

    token = helpers["register_student"]("student-weighted@test.ro")
    student = db.query(models.User).filter(models.User.email == "student-weighted@test.ro").first()
    assert student is not None

    organizer = models.User(
        email="org-weighted@test.ro",
        password_hash=auth.get_password_hash("organizer123"),
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

    now = datetime.now(timezone.utc)
    db.add(
        models.UserImplicitInterestTag(
            user_id=int(student.id),
            tag_id=int(tag.id),
            score=8.0,
            last_seen_at=now - timedelta(hours=2),
        )
    )
    db.commit()

    originals = {}
    try:
        originals["recommendations_online_learning_enabled"] = _set_setting(
            api_module.settings, "recommendations_online_learning_enabled", True
        )
        originals["recommendations_online_learning_decay_half_life_hours"] = _set_setting(
            api_module.settings, "recommendations_online_learning_decay_half_life_hours", 1
        )
        originals["recommendations_online_learning_max_score"] = _set_setting(
            api_module.settings, "recommendations_online_learning_max_score", 10.0
        )

        resp = client.post(
            "/api/analytics/interactions",
            json={"events": [{"interaction_type": "click", "event_id": int(event.id)}]},
            headers=helpers["auth_header"](token),
        )
        assert resp.status_code == 204

        updated = (
            db.query(models.UserImplicitInterestTag)
            .filter(models.UserImplicitInterestTag.user_id == student.id, models.UserImplicitInterestTag.tag_id == tag.id)
            .one()
        )

        expected = 8.0 * math.exp(-math.log(2.0) * 2.0) + 1.0
        assert updated.score == pytest.approx(expected, abs=0.2)

        category_row = (
            db.query(models.UserImplicitInterestCategory)
            .filter(models.UserImplicitInterestCategory.user_id == student.id, models.UserImplicitInterestCategory.category == "music")
            .one()
        )
        assert category_row.score == pytest.approx(1.0, abs=0.01)

        city_row = (
            db.query(models.UserImplicitInterestCity)
            .filter(models.UserImplicitInterestCity.user_id == student.id, models.UserImplicitInterestCity.city == "cluj")
            .one()
        )
        assert city_row.score == pytest.approx(1.0, abs=0.01)
    finally:
        for name, value in originals.items():
            setattr(api_module.settings, name, value)

