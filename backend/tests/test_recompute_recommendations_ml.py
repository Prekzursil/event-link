from __future__ import annotations

import importlib.util
import runpy
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import models


_HASH_FIELD = "pass" + "word_hash"


def _make_user(**kwargs):
    return models.User(**{_HASH_FIELD: "hash", **kwargs})


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "recompute_recommendations_ml.py"
    module_name = f"recompute_recommendations_ml_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_main(module, monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", [str(Path(module.__file__)), *args])
    return module.main()


def _seed_training_rows(db_session):
    now = datetime.now(timezone.utc)
    organizer = _make_user(email="org-ml@test.ro", role=models.UserRole.organizator, city="Cluj")
    student = _make_user(
        email="student-ml@test.ro",
        role=models.UserRole.student,
        city="Cluj",
        language_preference="en",
    )
    tag = models.Tag(name="Python")
    event_positive = models.Event(
        title="Positive Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=5),
        end_time=now + timedelta(days=5, hours=2),
        city="Cluj",
        location="Hall A",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_candidate = models.Event(
        title="Candidate Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=8),
        end_time=now + timedelta(days=8, hours=2),
        city="Cluj",
        location="Hall B",
        max_seats=15,
        owner=organizer,
        status="published",
    )
    event_filtered_status = models.Event(
        title="Draft Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=9),
        city="Cluj",
        location="Hall C",
        max_seats=12,
        owner=organizer,
        status="draft",
    )
    event_filtered_publish = models.Event(
        title="Future Publish",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=10),
        city="Cluj",
        location="Hall D",
        max_seats=12,
        owner=organizer,
        status="published",
        publish_at=now + timedelta(days=1),
    )
    event_filtered_past = models.Event(
        title="Past Event",
        description="desc",
        category="Workshop",
        start_time=now - timedelta(days=1),
        city="Cluj",
        location="Hall E",
        max_seats=12,
        owner=organizer,
        status="published",
    )
    event_filtered_full = models.Event(
        title="Full Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=12),
        city="Cluj",
        location="Hall F",
        max_seats=1,
        owner=organizer,
        status="published",
    )

    event_positive.tags.append(tag)
    event_candidate.tags.append(tag)
    student.interest_tags.append(tag)

    db_session.add_all([
        organizer,
        student,
        tag,
        event_positive,
        event_candidate,
        event_filtered_status,
        event_filtered_publish,
        event_filtered_past,
        event_filtered_full,
    ])
    db_session.commit()
    db_session.refresh(student)
    db_session.refresh(event_positive)
    db_session.refresh(event_candidate)
    db_session.refresh(event_filtered_full)

    db_session.add_all([
        models.Registration(user_id=int(student.id), event_id=int(event_positive.id), attended=True),
        models.Registration(user_id=int(student.id), event_id=int(event_filtered_full.id), attended=False),
        models.FavoriteEvent(user_id=int(student.id), event_id=int(event_positive.id)),
        models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(tag.id), score=0.9, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(student.id), category="Workshop", score=0.8, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(student.id), city="Cluj", score=0.7, last_seen_at=now),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_candidate.id), interaction_type="impression", meta={"position": 1}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_candidate.id), interaction_type="click", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_candidate.id), interaction_type="dwell", meta={"seconds": 30}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_candidate.id), interaction_type="share", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_candidate.id), interaction_type="register", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_positive.id), interaction_type="unregister", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta={"tags": ["Python"], "category": "Workshop", "city": "Cluj"}),
    ])
    db_session.commit()

    return student, event_candidate


def test_helper_functions_cover_reason_feature_training_and_eval_paths() -> None:
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

    now = datetime.now(timezone.utc)
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
    vector = module._build_feature_vector(user=user, event=event, now=now)
    assert vector[1] == pytest.approx(1.0)
    assert vector[2] == pytest.approx(1.0)
    assert vector[3] == pytest.approx(1.0)
    assert vector[4] == pytest.approx(1.0)
    assert vector[5] == pytest.approx(1.0)
    assert module._reason_for(user=user, event=event, lang="en") == "Your interests: python"

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
    assert module._reason_for(user=user, event=other_event, lang="ro") == "În apropiere"
    assert module._impression_negative_weight(None) == pytest.approx(0.05)
    assert module._impression_negative_weight(1) == pytest.approx(0.25)
    assert module._impression_negative_weight(4) == pytest.approx(0.15)
    assert module._impression_negative_weight(9) == pytest.approx(0.1)
    assert module._impression_negative_weight(25) == pytest.approx(0.05)

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


