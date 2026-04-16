from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .logging_utils import log_event, log_warning


@dataclass(frozen=True)
class _GuardrailConfig:
    days: int
    min_impressions: int
    ctr_drop_ratio: float
    conversion_drop_ratio: float
    click_to_register_window: timedelta


def _guardrail_config(payload: dict[str, Any]) -> _GuardrailConfig:
    days = int(payload.get("days") or settings.personalization_guardrails_days)
    if days < 1 or days > 365:
        days = int(settings.personalization_guardrails_days)
    click_to_register_hours = int(
        payload.get("click_to_register_window_hours")
        or settings.personalization_guardrails_click_to_register_window_hours
    )
    return _GuardrailConfig(
        days=days,
        min_impressions=int(payload.get("min_impressions") or settings.personalization_guardrails_min_impressions),
        ctr_drop_ratio=float(payload.get("ctr_drop_ratio") or settings.personalization_guardrails_ctr_drop_ratio),
        conversion_drop_ratio=float(
            payload.get("conversion_drop_ratio") or settings.personalization_guardrails_conversion_drop_ratio
        ),
        click_to_register_window=timedelta(hours=max(1, click_to_register_hours)),
    )


def _meta_value(meta: object, key: str) -> str | None:
    if isinstance(meta, dict):
        value = meta.get(key)
        return None if value is None else str(value)
    return None


def _guardrail_buckets() -> dict[str, int]:
    return {"recommended": 0, "time": 0}


def _load_impression_counts(*, db: Session, start: datetime) -> dict[str, int]:
    impressions = _guardrail_buckets()
    rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "impression")
        .all()
    )
    for _user_id, _event_id, _occurred_at, meta in rows:
        source = (_meta_value(meta, "source") or "").strip().lower()
        sort = (_meta_value(meta, "sort") or "").strip().lower()
        if source == "events_list" and sort in impressions:
            impressions[sort] += 1
    return impressions


def _load_click_counts(
    *,
    db: Session,
    start: datetime,
) -> tuple[dict[str, int], dict[tuple[int, int], tuple[str, datetime]]]:
    clicks = _guardrail_buckets()
    click_by_user_event: dict[tuple[int, int], tuple[str, datetime]] = {}
    rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "click")
        .all()
    )
    for user_id, event_id, occurred_at, meta in rows:
        source = (_meta_value(meta, "source") or "").strip().lower()
        sort = (_meta_value(meta, "sort") or "").strip().lower()
        if source != "events_list" or sort not in clicks:
            continue
        clicks[sort] += 1
        key = (int(user_id), int(event_id))
        previous = click_by_user_event.get(key)
        if previous is None or occurred_at > previous[1]:
            click_by_user_event[key] = (sort, occurred_at)
    return clicks, click_by_user_event


def _load_conversion_counts(
    *,
    db: Session,
    start: datetime,
    click_by_user_event: dict[tuple[int, int], tuple[str, datetime]],
    window: timedelta,
) -> dict[str, int]:
    conversions = _guardrail_buckets()
    rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "register")
        .all()
    )
    for user_id, event_id, occurred_at in rows:
        click = click_by_user_event.get((int(user_id), int(event_id)))
        if not click:
            continue
        sort, click_time = click
        if click_time <= occurred_at <= (click_time + window):
            conversions[sort] += 1
    return conversions


def _safe_ratio(num: int, den: int) -> float:
    return float(num) / float(den) if den else 0.0


def _guardrail_result(
    *,
    config: _GuardrailConfig,
    impressions: dict[str, int],
    clicks: dict[str, int],
    conversions: dict[str, int],
) -> dict[str, Any]:
    ctr = {key: _safe_ratio(clicks[key], impressions[key]) for key in impressions}
    conversion = {key: _safe_ratio(conversions[key], clicks[key]) for key in clicks}
    return {
        "enabled": True,
        "days": config.days,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "ctr": ctr,
        "conversion": conversion,
    }


