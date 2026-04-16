#!/usr/bin/env python3
"""Command-line helper: recompute ml interactions."""

from __future__ import annotations

from recompute_ml_shared import _normalize_category, _normalize_city, _normalize_tag


def _merge_search_filter_tags(
    *, user_id: int, meta: dict[object, object], implicit_interest_tags_by_user
) -> None:
    """Implements the merge search filter tags helper."""
    tags_value = meta.get("tags")
    if not isinstance(tags_value, list):
        return
    for tag in tags_value:
        normalized = _normalize_tag(str(tag))
        if normalized:
            implicit_interest_tags_by_user.setdefault(user_id, set()).add(normalized)


def _merge_search_filter_category(
    *, user_id: int, meta: dict[object, object], implicit_categories_by_user
) -> None:
    """Implements the merge search filter category helper."""
    category_value = meta.get("category")
    if isinstance(category_value, str) and category_value.strip():
        implicit_categories_by_user.setdefault(user_id, set()).add(
            _normalize_category(category_value)
        )


def _merge_search_filter_city(
    *, user_id: int, meta: dict[object, object], implicit_city_by_user
) -> None:
    """Implements the merge search filter city helper."""
    city_value = meta.get("city")
    if isinstance(city_value, str):
        normalized_city = _normalize_city(city_value)
        if normalized_city:
            implicit_city_by_user[user_id] = normalized_city


def _apply_search_filter_preferences(
    *,
    search_filter_rows,
    implicit_interest_tags_by_user,
    implicit_categories_by_user,
    implicit_city_by_user,
):
    """Applies search filter preferences to the target."""
    for raw_user_id, _interaction_type, meta in search_filter_rows:
        if not isinstance(meta, dict):
            continue
        user_id = int(raw_user_id)
        _merge_search_filter_tags(
            user_id=user_id,
            meta=meta,
            implicit_interest_tags_by_user=implicit_interest_tags_by_user,
        )
        _merge_search_filter_category(
            user_id=user_id,
            meta=meta,
            implicit_categories_by_user=implicit_categories_by_user,
        )
        _merge_search_filter_city(
            user_id=user_id,
            meta=meta,
            implicit_city_by_user=implicit_city_by_user,
        )


def _impression_position(meta: object) -> int | None:
    """Implements the impression position helper."""
    if not isinstance(meta, dict):
        return None
    position_value = meta.get("position")
    if not isinstance(position_value, (int, float)):
        return None
    return int(position_value)


def _record_impression_feedback(
    *, user_id: int, event_id: int, meta: object, seen_by_user, impression_position_by_user_event
) -> None:
    """Implements the record impression feedback helper."""
    seen_by_user.setdefault(user_id, set()).add(event_id)
    position = _impression_position(meta)
    if position is None:
        return
    key = (user_id, event_id)
    existing = impression_position_by_user_event.get(key)
    if existing is None or position < existing:
        impression_position_by_user_event[key] = position


def _dwell_positive_weight(meta: object) -> float:
    """Implements the dwell positive weight helper."""
    if not isinstance(meta, dict):
        return 0.35
    seconds = meta.get("seconds")
    if isinstance(seconds, (int, float)) and seconds > 0:
        return min(0.8, 0.35 + (float(seconds) / 120.0) * 0.25)
    return 0.35


def _positive_interaction_weight(*, normalized_type: str, meta: object) -> float:
    """Implements the positive interaction weight helper."""
    if normalized_type == "dwell":
        return _dwell_positive_weight(meta)
    return {
        "click": 0.4,
        "view": 0.25,
        "share": 0.6,
        "favorite": 1.2,
        "register": 1.0,
    }[normalized_type]


def _record_negative_feedback(*, user_id: int, event_id: int, negative_weights) -> None:
    """Implements the record negative feedback helper."""
    key = (user_id, event_id)
    negative_weights[key] = max(negative_weights.get(key, 0.0), 2.0)


def _record_positive_feedback(
    *, user_id: int, event_id: int, normalized_type: str, meta: object, positive_weights
) -> None:
    """Implements the record positive feedback helper."""
    key = (user_id, event_id)
    weight = _positive_interaction_weight(normalized_type=normalized_type, meta=meta)
    positive_weights[key] = max(positive_weights.get(key, 0.0), weight)