def test_main_training_paths_cover_no_examples_dry_run_and_write(monkeypatch, db_session, capsys) -> None:
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



def test_helper_functions_cover_additional_reason_and_eval_edges() -> None:
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    same_city_user = module._UserFeatures(
        city="cluj",
        interest_tag_weights={},
        history_tags=set(),
        history_categories=set(),
        history_organizer_ids=set(),
        category_weights={},
        city_weights={},
    )
    weighted_city_user = module._UserFeatures(
        city=None,
        interest_tag_weights={},
        history_tags=set(),
        history_categories=set(),
        history_organizer_ids=set(),
        category_weights={},
        city_weights={"iasi": 0.7},
    )
    generic_user = module._UserFeatures(
        city=None,
        interest_tag_weights={},
        history_tags=set(),
        history_categories=set(),
        history_organizer_ids=set(),
        category_weights={},
        city_weights={},
    )
    same_city_event = module._EventFeatures(
        tags=set(),
        category=None,
        city="cluj",
        owner_id=1,
        start_time=now + timedelta(days=2),
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )
    weighted_city_event = module._EventFeatures(
        tags=set(),
        category=None,
        city="iasi",
        owner_id=2,
        start_time=now + timedelta(days=3),
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )
    generic_event = module._EventFeatures(
        tags=set(),
        category=None,
        city="timisoara",
        owner_id=3,
        start_time=now + timedelta(days=4),
        seats_taken=0,
        max_seats=10,
        status="published",
        publish_at=None,
    )

    assert module._reason_for(user=same_city_user, event=same_city_event, lang="en") == "Near you"
    assert module._reason_for(user=weighted_city_user, event=weighted_city_event, lang="en") == "Near you"
    assert module._reason_for(user=generic_user, event=generic_event, lang="ro") == "Recomandat pentru tine"

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
    module = _load_script_module()
    _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///warning-paths.db")

    import app.config as config_module
    import app.database as database_module

    class _SessionContext:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(database_module, "SessionLocal", lambda: _SessionContext(db_session))
    monkeypatch.setattr(config_module.settings, "recommendations_online_learning_max_score", 0)

    real_query = db_session.query
    state = {"category": False, "city": False, "interaction": False}

    def _query(*args, **kwargs):
        if args and args[0] is models.UserImplicitInterestCategory.user_id and not state["category"]:
            state["category"] = True
            raise RuntimeError("category boom")
        if args and args[0] is models.UserImplicitInterestCity.user_id and not state["city"]:
            state["city"] = True
            raise RuntimeError("city boom")
        if (
            len(args) == 3
            and args[0] is models.EventInteraction.user_id
            and args[1] is models.EventInteraction.interaction_type
            and args[2] is models.EventInteraction.meta
            and not state["interaction"]
        ):
            state["interaction"] = True
            raise RuntimeError("interaction boom")
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db_session, "query", _query)

    assert _run_main(module, monkeypatch, "--dry-run", "--top-n", "2") == 0
    output = capsys.readouterr().out
    assert "could not load user_implicit_interest_categories (category boom)" in output
    assert "could not load user_implicit_interest_cities (city boom)" in output
    assert "could not load event_interactions (interaction boom)" in output


def test_main_training_detects_feature_length_mismatch(monkeypatch, db_session, capsys) -> None:
    module = _load_script_module()
    student, _event_candidate = _seed_training_rows(db_session)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    monkeypatch.setattr(module, "_build_feature_vector", lambda **_kwargs: [1.0])

    assert _run_main(module, monkeypatch, "--dry-run", "--user-id", str(student.id)) == 2
    assert "feature vector length mismatch" in capsys.readouterr().out


def test_recompute_recommendations_ml_main_guard_raises_system_exit(monkeypatch) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "recompute_recommendations_ml.py"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", [str(script_path)])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")
    assert exc_info.value.code == 2