def _is_low_volume(result: dict[str, Any], *, min_impressions: int) -> bool:
    return result["impressions"]["recommended"] < min_impressions or result["impressions"]["time"] < min_impressions


def _guardrail_threshold_status(
    result: dict[str, Any],
    *,
    config: _GuardrailConfig,
) -> tuple[bool, bool]:
    recommended_ctr = result["ctr"]["recommended"]
    time_ctr = result["ctr"]["time"]
    recommended_conv = result["conversion"]["recommended"]
    time_conv = result["conversion"]["time"]
    ctr_ok = time_ctr == 0 or recommended_ctr >= time_ctr * (1.0 - config.ctr_drop_ratio)
    conv_ok = time_conv == 0 or recommended_conv >= time_conv * (1.0 - config.conversion_drop_ratio)
    return ctr_ok, conv_ok


def _active_and_previous_models(db: Session) -> tuple[models.RecommenderModel | None, models.RecommenderModel | None]:
    is_active_attr = "is_active"
    active = (
        db.query(models.RecommenderModel)
        .filter(getattr(models.RecommenderModel, is_active_attr).is_(True))
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    if not active:
        return None, None
    previous = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.id < active.id)
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    return active, previous


def _rollback_guardrail_model(
    *,
    db: Session,
    active: models.RecommenderModel,
    previous: models.RecommenderModel,
    enqueue_job_fn: Callable[..., Any],
    recompute_job_type: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    setattr(active, "is_active", False)
    setattr(previous, "is_active", True)
    db.add_all([active, previous])
    db.commit()
    log_warning(
        "personalization_guardrails_rollback",
        from_model_version=active.model_version,
        to_model_version=previous.model_version,
        **result,
    )
    enqueue_job_fn(
        db,
        recompute_job_type,
        {"top_n": int(settings.recommendations_realtime_refresh_top_n), "skip_training": True},
        dedupe_key="global",
    )
    result["action"] = "rollback"
    result["rolled_back_from"] = str(active.model_version)
    result["rolled_back_to"] = str(previous.model_version)
    return result


def evaluate_personalization_guardrails(
    *,
    db: Session,
    payload: dict[str, Any],
    enqueue_job_fn: Callable[..., Any],
    recompute_job_type: str,
) -> dict[str, Any]:
    if not settings.personalization_guardrails_enabled:
        return {"enabled": False}

    config = _guardrail_config(payload)
    start = datetime.now(timezone.utc) - timedelta(days=config.days)
    impressions = _load_impression_counts(db=db, start=start)
    clicks, click_by_user_event = _load_click_counts(db=db, start=start)
    conversions = _load_conversion_counts(
        db=db,
        start=start,
        click_by_user_event=click_by_user_event,
        window=config.click_to_register_window,
    )
    result = _guardrail_result(config=config, impressions=impressions, clicks=clicks, conversions=conversions)

    if _is_low_volume(result, min_impressions=config.min_impressions):
        log_event("personalization_guardrails_skip_low_volume", **result)
        result["action"] = "skip_low_volume"
        return result

    ctr_ok, conv_ok = _guardrail_threshold_status(result, config=config)
    result["ctr_ok"] = ctr_ok
    result["conversion_ok"] = conv_ok
    if ctr_ok and conv_ok:
        log_event("personalization_guardrails_ok", **result)
        result["action"] = "ok"
        return result

    active, previous = _active_and_previous_models(db)
    if not active:
        log_warning("personalization_guardrails_no_active_model", **result)
        result["action"] = "no_active_model"
        return result
    if not previous:
        log_warning("personalization_guardrails_no_previous_model", active_model_version=active.model_version, **result)
        result["action"] = "no_previous_model"
        return result
    return _rollback_guardrail_model(
        db=db,
        active=active,
        previous=previous,
        enqueue_job_fn=enqueue_job_fn,
        recompute_job_type=recompute_job_type,
        result=result,
    )
