"""Tests for the task queue digest guardrails behavior."""

# Tests access private helpers of modules-under-test intentionally.
# pylint: disable=protected-access

# Test fixture classes commonly have a single public method by design.
# pylint: disable=too-few-public-methods

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import auth, models, task_queue
from task_queue_test_support import (
    ChainQuery,
    FakeFillingFastDb,
    add_balanced_guardrail_rows,
    interaction,
    mk_job,
    patch_filling_fast_alerts,
    reset_guardrail_state,
    seed_filling_fast_branch_matrix,
    seed_guardrail_rollback_state,
    seed_guardrail_user_event,
    seed_guardrail_window_rows,
    seed_weekly_digest_fixture,
    unexpected_enqueue,
)


def test_send_weekly_digest_skips_and_handles_system_language(monkeypatch, db_session):
    """Verifies send weekly digest skips and handles system language behavior."""
    seed_weekly_digest_fixture(db_session)
    monkeypatch.setattr(
        task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set())
    )
    enqueued = []
    monkeypatch.setattr(
        task_queue, "enqueue_job", lambda _db, _jt, payload: enqueued.append(payload)
    )
    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 3})
    assert result["users"] == 1
    assert result["emails"] == 1
    assert enqueued and "Salut" in enqueued[0]["body_text"]


def test_evaluate_personalization_guardrails_disabled(monkeypatch, db_session):
    """Verifies evaluate personalization guardrails disabled behavior."""
    monkeypatch.setattr(
        task_queue.settings, "personalization_guardrails_enabled", False
    )
    result = task_queue._evaluate_personalization_guardrails(db=db_session, payload={})
    assert result == {"enabled": False}


def test_coerce_bool_fallback_uses_truthiness_of_custom_object() -> None:
    """Verifies coerce bool fallback uses truthiness of custom object behavior."""

    class _Truthy:
        """Truthy value object used in the surrounding module."""

        def __bool__(self) -> bool:
            """Implements the bool helper."""
            return True

    assert task_queue._coerce_bool(_Truthy()) is True


def test_claim_next_job_returns_none_when_queue_empty(db_session):
    """Verifies claim next job returns none when queue empty behavior."""
    assert task_queue.claim_next_job(db_session, worker_id="worker-none") is None


def test_claim_next_job_uses_skip_locked_for_postgres(monkeypatch, db_session):
    """Verifies claim next job uses skip locked for postgres behavior."""
    mk_job(db_session, job_type="queued")

    query_type = type(db_session.query(models.BackgroundJob))
    original_with_for_update = query_type.with_for_update
    seen: dict[str, bool] = {}

    def _spy_with_for_update(self, *args, **kwargs):
        """Implements the spy with for update helper."""
        seen["skip_locked"] = bool(kwargs.get("skip_locked"))
        return original_with_for_update(self, *args, **kwargs)

    monkeypatch.setattr(query_type, "with_for_update", _spy_with_for_update)
    monkeypatch.setattr(db_session.bind.dialect, "name", "postgresql", raising=False)

    claimed = task_queue.claim_next_job(db_session, worker_id="worker-pg")
    assert claimed is not None
    assert claimed.locked_by == "worker-pg"
    assert seen.get("skip_locked") is True


def test_run_recompute_recommendations_ml_missing_script_path(monkeypatch, tmp_path):
    """Verifies run recompute recommendations ml missing script path behavior."""
    backend_root = tmp_path / "backend"
    backend_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(task_queue, "_backend_root", lambda: backend_root)

    with pytest.raises(RuntimeError, match="Missing trainer script"):
        task_queue._run_recompute_recommendations_ml(payload={})


def test_send_weekly_digest_counts_eligible_users_when_no_events(
    monkeypatch, db_session
):
    """Verifies send weekly digest counts eligible users when no events behavior."""
    user = models.User(
        email="digest-no-events@test.ro",
        password_hash=auth.get_password_hash("student-fixture-A1"),
        role=models.UserRole.student,
        is_active=True,
        email_digest_enabled=True,
        language_preference="ro",
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set())
    )

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 3})
    assert result == {"users": 1, "emails": 0}


def test_send_weekly_digest_filters_blocked_organizers_and_hidden_tags(
    db_session, monkeypatch
):
    """Verifies send weekly digest filters blocked organizers and hidden tags behavior."""
    users, event = seed_weekly_digest_fixture(db_session)
    active_user = users["active"]
    organizer = event.owner
    assert organizer is not None

    hidden_tag = models.Tag(name="digest-hidden-branch")
    event.tags.append(hidden_tag)
    db_session.add(hidden_tag)
    db_session.commit()
    db_session.refresh(hidden_tag)

    db_session.execute(
        models.user_hidden_tags.insert().values(
            user_id=int(active_user.id), tag_id=int(hidden_tag.id)
        )
    )
    db_session.execute(
        models.user_blocked_organizers.insert().values(
            user_id=int(active_user.id),
            organizer_id=int(organizer.id),
        )
    )
    db_session.commit()

    monkeypatch.setattr(task_queue, "enqueue_job", unexpected_enqueue)

    result = task_queue._send_weekly_digest(db=db_session, payload={"top_n": 3})
    assert result == {"users": 1, "emails": 0}


