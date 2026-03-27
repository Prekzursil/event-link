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


def _make_event(
    owner,
    *,
    title: str,
    now: datetime,
    days: int,
    hours: int = 0,
    category: str = "Workshop",
    city: str = "Cluj",
    location: str = "Hall",
    max_seats: int = 10,
    status: str = "published",
    publish_at: datetime | None = None,
    deleted_at: datetime | None = None,
    end_hours: int | None = None,
):
    start_time = now + timedelta(days=days, hours=hours)
    payload = {
        "title": title,
        "description": "desc",
        "category": category,
        "start_time": start_time,
        "city": city,
        "location": location,
        "max_seats": max_seats,
        "owner": owner,
        "status": status,
    }
    if end_hours is not None:
        payload["end_time"] = start_time + timedelta(hours=end_hours)
    if publish_at is not None:
        payload["publish_at"] = publish_at
    if deleted_at is not None:
        payload["deleted_at"] = deleted_at
    return models.Event(**payload)


def _refresh_all(db_session, *instances) -> None:
    for instance in instances:
        db_session.refresh(instance)


def _build_seed_training_entities(now: datetime):
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
    events["positive"].tags.append(tag)
    events["candidate"].tags.append(tag)
    student.interest_tags.append(tag)
    db_session.add_all([organizer, student, tag, *events.values()])
    db_session.commit()
    _refresh_all(db_session, student, events["positive"], events["candidate"], events["filtered_full"])


def _build_seed_training_interactions(now: datetime, student, tag, events):
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
    now = datetime.now(timezone.utc)
    organizer, student, tag, events = _build_seed_training_entities(now)
    _persist_seed_training_entities(db_session, organizer, student, tag, events)
    db_session.add_all(_build_seed_training_interactions(now, student, tag, events))
    db_session.commit()
    return student, events["candidate"]


def _warning_path_query_error(args: tuple[object, ...], state: dict[str, bool]) -> str | None:
    if args and args[0] is models.UserImplicitInterestCategory.user_id and not state["category"]:
        state["category"] = True
        return "category boom"
    if args and args[0] is models.UserImplicitInterestCity.user_id and not state["city"]:
        state["city"] = True
        return "city boom"
    is_interaction_query = (
        len(args) == 3
        and args[0] is models.EventInteraction.user_id
        and args[1] is models.EventInteraction.interaction_type
        and args[2] is models.EventInteraction.meta
    )
    if is_interaction_query and not state["interaction"]:
        state["interaction"] = True
        return "interaction boom"
    return None


def _build_helper_user_and_events(module, now: datetime):
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


def test_helper_rng_and_normalize_primitives() -> None:
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


def test_helper_train_and_eval_hitrate_smoke() -> None:
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



def _empty_user_features(module, *, city: str | None = None, city_weights: dict[str, float] | None = None):
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


def _build_edge_training_entities(now: datetime):
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
    fixture["tag"].tags.append(fixture["tag_good"])
    fixture["no_match"].tags.append(fixture["tag_blank"])
    fixture["weak_tag"].tags.append(fixture["tag_good"])
    fixture["student"].interest_tags.append(fixture["tag_blank"])
    db_session.add_all([fixture["organizer"], fixture["student"], fixture["shadow_org"], fixture["tag_good"], fixture["tag_blank"], fixture["holdout"], fixture["train"], fixture["category"], fixture["tag"], fixture["no_match"], fixture["weak_category"], fixture["weak_tag"], fixture["deleted_positive"], fixture["deleted_seen"]])
    db_session.commit()
    _refresh_all(db_session, fixture["student"], fixture["organizer"], fixture["shadow_org"], fixture["holdout"], fixture["train"], fixture["category"], fixture["tag"], fixture["no_match"], fixture["weak_category"], fixture["weak_tag"], fixture["deleted_positive"], fixture["deleted_seen"], fixture["tag_good"], fixture["tag_blank"])


def _seed_edge_training_rows(db_session, fixture, now: datetime):
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
    class _FakeRng:
        def __init__(self, _seed: int) -> None:
            self._remaining = list(choices)
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


