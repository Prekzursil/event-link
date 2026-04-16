"""Edge-case coverage for recommendation recomputation training."""

# Tests access private helpers of modules-under-test intentionally.
# pylint: disable=protected-access

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import models
from recompute_ml_test_helpers import (
    _build_helper_user_and_events,
    _load_script_module,
    _make_event,
    _make_user,
    _refresh_all,
    _run_main,
)


def _build_edge_training_entities(now: datetime):
    """Builds the edge training entities fixture data."""
    organizer = _make_user(email="org-edge@test.ro", role=models.UserRole.organizator)
    student = _make_user(
        email="student-edge@test.ro", role=models.UserRole.student, city=None
    )
    shadow_org = _make_user(
        email="shadow-org@test.ro", role=models.UserRole.organizator
    )
    tag_good = models.Tag(name="Python")
    tag_blank = models.Tag(name="   ")
    events = {
        "holdout": _make_event(
            owner=organizer, title="Holdout Event", now=now, days=4, location="Hall A"
        ),
        "train": _make_event(
            owner=organizer, title="Train Event", now=now, days=5, location="Hall B"
        ),
        "category": _make_event(
            owner=organizer,
            title="Category Match",
            now=now,
            days=6,
            category="Seminar",
            city="Brasov",
            location="Hall C",
        ),
        "tag": _make_event(
            owner=organizer,
            title="Tag Match",
            now=now,
            days=7,
            category="Other",
            city="Oradea",
            location="Hall D",
        ),
        "no_match": _make_event(
            owner=organizer,
            title="No Match",
            now=now,
            days=8,
            category="Hackathon",
            city="Arad",
            location="Hall E",
        ),
        "weak_category": _make_event(
            owner=organizer,
            title="Weak Category Candidate",
            now=now,
            days=8,
            hours=1,
            category="Seminar",
            city="Sibiu",
            location="Hall E2",
        ),
        "weak_tag": _make_event(
            owner=organizer,
            title="Weak Tag Candidate",
            now=now,
            days=8,
            hours=2,
            category="Other",
            city="Timisoara",
            location="Hall E3",
        ),
        "deleted_positive": _make_event(
            owner=organizer,
            title="Deleted Positive",
            now=now,
            days=9,
            location="Hall F",
            deleted_at=now,
        ),
        "deleted_seen": _make_event(
            owner=organizer,
            title="Deleted Seen",
            now=now,
            days=10,
            location="Hall G",
            deleted_at=now,
        ),
    }
    return {
        "organizer": organizer,
        "student": student,
        "shadow_org": shadow_org,
        "tag_good": tag_good,
        "tag_blank": tag_blank,
        **events,
    }


def _persist_edge_training_entities(db_session, fixture) -> None:
    """Persists the edge training entities fixture rows."""
    fixture["tag"].tags.append(fixture["tag_good"])
    fixture["no_match"].tags.append(fixture["tag_blank"])
    fixture["weak_tag"].tags.append(fixture["tag_good"])
    fixture["student"].interest_tags.append(fixture["tag_blank"])
    db_session.add_all(
        [
            fixture["organizer"],
            fixture["student"],
            fixture["shadow_org"],
            fixture["tag_good"],
            fixture["tag_blank"],
            fixture["holdout"],
            fixture["train"],
            fixture["category"],
            fixture["tag"],
            fixture["no_match"],
            fixture["weak_category"],
            fixture["weak_tag"],
            fixture["deleted_positive"],
            fixture["deleted_seen"],
        ]
    )
    db_session.commit()
    _refresh_all(
        db_session,
        fixture["student"],
        fixture["organizer"],
        fixture["shadow_org"],
        fixture["holdout"],
        fixture["train"],
        fixture["category"],
        fixture["tag"],
        fixture["no_match"],
        fixture["weak_category"],
        fixture["weak_tag"],
        fixture["deleted_positive"],
        fixture["deleted_seen"],
        fixture["tag_good"],
        fixture["tag_blank"],
    )