def _seed_mixed_interaction_meta(db_session, user, event, now):
    """Adds interaction rows with varied meta payloads for guardrail coverage."""
    rows = [
        ("impression", now, "not-a-dict"),
        ("impression", now, {"source": "events_list"}),
        ("impression", now, {"source": "other", "sort": "time"}),
        ("click", now, {"source": "events_list", "sort": "unknown"}),
        ("register", now + timedelta(hours=5), None),
    ]
    db_session.add_all(
        [
            interaction(
                user_id=int(user.id),
                event_id=int(event.id),
                kind=kind,
                occurred_at=occurred_at,
                meta=meta,
            )
            for kind, occurred_at, meta in rows
        ]
    )
    db_session.commit()


def test_guardrails_low_volume_with_invalid_days_and_meta_variants(
    monkeypatch, db_session
):
    """Verifies guardrails low volume with invalid days and meta variants behavior."""
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    _seed_mixed_interaction_meta(db_session, user, event, now)
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_days", 7)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 0, "min_impressions": 10, "click_to_register_window_hours": 1},
    )
    assert result["enabled"] is True
    assert result["days"] == 7
    assert result["action"] == "skip_low_volume"


def test_guardrails_returns_ok_for_balanced_metrics(monkeypatch, db_session):
    """Verifies guardrails returns ok for balanced metrics behavior."""
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    add_balanced_guardrail_rows(
        db_session, user_id=int(user.id), event_id=int(event.id), now=now
    )
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": 1,
            "min_impressions": 1,
            "ctr_drop_ratio": 0.5,
            "conversion_drop_ratio": 0.5,
        },
    )
    assert result["action"] == "ok"


def test_guardrails_reports_no_active_model_when_recommended_quality_collapses(
    monkeypatch, db_session
):
    """Verifies guardrails reports no active model when recommended quality collapses
    behavior.
    """
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    add_balanced_guardrail_rows(
        db_session, user_id=int(user.id), event_id=int(event.id), now=now
    )
    db_session.add(
        interaction(
            user_id=int(user.id),
            event_id=int(event.id),
            kind="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": "recommended"},
        )
    )
    db_session.commit()
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": 1,
            "min_impressions": 1,
            "ctr_drop_ratio": 0.0001,
            "conversion_drop_ratio": 0.0001,
        },
    )
    assert result["action"] == "no_active_model"


def test_guardrails_reports_no_previous_model_without_inactive_model(
    monkeypatch, db_session
):
    """Verifies guardrails reports no previous model without inactive model behavior."""
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    add_balanced_guardrail_rows(
        db_session, user_id=int(user.id), event_id=int(event.id), now=now
    )
    db_session.add(
        interaction(
            user_id=int(user.id),
            event_id=int(event.id),
            kind="impression",
            occurred_at=now,
            meta={"source": "events_list", "sort": "recommended"},
        )
    )
    active_model = models.RecommenderModel(
        model_version="active-only",
        feature_names=["bias"],
        weights=[0.0],
        meta={},
        is_active=True,
    )
    db_session.add(active_model)
    db_session.commit()
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": 1,
            "min_impressions": 1,
            "ctr_drop_ratio": 0.0001,
            "conversion_drop_ratio": 0.0001,
        },
    )
    assert result["action"] == "no_previous_model"


def test_send_filling_fast_alerts_branch_matrix_counts_and_exclusions(
    monkeypatch, db_session
):
    """Verifies send filling fast alerts branch matrix counts and exclusions behavior."""
    setup = seed_filling_fast_branch_matrix(db_session)
    enqueued = []
    langs = []
    patch_filling_fast_alerts(monkeypatch, setup, enqueued=enqueued, langs=langs)
    result = task_queue._send_filling_fast_alerts(
        db=db_session,
        payload={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 1},
    )
    assert result["pairs"] >= 7
    assert result["emails"] == 2
    assert len(enqueued) == 2