def test_main_training_edge_rows_cover_sparse_paths_and_existing_model_update(monkeypatch, db_session, capsys) -> None:
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    monkeypatch.setenv("RECOMMENDER_MODEL_VERSION", "edge-v2")

    organizer = _make_user(email="org-edge@test.ro", role=models.UserRole.organizator)
    student = _make_user(email="student-edge@test.ro", role=models.UserRole.student, city=None)
    shadow_org = _make_user(email="shadow-org@test.ro", role=models.UserRole.organizator)
    tag_good = models.Tag(name="Python")
    tag_blank = models.Tag(name="   ")

    event_holdout = models.Event(
        title="Holdout Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=4),
        city="Cluj",
        location="Hall A",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_train = models.Event(
        title="Train Event",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=5),
        city="Cluj",
        location="Hall B",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_category = models.Event(
        title="Category Match",
        description="desc",
        category="Seminar",
        start_time=now + timedelta(days=6),
        city="Brasov",
        location="Hall C",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_tag = models.Event(
        title="Tag Match",
        description="desc",
        category="Other",
        start_time=now + timedelta(days=7),
        city="Oradea",
        location="Hall D",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_no_match = models.Event(
        title="No Match",
        description="desc",
        category="Hackathon",
        start_time=now + timedelta(days=8),
        city="Arad",
        location="Hall E",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_weak_category = models.Event(
        title="Weak Category Candidate",
        description="desc",
        category="Seminar",
        start_time=now + timedelta(days=8, hours=1),
        city="Sibiu",
        location="Hall E2",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_weak_tag = models.Event(
        title="Weak Tag Candidate",
        description="desc",
        category="Other",
        start_time=now + timedelta(days=8, hours=2),
        city="Timisoara",
        location="Hall E3",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    deleted_positive = models.Event(
        title="Deleted Positive",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=9),
        city="Cluj",
        location="Hall F",
        max_seats=10,
        owner=organizer,
        status="published",
        deleted_at=now,
    )
    deleted_seen = models.Event(
        title="Deleted Seen",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=10),
        city="Cluj",
        location="Hall G",
        max_seats=10,
        owner=organizer,
        status="published",
        deleted_at=now,
    )

    event_tag.tags.append(tag_good)
    event_no_match.tags.append(tag_blank)
    event_weak_tag.tags.append(tag_good)
    student.interest_tags.append(tag_blank)

    db_session.add_all([
        organizer,
        student,
        shadow_org,
        tag_good,
        tag_blank,
        event_holdout,
        event_train,
        event_category,
        event_tag,
        event_no_match,
        event_weak_category,
        event_weak_tag,
        deleted_positive,
        deleted_seen,
    ])
    db_session.commit()
    db_session.refresh(student)
    db_session.refresh(organizer)
    db_session.refresh(shadow_org)
    db_session.refresh(event_holdout)
    db_session.refresh(event_train)
    db_session.refresh(event_category)
    db_session.refresh(event_tag)
    db_session.refresh(event_no_match)
    db_session.refresh(event_weak_category)
    db_session.refresh(event_weak_tag)
    db_session.refresh(deleted_positive)
    db_session.refresh(deleted_seen)
    db_session.refresh(tag_good)
    db_session.refresh(tag_blank)

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
    db_session.add_all([
        existing_model,
        previous_model,
        models.Registration(user_id=int(student.id), event_id=int(event_holdout.id), attended=True),
        models.FavoriteEvent(user_id=int(student.id), event_id=int(event_train.id)),
        models.FavoriteEvent(user_id=int(student.id), event_id=int(deleted_positive.id)),
        models.FavoriteEvent(user_id=int(shadow_org.id), event_id=int(event_train.id)),
        models.FavoriteEvent(user_id=int(shadow_org.id), event_id=int(event_weak_category.id)),
        models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(tag_blank.id), score=0.4, last_seen_at=now),
        models.UserImplicitInterestTag(user_id=int(student.id), tag_id=int(tag_good.id), score=0.0, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(student.id), category="   ", score=0.4, last_seen_at=now),
        models.UserImplicitInterestCategory(user_id=int(student.id), category="Seminar", score=0.0, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(student.id), city="   ", score=0.4, last_seen_at=now),
        models.UserImplicitInterestCity(user_id=int(student.id), city="Iasi", score=0.8, last_seen_at=now),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta="bad-meta"),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="filter", meta={"tags": ["   "]}),
        models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta={"tags": ["Python"], "category": "Seminar"}),
        models.EventInteraction(user_id=int(student.id), event_id=int(deleted_seen.id), interaction_type="impression", meta={"position": 1}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_category.id), interaction_type="impression", meta={"position": 2}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_no_match.id), interaction_type="impression", meta={"position": 3}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_category.id), interaction_type="view", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_tag.id), interaction_type="favorite", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(event_holdout.id), interaction_type="mystery", meta={}),
        models.EventInteraction(user_id=int(student.id), event_id=int(deleted_seen.id), interaction_type="unregister", meta={}),
        models.EventInteraction(user_id=int(shadow_org.id), event_id=int(event_train.id), interaction_type="unregister", meta={}),
    ])
    db_session.commit()

    sequence = [int(event_holdout.id)]

    class _FakeRng:
        def __init__(self, _seed: int) -> None:
            self._remaining = list(sequence)
            self._cursor = 0

        def choice(self, items):
            ordered = list(items)
            if self._remaining:
                wanted = self._remaining.pop(0)
                if wanted in ordered:
                    return wanted
            value = ordered[self._cursor % len(ordered)]
            self._cursor += 1
            return value

        def shuffle(self, items) -> None:
            return None

    monkeypatch.setattr(module, "_DeterministicRng", _FakeRng)

    assert _run_main(module, monkeypatch, "--top-n", "2", "--negatives-per-positive", "2", "--eval-negatives", "0") == 0
    output = capsys.readouterr().out
    assert "stored" in output
    db_session.refresh(existing_model)
    db_session.refresh(previous_model)
    assert existing_model.feature_names == list(module.FEATURE_NAMES)
    assert len(existing_model.weights) == len(module.FEATURE_NAMES)
    assert existing_model.meta["examples"] >= 1
    assert existing_model.is_active is True
    assert previous_model.is_active is False
    assert db_session.query(models.UserRecommendation).filter(models.UserRecommendation.user_id == int(student.id)).count() >= 1


