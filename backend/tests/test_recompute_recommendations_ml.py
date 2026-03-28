"""Coverage-closure tests for recommendation recomputation edge paths."""
from __future__ import annotations

import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models
from recompute_ml_test_helpers import (
    _build_helper_user_and_events,
    _load_script_module,
    _make_event,
    _make_user,
    _refresh_all,
    _run_main,
    _seed_training_rows,
    _warning_path_query_error,
)


def test_helper_rng_and_normalize_primitives() -> None:
    """Exercises helper rng and normalize primitives."""
    module = _load_script_module()
    rng_a = module._DeterministicRng(42)
    rng_b = module._DeterministicRng(42)

    seq_a = list(range(8))
    seq_b = list(range(8))
    rng_a.shuffle(seq_a)
    rng_b.shuffle(seq_b)

    assert seq_a == seq_b
    assert rng_a.choice(["a", "b", "c"]) == rng_b.choice(["a", "b", "c"])
    with pytest.raises(IndexError, match="empty sequence"):
        rng_a.choice([])
    with pytest.raises(ValueError, match="upper bound"):
        rng_b.randbelow(0)

    aware_now = datetime.now(timezone.utc)
    assert module._normalize_tag(" Python ") == "python"
    assert module._normalize_city(" Cluj ") == "cluj"
    assert module._normalize_city(None) is None
    assert module._normalize_category(" Workshop ") == "workshop"
    assert module._normalize_category(None) is None
    assert module._coerce_utc(aware_now) is aware_now


def test_helper_feature_vector_reason_and_impression_weights() -> None:
    """Exercises helper feature vector reason and impression weights."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    user, event, other_event = _build_helper_user_and_events(module, now)
    vector = module._build_feature_vector(user=user, event=event, now=now)
    assert vector[1] == pytest.approx(1.0)
    assert vector[2] == pytest.approx(1.0)
    assert vector[3] == pytest.approx(1.0)
    assert vector[4] == pytest.approx(1.0)
    assert vector[5] == pytest.approx(1.0)
    assert module._reason_for(user=user, event=event, lang="en") == "Your interests: python"
    assert module._reason_for(user=user, event=other_event, lang="ro") == "În apropiere"
    assert module._impression_negative_weight(None) == pytest.approx(0.05)
    assert module._impression_negative_weight(1) == pytest.approx(0.25)
    assert module._impression_negative_weight(4) == pytest.approx(0.15)
    assert module._impression_negative_weight(9) == pytest.approx(0.1)
    assert module._impression_negative_weight(25) == pytest.approx(0.05)


def test_selected_model_row_falls_back_when_requested_version_is_missing(db_session) -> None:
    """Exercises selected model row falls back when requested version is missing."""
    module = _load_script_module()
    active_model = models.RecommenderModel(
        model_version="active-v1",
        feature_names=["bias"],
        weights=[1.0],
        is_active=True,
    )
    older_model = models.RecommenderModel(
        model_version="older-v0",
        feature_names=["bias"],
        weights=[0.5],
        is_active=False,
    )
    db_session.add_all([active_model, older_model])
    db_session.commit()

    selected = module._selected_model_row(
        db=db_session,
        models=models,
        requested_model_version="missing-v9",
    )

    assert selected is not None
    assert selected.model_version == "active-v1"


def test_event_id_for_features_raises_when_candidate_is_missing() -> None:
    """Exercises event id for features raises when candidate is missing."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    _user, candidate_event, other_event = _build_helper_user_and_events(module, now)

    with pytest.raises(KeyError, match="candidate event not found"):
        module._event_id_for_features({2: other_event}, candidate_event)