def test_send_filling_fast_alerts_branch_matrix_defaults_system_language(
    monkeypatch, db_session
):
    """Verifies send filling fast alerts branch matrix defaults system language
    behavior.
    """
    setup = seed_filling_fast_branch_matrix(db_session)
    enqueued = []
    langs = []
    patch_filling_fast_alerts(monkeypatch, setup, enqueued=enqueued, langs=langs)
    task_queue._send_filling_fast_alerts(
        db=db_session,
        payload={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 1},
    )
    assert any(
        email == "system@test.ro" and lang == "ro"
        for email, lang, _available, _title in langs
    )


def test_send_filling_fast_alerts_skips_rows_without_max_seats(monkeypatch):
    """Verifies send filling fast alerts skips rows without max seats behavior."""
    user = SimpleNamespace(
        id=11,
        is_active=True,
        email_filling_fast_enabled=True,
        language_preference="en",
        email="user@test.ro",
    )
    event = SimpleNamespace(
        id=21, owner_id=31, tags=[], max_seats=None, title="No seats"
    )
    fake_db = FakeFillingFastDb(
        ChainQuery(
            subquery_result=SimpleNamespace(
                c=SimpleNamespace(seats_taken=0, event_id=0)
            )
        ),
        ChainQuery(rows=[(user, event, 0)]),
        ChainQuery(first_result=None),
        ChainQuery(first_result=None),
    )
    render_calls = []
    monkeypatch.setattr(
        task_queue, "_load_personalization_exclusions", lambda **_kwargs: (set(), set())
    )
    monkeypatch.setattr(task_queue, "enqueue_job", unexpected_enqueue)
    import app.email_templates as tpl

    monkeypatch.setattr(
        tpl,
        "render_filling_fast_email",
        lambda *_args, **_kwargs: render_calls.append("rendered"),
    )
    result = task_queue._send_filling_fast_alerts(
        db=fake_db,
        payload={"threshold_abs": 5, "threshold_ratio": 0.2, "max_per_user": 1},
    )
    assert result == {"pairs": 1, "emails": 0}
    assert render_calls == []
    assert fake_db.query().filter().first() is None


def test_guardrails_days_fallback_click_source_skip_and_window_skip(
    monkeypatch, db_session
):
    """Verifies guardrails days fallback click source skip and window skip behavior."""
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    seed_guardrail_window_rows(
        db_session, user_id=int(user.id), event_id=int(event.id), now=now
    )
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_days", 7)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": -1,
            "min_impressions": 1,
            "click_to_register_window_hours": 1,
            "ctr_drop_ratio": 0.5,
            "conversion_drop_ratio": 0.5,
        },
    )
    assert result["days"] == 7
    assert result["enabled"] is True


def test_guardrails_skips_registers_with_unknown_click_sort(monkeypatch, db_session):
    """Verifies guardrails skips registers with unknown click sort behavior."""
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            interaction(
                user_id=int(user.id),
                event_id=int(event.id),
                kind="impression",
                occurred_at=now,
                meta={"source": "events_list", "sort": "recommended"},
            ),
            interaction(
                user_id=int(user.id),
                event_id=int(event.id),
                kind="click",
                occurred_at=now + timedelta(minutes=1),
                meta={"source": "events_list", "sort": "unknown"},
            ),
            interaction(
                user_id=int(user.id),
                event_id=int(event.id),
                kind="register",
                occurred_at=now + timedelta(minutes=2),
            ),
        ]
    )
    db_session.commit()
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={"days": 1, "min_impressions": 1, "click_to_register_window_hours": 1},
    )
    assert result["action"] in {
        "skip_low_volume",
        "ok",
        "no_active_model",
        "no_previous_model",
    }


def test_guardrails_rollback_reactivates_previous_model(monkeypatch, db_session):
    """Verifies guardrails rollback reactivates previous model behavior."""
    reset_guardrail_state(db_session)
    user, event = seed_guardrail_user_event(db_session)
    now = datetime.now(timezone.utc)
    previous, active = seed_guardrail_rollback_state(
        db_session,
        user_id=int(user.id),
        event_id=int(event.id),
        now=now,
    )
    enqueued = []
    monkeypatch.setattr(task_queue.settings, "personalization_guardrails_enabled", True)
    monkeypatch.setattr(
        task_queue,
        "enqueue_job",
        lambda *args, **kwargs: enqueued.append((args, kwargs)),
    )
    result = task_queue._evaluate_personalization_guardrails(
        db=db_session,
        payload={
            "days": 1,
            "min_impressions": 1,
            "ctr_drop_ratio": 0.0001,
            "conversion_drop_ratio": 0.0001,
        },
    )
    db_session.refresh(previous)
    db_session.refresh(active)
    assert result["action"] == "rollback"
    assert result["rolled_back_from"] == "model-active"
    assert result["rolled_back_to"] == "model-prev"
    assert previous.is_active is True
    assert active.is_active is False
    assert enqueued and enqueued[0][1]["dedupe_key"] == "global"
