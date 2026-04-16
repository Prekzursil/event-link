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
    _make_user,
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
    reason_for = getattr(module, "_reason_for")
    assert (
        reason_for(user=user, event=event, lang="en")
        == "Your interests: python"
    )
    assert reason_for(user=user, event=other_event, lang="ro") == "În apropiere"
    assert module._impression_negative_weight(None) == pytest.approx(0.05)
    assert module._impression_negative_weight(1) == pytest.approx(0.25)
    assert module._impression_negative_weight(4) == pytest.approx(0.15)
    assert module._impression_negative_weight(9) == pytest.approx(0.1)
    assert module._impression_negative_weight(25) == pytest.approx(0.05)


def test_selected_model_row_falls_back_when_requested_version_is_missing(
    db_session,
) -> None:
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


def test_main_handles_missing_database_and_empty_inputs(
    monkeypatch, db_session, capsys
) -> None:
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
    assert (
        _run_main(
            module,
            monkeypatch,
            "--skip-training",
            "--dry-run",
            "--user-id",
            str(student.id),
        )
        == 0
    )
    assert "using persisted model_version=bad-features" in capsys.readouterr().out

    monkeypatch.delenv("RECOMMENDER_MODEL_VERSION", raising=False)
    assert (
        _run_main(module, monkeypatch, "--skip-training", "--user-id", str(student.id))
        == 0
    )
    capsys.readouterr()
    recommendations = (
        db_session.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == int(student.id))
        .all()
    )
    assert recommendations
    assert any(rec.event_id == int(event_candidate.id) for rec in recommendations)


def test_main_skip_training_returns_zero_when_loader_yields_empty_state(
    monkeypatch, db_session
) -> None:
    """Exercises main skip training returns zero when loader yields empty state."""
    module = _load_script_module()
    student, _event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    def _load_empty_model_state(**_kwargs):
        """Returns an empty persisted-model state for the test."""
        return (None, None, None)

    monkeypatch.setattr(module, "_load_persisted_model_state", _load_empty_model_state)

    assert (
        _run_main(module, monkeypatch, "--skip-training", "--user-id", str(student.id))
        == 0
    )

    recommendations = (
        db_session.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == int(student.id))
        .all()
    )
    assert recommendations == []


def test_main_training_paths_cover_no_examples_dry_run_and_write(
    monkeypatch, db_session, capsys
) -> None:
    """Exercises main training paths cover no examples dry run and write."""
    module = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    organizer = _make_user(
        email="org-no-data@test.ro", role=models.UserRole.organizator
    )
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

    assert (
        _run_main(
            module,
            monkeypatch,
            "--dry-run",
            "--user-id",
            str(student.id),
            "--top-n",
            "2",
        )
        == 0
    )
    dry_run_output = capsys.readouterr().out
    assert "[eval] hitrate@10=" in dry_run_output
    assert "dry-run enabled" in dry_run_output

    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "requested-v1")
    assert (
        _run_main(module, monkeypatch, "--user-id", str(student.id), "--top-n", "2")
        == 0
    )
    write_output = capsys.readouterr().out
    assert "stored" in write_output
    model = (
        db_session.query(models.RecommenderModel)
        .filter(models.RecommenderModel.model_version == "requested-v1")
        .first()
    )
    assert model is not None and model.is_active is True
    recommendations = (
        db_session.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == int(student.id))
        .all()
    )
    assert recommendations
    assert any(rec.event_id == int(event_candidate.id) for rec in recommendations)


def _empty_user_features(
    module, *, city: str | None = None, city_weights: dict[str, float] | None = None
):
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


# pylint: disable-next=too-many-arguments
def _basic_event_features(
    module,
    now: datetime,
    *,
    city: str,
    owner_id: int,
    days: int,
    category: str | None = None,
):
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
    same_city_event = _basic_event_features(
        module, now, city="cluj", owner_id=1, days=2
    )
    weighted_city_event = _basic_event_features(
        module, now, city="iasi", owner_id=2, days=3
    )
    generic_event = _basic_event_features(
        module, now, city="timisoara", owner_id=3, days=4
    )
    reason_for = getattr(module, "_reason_for")
    assert (
        reason_for(user=same_city_user, event=same_city_event, lang="en")
        == "Near you"
    )
    assert (
        reason_for(user=weighted_city_user, event=weighted_city_event, lang="en")
        == "Near you"
    )
    assert (
        reason_for(user=generic_user, event=generic_event, lang="ro")
        == "Recomandat pentru tine"
    )


def test_evaluate_hitrate_sparse_positive_edge() -> None:
    """Exercises evaluate hitrate sparse positive edge."""
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    same_city_user = _empty_user_features(module, city="cluj")
    same_city_event = _basic_event_features(
        module, now, city="cluj", owner_id=1, days=2
    )
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


def test_main_training_warning_paths_continue_on_query_failures(
    monkeypatch, db_session, capsys
) -> None:
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
    monkeypatch.setattr(
        config_module.settings, "recommendations_online_learning_max_score", 0
    )

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


def test_main_training_detects_feature_length_mismatch(
    monkeypatch, db_session, capsys
) -> None:
    """Exercises main training detects feature length mismatch."""
    module = _load_script_module()
    student, _event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    def _single_feature_vector(**_kwargs):
        """Returns a one-feature vector for mismatch validation."""
        return [1.0]

    monkeypatch.setattr(module, "_build_feature_vector", _single_feature_vector)

    assert (
        _run_main(module, monkeypatch, "--dry-run", "--user-id", str(student.id)) == 2
    )
    assert "feature vector length mismatch" in capsys.readouterr().out


def test_recompute_recommendations_ml_main_guard_raises_system_exit(
    monkeypatch,
) -> None:
    """Exercises recompute recommendations ml main guard raises system exit."""
    script_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "recompute_recommendations_ml.py"
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", [str(script_path)])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exc_info.value.code == 2