def test_helper_train_and_eval_hitrate_smoke() -> None:
    """Exercises helper train and eval hitrate smoke."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    user, event, other_event = _build_helper_user_and_events(module, now)
    weights = module._train_log_regression_sgd(
        examples=[([1.0, 0.0], 1, 1.0), ([0.0, 1.0], 0, 1.0)],
        n_features=2,
        epochs=2,
        lr=0.2,
        l2=0.01,
        seed=9,
    )
    assert len(weights) == 2
    hitrate = module._evaluate_hitrate_at_k(
        weights=[0.9, 0.1],
        users={1: user},
        events={10: event, 11: other_event},
        positives_holdout={1: 10},
        all_event_ids=[10, 11],
        now=now,
        k=1,
        negatives_per_user=1,
        seed=11,
    )
    assert 0.0 <= hitrate <= 1.0


def test_main_handles_missing_database_and_empty_inputs(monkeypatch, db_session, capsys) -> None:
    """Exercises main handles missing database and empty inputs."""
    module = _load_script_module()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _run_main(module, monkeypatch, "--dry-run") == 2
    assert "Missing DATABASE_URL" in capsys.readouterr().out

    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    assert _run_main(module, monkeypatch, "--dry-run") == 0
    assert "No student users found" in capsys.readouterr().out

    student = _make_user(email="student-empty@test.ro", role=models.UserRole.student)
    db_session.add(student)
    db_session.commit()

    assert _run_main(module, monkeypatch, "--dry-run") == 0
    assert "No events found" in capsys.readouterr().out


def test_main_skip_training_paths(monkeypatch, db_session, capsys) -> None:
    """Exercises main skip training paths."""
    module = _load_script_module()
    student, event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    assert _run_main(module, monkeypatch, "--skip-training") == 0
    assert "no persisted recommender model found" in capsys.readouterr().out

    bad_model = models.RecommenderModel(
        model_version="bad-features",
        feature_names=["wrong"],
        weights=[1.0],
        is_active=True,
    )
    db_session.add(bad_model)
    db_session.commit()
    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "bad-features")
    assert _run_main(module, monkeypatch, "--skip-training") == 2
    assert "feature_names mismatch" in capsys.readouterr().out

    bad_model.feature_names = list(module.FEATURE_NAMES)
    bad_model.weights = [1.0]
    db_session.add(bad_model)
    db_session.commit()
    assert _run_main(module, monkeypatch, "--skip-training") == 2
    assert "weights length mismatch" in capsys.readouterr().out

    bad_model.weights = [0.1] * len(module.FEATURE_NAMES)
    db_session.add(bad_model)
    db_session.commit()
    assert _run_main(module, monkeypatch, "--skip-training", "--dry-run", "--user-id", str(student.id)) == 0
    assert "using persisted model_version=bad-features" in capsys.readouterr().out

    monkeypatch.delenv("RECOMMENDER_MODEL_VERSION", raising=False)
    assert _run_main(module, monkeypatch, "--skip-training", "--user-id", str(student.id)) == 0
    capsys.readouterr()
    recommendations = db_session.query(models.UserRecommendation).filter(models.UserRecommendation.user_id == int(student.id)).all()
    assert recommendations
    assert any(rec.event_id == int(event_candidate.id) for rec in recommendations)


def test_main_skip_training_returns_zero_when_loader_yields_empty_state(monkeypatch, db_session) -> None:
    """Exercises main skip training returns zero when loader yields empty state."""
    module = _load_script_module()
    student, _event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    def _load_empty_model_state(**_kwargs):
        """Returns an empty persisted-model state for the test."""
        return (None, None, None)

    monkeypatch.setattr(module, "_load_persisted_model_state", _load_empty_model_state)

    assert _run_main(module, monkeypatch, "--skip-training", "--user-id", str(student.id)) == 0

    recommendations = (
        db_session.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == int(student.id))
        .all()
    )
    assert recommendations == []


def test_main_training_paths_cover_no_examples_dry_run_and_write(monkeypatch, db_session, capsys) -> None:
    """Exercises main training paths cover no examples dry run and write."""
    module = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    organizer = _make_user(email="org-no-data@test.ro", role=models.UserRole.organizator)
    student = _make_user(email="student-no-data@test.ro", role=models.UserRole.student)
    event = models.Event(
        title="No Data Event",
        description="desc",
        category="Workshop",
        start_time=datetime.now(timezone.utc) + timedelta(days=4),
        city="Cluj",
        location="Hall",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    db_session.add_all([organizer, student, event])
    db_session.commit()

    assert _run_main(module, monkeypatch, "--dry-run") == 0
    assert "No training data found" in capsys.readouterr().out

    db_session.query(models.UserRecommendation).delete()
    db_session.query(models.RecommenderModel).delete()
    db_session.query(models.EventInteraction).delete()
    db_session.query(models.Registration).delete()
    db_session.query(models.FavoriteEvent).delete()
    db_session.query(models.UserImplicitInterestTag).delete()
    db_session.query(models.UserImplicitInterestCategory).delete()
    db_session.query(models.UserImplicitInterestCity).delete()
    db_session.query(models.Event).delete()
    db_session.query(models.Tag).delete()
    db_session.query(models.User).delete()
    db_session.commit()

    student, event_candidate = _seed_training_rows(db_session)

    assert _run_main(module, monkeypatch, "--dry-run", "--user-id", str(student.id), "--top-n", "2") == 0
    dry_run_output = capsys.readouterr().out
    assert "[eval] hitrate@10=" in dry_run_output
    assert "dry-run enabled" in dry_run_output

    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "requested-v1")
    assert _run_main(module, monkeypatch, "--user-id", str(student.id), "--top-n", "2") == 0
    write_output = capsys.readouterr().out
    assert "stored" in write_output
    model = db_session.query(models.RecommenderModel).filter(models.RecommenderModel.model_version == "requested-v1").first()
    assert model is not None and model.is_active is True
    recommendations = db_session.query(models.UserRecommendation).filter(models.UserRecommendation.user_id == int(student.id)).all()
    assert recommendations
    assert any(rec.event_id == int(event_candidate.id) for rec in recommendations)



def _empty_user_features(module, *, city: str | None = None, city_weights: dict[str, float] | None = None):
    """Builds the empty user features fixture."""
    return module._UserFeatures(
        city=city,
        interest_tag_weights={},
        history_tags=set(),
        history_categories=set(),
        history_organizer_ids=set(),
        category_weights={},
        city_weights=city_weights or {},
    )


def _basic_event_features(module, now: datetime, *, city: str, owner_id: int, days: int, category: str | None = None):
    """Builds the basic event features fixture."""
    return module._EventFeatures(
        tags=set(),
        category=category,
        city=city,
        owner_id=owner_id,
        start_time=now + timedelta(days=days),
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )


def test_reason_for_city_and_generic_fallback_edges() -> None:
    """Exercises reason for city and generic fallback edges."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    same_city_user = _empty_user_features(module, city="cluj")
    weighted_city_user = _empty_user_features(module, city_weights={"iasi": 0.7})
    generic_user = _empty_user_features(module)
    same_city_event = _basic_event_features(module, now, city="cluj", owner_id=1, days=2)
    weighted_city_event = _basic_event_features(module, now, city="iasi", owner_id=2, days=3)
    generic_event = _basic_event_features(module, now, city="timisoara", owner_id=3, days=4)
    assert module._reason_for(user=same_city_user, event=same_city_event, lang="en") == "Near you"
    assert module._reason_for(user=weighted_city_user, event=weighted_city_event, lang="en") == "Near you"
    assert module._reason_for(user=generic_user, event=generic_event, lang="ro") == "Recomandat pentru tine"