def _apply_event_interaction_feedback(
    *,
    interaction_rows,
    seen_by_user,
    impression_position_by_user_event,
    positive_weights,
    negative_weights,
) -> None:
    """Applies event interaction feedback to the target."""
    for raw_user_id, raw_event_id, interaction_type, meta in interaction_rows:
        user_id = int(raw_user_id)
        event_id = int(raw_event_id)
        normalized_type = str(interaction_type or "").strip().lower()
        if normalized_type == "impression":
            _record_impression_feedback(
                user_id=user_id,
                event_id=event_id,
                meta=meta,
                seen_by_user=seen_by_user,
                impression_position_by_user_event=impression_position_by_user_event,
            )
            continue
        if normalized_type == "unregister":
            _record_negative_feedback(
                user_id=user_id, event_id=event_id, negative_weights=negative_weights
            )
            continue
        _record_positive_feedback(
            user_id=user_id,
            event_id=event_id,
            normalized_type=normalized_type,
            meta=meta,
            positive_weights=positive_weights,
        )


def _load_search_filter_preferences(
    *,
    db,
    models,
    user_id: int | None,
    implicit_interest_tags_by_user,
    implicit_categories_by_user,
    implicit_city_by_user,
) -> None:
    """Loads the search filter preferences resource."""
    search_filter_query = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.interaction_type,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.is_(None))
        .filter(models.EventInteraction.interaction_type.in_(["search", "filter"]))
    )
    if user_id is not None:
        search_filter_query = search_filter_query.filter(
            models.EventInteraction.user_id == int(user_id)
        )
    _apply_search_filter_preferences(
        search_filter_rows=search_filter_query.all(),
        implicit_interest_tags_by_user=implicit_interest_tags_by_user,
        implicit_categories_by_user=implicit_categories_by_user,
        implicit_city_by_user=implicit_city_by_user,
    )


def _load_event_feedback_signals(
    *,
    db,
    models,
    user_id: int | None,
    seen_by_user,
    impression_position_by_user_event,
    positive_weights,
    negative_weights,
) -> None:
    """Loads the event feedback signals resource."""
    interaction_query = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.interaction_type,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(
            models.EventInteraction.interaction_type.in_(
                [
                    "impression",
                    "click",
                    "view",
                    "dwell",
                    "share",
                    "favorite",
                    "register",
                    "unregister",
                ]
            )
        )
    )
    if user_id is not None:
        interaction_query = interaction_query.filter(
            models.EventInteraction.user_id == int(user_id)
        )
    _apply_event_interaction_feedback(
        interaction_rows=interaction_query.all(),
        seen_by_user=seen_by_user,
        impression_position_by_user_event=impression_position_by_user_event,
        positive_weights=positive_weights,
        negative_weights=negative_weights,
    )


def _load_interaction_signals(
    *,
    db,
    models,
    user_id: int | None,
    positive_weights,
) -> tuple[
    dict[tuple[int, int], float],
    dict[int, set[int]],
    dict[tuple[int, int], int],
    dict[int, set[str]],
    dict[int, set[str]],
    dict[int, str],
]:
    """Loads the interaction signals resource."""
    negative_weights: dict[tuple[int, int], float] = {}
    seen_by_user: dict[int, set[int]] = {}
    impression_position_by_user_event: dict[tuple[int, int], int] = {}
    implicit_interest_tags_by_user: dict[int, set[str]] = {}
    implicit_categories_by_user: dict[int, set[str]] = {}
    implicit_city_by_user: dict[int, str] = {}

    try:
        _load_search_filter_preferences(
            db=db,
            models=models,
            user_id=user_id,
            implicit_interest_tags_by_user=implicit_interest_tags_by_user,
            implicit_categories_by_user=implicit_categories_by_user,
            implicit_city_by_user=implicit_city_by_user,
        )
        _load_event_feedback_signals(
            db=db,
            models=models,
            user_id=user_id,
            seen_by_user=seen_by_user,
            impression_position_by_user_event=impression_position_by_user_event,
            positive_weights=positive_weights,
            negative_weights=negative_weights,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"[warn] could not load event_interactions ({exc}); continuing without interaction signals"
        )

    return (
        negative_weights,
        seen_by_user,
        impression_position_by_user_event,
        implicit_interest_tags_by_user,
        implicit_categories_by_user,
        implicit_city_by_user,
    )