def _seed_edge_training_rows(db_session, fixture, now: datetime):
    """Seeds the edge training rows fixture rows."""
    existing_model = models.RecommenderModel(
        model_version="edge-v2",
        feature_names=["stale"],
        weights=[99.0],
        meta={"stale": True},
        is_active=True,
    )
    previous_model = models.RecommenderModel(
        model_version="edge-v1",
        feature_names=["bias"],
        weights=[0.0],
        meta={},
        is_active=False,
    )
    rows = [
        models.Registration(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["holdout"].id),
            attended=True,
        ),
        models.FavoriteEvent(
            user_id=int(fixture["student"].id), event_id=int(fixture["train"].id)
        ),
        models.FavoriteEvent(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["deleted_positive"].id),
        ),
        models.FavoriteEvent(
            user_id=int(fixture["shadow_org"].id), event_id=int(fixture["train"].id)
        ),
        models.FavoriteEvent(
            user_id=int(fixture["shadow_org"].id),
            event_id=int(fixture["weak_category"].id),
        ),
        models.UserImplicitInterestTag(
            user_id=int(fixture["student"].id),
            tag_id=int(fixture["tag_blank"].id),
            score=0.4,
            last_seen_at=now,
        ),
        models.UserImplicitInterestTag(
            user_id=int(fixture["student"].id),
            tag_id=int(fixture["tag_good"].id),
            score=0.0,
            last_seen_at=now,
        ),
        models.UserImplicitInterestCategory(
            user_id=int(fixture["student"].id),
            category="   ",
            score=0.4,
            last_seen_at=now,
        ),
        models.UserImplicitInterestCategory(
            user_id=int(fixture["student"].id),
            category="Seminar",
            score=0.0,
            last_seen_at=now,
        ),
        models.UserImplicitInterestCity(
            user_id=int(fixture["student"].id), city="   ", score=0.4, last_seen_at=now
        ),
        models.UserImplicitInterestCity(
            user_id=int(fixture["student"].id), city="Iasi", score=0.8, last_seen_at=now
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=None,
            interaction_type="search",
            meta="bad-meta",
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=None,
            interaction_type="filter",
            meta={"tags": ["   "]},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=None,
            interaction_type="search",
            meta={"tags": ["Python"], "category": "Seminar"},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["deleted_seen"].id),
            interaction_type="impression",
            meta={"position": 1},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["category"].id),
            interaction_type="impression",
            meta={"position": 2},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["no_match"].id),
            interaction_type="impression",
            meta={"position": 3},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["category"].id),
            interaction_type="view",
            meta={},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["tag"].id),
            interaction_type="favorite",
            meta={},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["holdout"].id),
            interaction_type="mystery",
            meta={},
        ),
        models.EventInteraction(
            user_id=int(fixture["student"].id),
            event_id=int(fixture["deleted_seen"].id),
            interaction_type="unregister",
            meta={},
        ),
        models.EventInteraction(
            user_id=int(fixture["shadow_org"].id),
            event_id=int(fixture["train"].id),
            interaction_type="unregister",
            meta={},
        ),
    ]
    db_session.add_all([existing_model, previous_model, *rows])
    db_session.commit()
    return existing_model, previous_model


def _patch_rng_for_choices(monkeypatch, module, choices: list[int]) -> None:
    """Patches the rng for choices helper for the test."""

    class _FakeRng:
        """Test double for FakeRng."""

        def __init__(self, _seed: int) -> None:
            """Initializes the instance state."""
            self._remaining = list(choices)
            self._cursor = 0

        def choice(self, items):
            """Implements the choice helper."""
            ordered = list(items)
            if self._remaining:
                wanted = self._remaining.pop(0)
                if wanted in ordered:
                    return wanted
            value = ordered[self._cursor % len(ordered)]
            self._cursor += 1
            return value

        @staticmethod
        def shuffle(items) -> None:  # noqa: S1186
            """No-op shuffle for deterministic tests."""

    monkeypatch.setattr(module, "_DeterministicRng", _FakeRng)


def _assert_edge_training_results(
    db_session, module, fixture, existing_model, previous_model
) -> None:
    """Asserts the edge training results expectations."""
    db_session.refresh(existing_model)
    db_session.refresh(previous_model)
    assert existing_model.feature_names == list(module.FEATURE_NAMES)
    assert len(existing_model.weights) == len(module.FEATURE_NAMES)
    assert existing_model.meta["examples"] >= 1
    assert existing_model.is_active is True
    assert previous_model.is_active is False
    count = (
        db_session.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == int(fixture["student"].id))
        .count()
    )
    assert count >= 1