def test_evaluate_hitrate_sparse_positive_edge() -> None:
    """Exercises evaluate hitrate sparse positive edge."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    same_city_user = _empty_user_features(module, city="cluj")
    same_city_event = _basic_event_features(module, now, city="cluj", owner_id=1, days=2)
    hitrate = module._evaluate_hitrate_at_k(
        weights=[0.0] * len(module.FEATURE_NAMES),
        users={1: same_city_user},
        events={10: same_city_event},
        positives_holdout={1: 10, 2: 20},
        all_event_ids=[99],
        now=now,
        k=1,
        negatives_per_user=1,
        seed=7,
    )
    assert hitrate == pytest.approx(1.0)


def test_main_training_warning_paths_continue_on_query_failures(monkeypatch, db_session, capsys) -> None:
    """Exercises main training warning paths continue on query failures."""
    module = _load_script_module()
    _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///warning-paths.db")

    import app.config as config_module
    import app.database as database_module

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

    def _session_local():
        """Builds the fake session-local context factory."""
        return _SessionContext(db_session)

    monkeypatch.setattr(database_module, "SessionLocal", _session_local)
    monkeypatch.setattr(config_module.settings, "recommendations_online_learning_max_score", 0)

    real_query = db_session.query
    state = {"category": False, "city": False, "interaction": False}

    def _query(*args, **kwargs):
        """Builds the query helper used by the test."""
        if message := _warning_path_query_error(args, state):
            raise RuntimeError(message)
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db_session, "query", _query)

    assert _run_main(module, monkeypatch, "--dry-run", "--top-n", "2") == 0
    output = capsys.readouterr().out
    assert "could not load user_implicit_interest_categories (category boom)" in output
    assert "could not load user_implicit_interest_cities (city boom)" in output
    assert "could not load event_interactions (interaction boom)" in output


def test_main_training_detects_feature_length_mismatch(monkeypatch, db_session, capsys) -> None:
    """Exercises main training detects feature length mismatch."""
    module = _load_script_module()
    student, _event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    def _single_feature_vector(**_kwargs):
        """Returns a one-feature vector for mismatch validation."""
        return [1.0]

    monkeypatch.setattr(module, "_build_feature_vector", _single_feature_vector)

    assert _run_main(module, monkeypatch, "--dry-run", "--user-id", str(student.id)) == 2
    assert "feature vector length mismatch" in capsys.readouterr().out


def test_recompute_recommendations_ml_main_guard_raises_system_exit(monkeypatch) -> None:
    """Exercises recompute recommendations ml main guard raises system exit."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "recompute_recommendations_ml.py"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", [str(script_path)])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exc_info.value.code == 2