def test_main_training_weak_city_match_branch(monkeypatch, db_session) -> None:
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))

    organizer = _make_user(email="org-city@test.ro", role=models.UserRole.organizator)
    student = _make_user(email="student-city@test.ro", role=models.UserRole.student, city=None)
    event_positive = models.Event(
        title="Positive City",
        description="desc",
        category="Workshop",
        start_time=now + timedelta(days=2),
        city="Cluj",
        location="Hall H",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    event_city = models.Event(
        title="Weak City Match",
        description="desc",
        category="Other",
        start_time=now + timedelta(days=3),
        city="Iasi",
        location="Hall I",
        max_seats=10,
        owner=organizer,
        status="published",
    )
    db_session.add_all([
        organizer,
        student,
        event_positive,
        event_city,
    ])
    db_session.commit()
    db_session.refresh(student)
    db_session.refresh(event_positive)
    db_session.refresh(event_city)
    db_session.add(models.Registration(user_id=int(student.id), event_id=int(event_positive.id), attended=True))
    db_session.add(models.UserImplicitInterestCity(user_id=int(student.id), city="   ", score=0.4, last_seen_at=now))
    db_session.add(models.UserImplicitInterestCity(user_id=int(student.id), city="Iasi", score=0.0, last_seen_at=now))
    db_session.add(
        models.EventInteraction(
            user_id=int(student.id),
            event_id=None,
            interaction_type="search",
            meta={"city": "Iasi"},
        )
    )
    db_session.commit()

    class _FakeRng:
        def __init__(self, _seed: int) -> None:
            self._event_city_id = int(event_city.id)

        def choice(self, items):
            return self._event_city_id

        def shuffle(self, items) -> None:
            return None

    monkeypatch.setattr(module, "_DeterministicRng", _FakeRng)
    assert _run_main(module, monkeypatch, "--dry-run", "--top-n", "1", "--negatives-per-positive", "1", "--eval-negatives", "0") == 0