def test_main_training_edge_rows_cover_sparse_paths_and_existing_model_update(
    monkeypatch, db_session, capsys
) -> None:
    """Exercises main training edge rows cover sparse paths and existing model update."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "edge-v2")
    fixture = _build_edge_training_entities(now)
    _persist_edge_training_entities(db_session, fixture)
    existing_model, previous_model = _seed_edge_training_rows(db_session, fixture, now)
    _patch_rng_for_choices(monkeypatch, module, [int(fixture["holdout"].id)])
    assert (
        _run_main(
            module,
            monkeypatch,
            "--top-n",
            "2",
            "--negatives-per-positive",
            "2",
            "--eval-negatives",
            "0",
        )
        == 0
    )
    assert "stored" in capsys.readouterr().out
    _assert_edge_training_results(
        db_session, module, fixture, existing_model, previous_model
    )


def _seed_weak_city_fixture(db_session, now: datetime):
    """Seeds the weak city fixture fixture rows."""
    organizer = _make_user(email="org-city@test.ro", role=models.UserRole.organizator)
    student = _make_user(
        email="student-city@test.ro", role=models.UserRole.student, city=None
    )
    event_positive = _make_event(
        owner=organizer, title="Positive City", now=now, days=2, location="Hall H"
    )
    event_city = _make_event(
        owner=organizer,
        title="Weak City Match",
        now=now,
        days=3,
        category="Other",
        city="Iasi",
        location="Hall I",
    )
    db_session.add_all([organizer, student, event_positive, event_city])
    db_session.commit()
    _refresh_all(db_session, student, event_positive, event_city)
    db_session.add_all(
        [
            models.Registration(
                user_id=int(student.id), event_id=int(event_positive.id), attended=True
            ),
            models.UserImplicitInterestCity(
                user_id=int(student.id), city="   ", score=0.4, last_seen_at=now
            ),
            models.UserImplicitInterestCity(
                user_id=int(student.id), city="Iasi", score=0.0, last_seen_at=now
            ),
            models.EventInteraction(
                user_id=int(student.id),
                event_id=None,
                interaction_type="search",
                meta={"city": "Iasi"},
            ),
        ]
    )
    db_session.commit()
    return student, event_city


def test_main_training_weak_city_match_branch(monkeypatch, db_session) -> None:
    """Exercises main training weak city match branch."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    _student, event_city = _seed_weak_city_fixture(db_session, now)
    _patch_rng_for_choices(monkeypatch, module, [int(event_city.id)])
    assert (
        _run_main(
            module,
            monkeypatch,
            "--dry-run",
            "--top-n",
            "1",
            "--negatives-per-positive",
            "1",
            "--eval-negatives",
            "0",
        )
        == 0
    )


def test_patch_rng_choices_falls_back_when_requested_choice_is_missing(
    monkeypatch,
) -> None:
    """Exercises patch rng choices falls back when requested choice is missing."""
    module = _load_script_module()
    _patch_rng_for_choices(monkeypatch, module, [999])
    rng = module._DeterministicRng(7)
    ordered = [11, 22]
    rng.shuffle(ordered)
    assert ordered == [11, 22]
    assert rng.choice([11, 22]) == 11
    assert rng.choice([11, 22]) == 22


def test_helper_feature_vector_handles_missing_city_and_start_time() -> None:
    """Exercises helper feature vector handles missing city and start time."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    user = module._UserFeatures(
        city=None,
        interest_tag_weights={},
        history_tags=set(),
        history_categories=set(),
        history_organizer_ids=set(),
        category_weights={"seminar": 0.3},
        city_weights={"iasi": 0.4},
    )
    event = module._EventFeatures(
        tags=set(),
        category="seminar",
        city=None,
        owner_id=9,
        start_time=None,
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )

    vector = module._build_feature_vector(user=user, event=event, now=now)
    assert vector[3] == pytest.approx(0.0)
    assert vector[4] == pytest.approx(0.3)
    assert vector[7] == pytest.approx(0.0)


def test_evaluate_hitrate_can_miss_positive(monkeypatch) -> None:
    """Exercises evaluate hitrate can miss positive."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    user, pos_event, neg_event = _build_helper_user_and_events(module, now)

    def _miss_positive_feature_vector(*, user, event, now):
        """Implements the miss positive feature vector helper."""
        return [0.0] if event is pos_event else [1.0]

    monkeypatch.setattr(module, "_build_feature_vector", _miss_positive_feature_vector)
    hitrate = module._evaluate_hitrate_at_k(
        weights=[1.0],
        users={1: user},
        events={10: pos_event, 11: neg_event},
        positives_holdout={1: 10},
        all_event_ids=[11],
        now=now,
        k=1,
        negatives_per_user=1,
        seed=1,
    )
    assert hitrate == pytest.approx(0.0)