def _build_edge_training_entities(now: datetime):
    """Builds the edge training entities fixture data."""
    organizer = _make_user(email="org-edge@test.ro", role=models.UserRole.organizator)
    student = _make_user(email="student-edge@test.ro", role=models.UserRole.student, city=None)
    shadow_org = _make_user(email="shadow-org@test.ro", role=models.UserRole.organizator)
    tag_good = models.Tag(name="Python")
    tag_blank = models.Tag(name="   ")
    events = {
        "holdout": _make_event(owner=organizer, title="Holdout Event", now=now, days=4, location="Hall A"),
        "train": _make_event(owner=organizer, title="Train Event", now=now, days=5, location="Hall B"),
        "category": _make_event(owner=organizer, title="Category Match", now=now, days=6, category="Seminar", city="Brasov", location="Hall C"),
        "tag": _make_event(owner=organizer, title="Tag Match", now=now, days=7, category="Other", city="Oradea", location="Hall D"),
        "no_match": _make_event(owner=organizer, title="No Match", now=now, days=8, category="Hackathon", city="Arad", location="Hall E"),
        "weak_category": _make_event(owner=organizer, title="Weak Category Candidate", now=now, days=8, hours=1, category="Seminar", city="Sibiu", location="Hall E2"),
        "weak_tag": _make_event(owner=organizer, title="Weak Tag Candidate", now=now, days=8, hours=2, category="Other", city="Timisoara", location="Hall E3"),
        "deleted_positive": _make_event(owner=organizer, title="Deleted Positive", now=now, days=9, location="Hall F", deleted_at=now),
        "deleted_seen": _make_event(owner=organizer, title="Deleted Seen", now=now, days=10, location="Hall G", deleted_at=now),
    }
    return {"organizer": organizer, "student": student, "shadow_org": shadow_org, "tag_good": tag_good, "tag_blank": tag_blank, **events}