def _assert_edge_training_results(db_session, module, fixture, existing_model, previous_model) -> None:
    db_session.refresh(existing_model)
    db_session.refresh(previous_model)
    assert existing_model.feature_names == list(module.FEATURE_NAMES)
    assert len(existing_model.weights) == len(module.FEATURE_NAMES)
    assert existing_model.meta["examples"] >= 1
    assert existing_model.is_active is True
    assert previous_model.is_active is False
    assert db_session.query(models.UserRecommendation).filter(models.UserRecommendation.user_id == int(fixture["student"].id)).count() >= 1


def test_main_training_edge_rows_cover_sparse_paths_and_existing_model_update(monkeypatch, db_session, capsys) -> None:
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
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    _student, event_city = _seed_weak_city_fixture(db_session, now)
    _patch_rng_for_choices(monkeypatch, module, [int(event_city.id)])
    assert _run_main(module, monkeypatch, "--dry-run", "--top-n", "1", "--negatives-per-positive", "1", "--eval-negatives", "0") == 0


def test_patch_rng_choices_falls_back_when_requested_choice_is_missing(monkeypatch) -> None:
    module = _load_script_module()
    _patch_rng_for_choices(monkeypatch, module, [999])
    rng = module._DeterministicRng(7)
    assert rng.choice([11, 22]) == 11
    assert rng.choice([11, 22]) == 22


def test_helper_feature_vector_handles_missing_city_and_start_time() -> None:
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
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    user, pos_event, neg_event = _build_helper_user_and_events(module, now)

    monkeypatch.setattr(
        module,
        "_build_feature_vector",
        lambda *, user, event, now: [0.0] if event is pos_event else [1.0],
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


def test_main_training_covers_sparse_meta_and_nondecayed_paths(monkeypatch, db_session) -> None:
    module = _load_script_module()
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("DATABASE_URL", str(db_session.bind.url))
    import app.database as database_module

    class _SessionContext:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(database_module, "SessionLocal", lambda: _SessionContext(db_session))
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

    python_tag = db_session.query(models.Tag).filter(models.Tag.name == "Python").first()
    assert python_tag is not None
    future_seen = now + timedelta(hours=2)
    existing_tag_row = (
        db_session.query(models.UserImplicitInterestTag)
        .filter(models.UserImplicitInterestTag.user_id == int(student.id), models.UserImplicitInterestTag.tag_id == int(python_tag.id))
        .first()
    )
    existing_category_row = (
        db_session.query(models.UserImplicitInterestCategory)
        .filter(models.UserImplicitInterestCategory.user_id == int(student.id), models.UserImplicitInterestCategory.category == "Workshop")
        .first()
    )
    existing_city_row = (
        db_session.query(models.UserImplicitInterestCity)
        .filter(models.UserImplicitInterestCity.user_id == int(student.id), models.UserImplicitInterestCity.city == "Cluj")
        .first()
    )
    assert existing_tag_row is not None
    assert existing_category_row is not None
    assert existing_city_row is not None
    existing_tag_row.last_seen_at = future_seen
    existing_category_row.last_seen_at = future_seen
    existing_city_row.last_seen_at = future_seen
    real_query = db_session.query

    class _InterceptQuery:
        def __init__(self, rows):
            self._rows = rows

        def join(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return list(self._rows)

    def _query(*args, **kwargs):
        is_implicit_tag_query = (
            len(args) == 4
            and args[0] is models.UserImplicitInterestTag.user_id
            and args[1] is models.Tag.name
            and args[2] is models.UserImplicitInterestTag.score
            and args[3] is models.UserImplicitInterestTag.last_seen_at
        )
        if is_implicit_tag_query:
            return _InterceptQuery([(int(student.id), "Python", 0.4, future_seen)])
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db_session, "query", _query)
    db_session.add_all(
        [
            models.Registration(user_id=int(student.id), event_id=int(no_category_positive.id), attended=True),
            models.EventInteraction(user_id=int(student.id), event_id=None, interaction_type="search", meta={"tags": ["Python"], "category": "   ", "city": "   "}),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="impression", meta="bad-meta"),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="impression", meta={"position": "x"}),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="impression", meta={"position": 1}),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="impression", meta={"position": 2}),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="dwell", meta="bad-meta"),
            models.EventInteraction(user_id=int(student.id), event_id=int(candidate.id), interaction_type="dwell", meta={"seconds": 0}),
        ]
    )
    db_session.commit()

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