def _persist_edge_training_entities(db_session, fixture) -> None:
    """Persists the edge training entities fixture rows."""
    fixture["tag"].tags.append(fixture["tag_good"])
    fixture["no_match"].tags.append(fixture["tag_blank"])
    fixture["weak_tag"].tags.append(fixture["tag_good"])
    fixture["student"].interest_tags.append(fixture["tag_blank"])
    db_session.add_all([fixture["organizer"], fixture["student"], fixture["shadow_org"], fixture["tag_good"], fixture["tag_blank"], fixture["holdout"], fixture["train"], fixture["category"], fixture["tag"], fixture["no_match"], fixture["weak_category"], fixture["weak_tag"], fixture["deleted_positive"], fixture["deleted_seen"]])
    db_session.commit()
    _refresh_all(db_session, fixture["student"], fixture["organizer"], fixture["shadow_org"], fixture["holdout"], fixture["train"], fixture["category"], fixture["tag"], fixture["no_match"], fixture["weak_category"], fixture["weak_tag"], fixture["deleted_positive"], fixture["deleted_seen"], fixture["tag_good"], fixture["tag_blank"])


def _seed_edge_training_rows(db_session, fixture, now: datetime):
    """Seeds the edge training rows fixture rows."""
    existing_model = models.RecommenderModel(model_version="edge-v2", feature_names=["stale"], weights=[99.0], meta={"stale": True}, is_active=True)
    previous_model = models.RecommenderModel(model_version="edge-v1", feature_names=["bias"], weights=[0.0], meta={}, is_active=False)
    rows = [
        models.Registration(user_id=int(fixture["student"].id), event_id=int(fixture["holdout"].id), attended=True),
        models.FavoriteEvent(user_id=int(fixture["student"].id), event_id=int(fixture["train"].id)),
        models.FavoriteEvent(user_id=int(fixture["student"].id), event_id=int(fixture["deleted_positive"].id)),
        models.FavoriteEvent(user_id=int(fixture["shadow_org"].id), event_id=int(fixture["train"].id)),
        models.FavoriteEvent(user_id=int(fixture["shadow_org"].id), event_id=int(fixture["weak_category"].id)),
        models.UserImplicitInterestTag(user_id=int(fixture["student"].id), tag_id=int(fixture["tag_blank"].id), score=0.4, last_seen_at=now),
        models.UserImplicitInterestTag(user_id=int(fixture["student"].id), tag_id=int(fixture["tag_good"].id), score=0.0, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(fixture["student"].id), category="   ", score=0.4, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(fixture["student"].id), category="Seminar", score=0.0, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(fixture["student"].id), city="   ", score=0.4, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(fixture["student"].id), city="Iasi", score=0.8, last_seen_at=now),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=None, interaction_type="search", meta="bad-meta"),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=None, interaction_type="filter", meta={"tags": ["   "]}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=None, interaction_type="search", meta={"tags": ["Python"], "category": "Seminar"}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["deleted_seen"].id), interaction_type="impression", meta={"position": 1}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["category"].id), interaction_type="impression", meta={"position": 2}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["no_match"].id), interaction_type="impression", meta={"position": 3}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["category"].id), interaction_type="view", meta={}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["tag"].id), interaction_type="favorite", meta={}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["holdout"].id), interaction_type="mystery", meta={}),
        models.EventInteraction(user_id=int(fixture["student"].id), event_id=int(fixture["deleted_seen"].id), interaction_type="unregister", meta={}),
        models.EventInteraction(user_id=int(fixture["shadow_org"].id), event_id=int(fixture["train"].id), interaction_type="unregister", meta={}),
    ]
    db_session.add_all([existing_model, previous_model, *rows])
    db_session.commit()
    return existing_model, previous_model


def _patch_rng_for_choices(monkeypatch, module, choices: list[int]) -> None:
    """Patches the rng for choices helper for the test."""
    class _FakeRng:
        """Test double for FakeRng."""
        def __init__(self, _seed: int) -> None:
            """Initializes the test double."""
            self._remaining = list(choices)
            self._cursor = 0

        def choice(self, items):
            """Returns the next deterministic choice."""
            ordered = list(items)
            if self._remaining:
                wanted = self._remaining.pop(0)
                if wanted in ordered:
                    return wanted
            value = ordered[self._cursor % len(ordered)]
            self._cursor += 1
            return value

        def shuffle(self, items) -> None:
            """Preserves deterministic ordering for the test."""
            return None

    monkeypatch.setattr(module, "_DeterministicRng", _FakeRng)


def _assert_edge_training_results(db_session, module, fixture, existing_model, previous_model) -> None:
    """Asserts the edge training results expectations."""
    db_session.refresh(existing_model)
    db_session.refresh(previous_model)
    assert existing_model.feature_names == list(module.FEATURE_NAMES)
    assert len(existing_model.weights) == len(module.FEATURE_NAMES)
    assert existing_model.meta["examples"] >= 1
    assert existing_model.is_active is True
    assert previous_model.is_active is False
    assert db_session.query(models.UserRecommendation).filter(models.UserRecommendation.user_id == int(fixture["student"].id)).count() >= 1


def test_main_training_edge_rows_cover_sparse_paths_and_existing_model_update(monkeypatch, db_session, capsys) -> None:
    """Exercises main training edge rows cover sparse paths and existing model update."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "edge-v2")
    fixture = _build_edge_training_entities(now)
    _persist_edge_training_entities(db_session, fixture)
    existing_model, previous_model = _seed_edge_training_rows(db_session, fixture, now)
    _patch_rng_for_choices(monkeypatch, module, [int(fixture["holdout"].id)])
    assert _run_main(module, monkeypatch, "--top-n", "2", "--negatives-per-positive", "2", "--eval-negatives", "0") == 0
    assert "stored" in capsys.readouterr().out
    _assert_edge_training_results(db_session, module, fixture, existing_model, previous_model)


def _seed_weak_city_fixture(db_session, now: datetime):
    """Seeds the weak city fixture fixture rows."""
    organizer = _make_user(email="org-city@test.ro", role=models.UserRole.organizator)
    student = _make_user(email="student-city@test.ro", role=models.UserRole.student, city=None)
    event_positive = _make_event(owner=organizer, title="Positive City", now=now, days=2, location="Hall H")
    event_city = _make_event(owner=organizer, title="Weak City Match", now=now, days=3, category="Other", city="Iasi", location="Hall I")
    db_session.add_all([organizer, student, event_positive, event_city])
    db_session.commit()
    _refresh_all(db_session, student, event_positive, event_city)
    db_session.add_all([
        models.Registration(user_id=int(student.id), event_id=int(event_positive.id), attended=True),
        models.UserImplicitInterestCity(user_id=int(student.id), city="   ", score=0.4, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(student.id), city="Iasi", score=0.0, last_seen_at=now),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta={"city": "Iasi"}),
    ])
    db_session.commit()
    return student, event_city


def test_main_training_weak_city_match_branch(monkeypatch, db_session) -> None:
    """Exercises main training weak city match branch."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    _student, event_city = _seed_weak_city_fixture(db_session, now)
    _patch_rng_for_choices(monkeypatch, module, [int(event_city.id)])
    assert _run_main(module, monkeypatch, "--dry-run", "--top-n", "1", "--negatives-per-positive", "1", "--eval-negatives", "0") == 0


def test_patch_rng_choices_falls_back_when_requested_choice_is_missing(monkeypatch) -> None:
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
        """Returns lower-scoring features for the positive event."""
        return [0.0] if event is pos_event else [1.0]

    monkeypatch.setattr(
        module,
        "_build_feature_vector",
        _miss_positive_feature_vector,
    )

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
