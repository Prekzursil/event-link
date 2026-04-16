#!/usr/bin/env python3
"""Command-line helper: recompute ml prepare state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from recompute_ml_shared import (
    _DeterministicRng,
    _EventFeatures,
    _PreparedState,
    _UserFeatures,
)
from recompute_ml_state_helpers import (
    _history_from_positive_events,
    _holdout_positive_event_ids,
    _interaction_training_state,
    _load_decay_weight_buckets,
    _positive_weights_by_user,
    _prepared_state_from_loaded_data,
    _preferred_lang,
    _resolved_user_city,
    _student_event_state,
)


def _build_users_and_holdout(
    **kwargs,
) -> tuple[dict[int, _UserFeatures], dict[int, str], dict[int, int]]:
    """Build user feature rows together with language and holdout state."""
    users: dict[int, _UserFeatures] = {}
    user_lang: dict[int, str] = {}
    holdout: dict[int, int] = {}
    rng = _DeterministicRng(int(kwargs["args"].seed))

    for student in kwargs["students"]:
        user_id = int(student.id)
        city = _resolved_user_city(
            student=student,
            user_id=user_id,
            implicit_city_by_user=kwargs["implicit_city_by_user"],
            city_weights_by_user=kwargs["city_weights_by_user"],
        )
        user_lang[user_id] = _preferred_lang(student.language_preference)
        positive_event_ids = _holdout_positive_event_ids(
            user_id=user_id,
            positives=kwargs["positives_by_user"].get(user_id, {}),
            holdout=holdout,
            rng=rng,
        )
        (
            history_tags,
            history_categories,
            history_organizers,
        ) = _history_from_positive_events(
            positive_event_ids=positive_event_ids,
            events=kwargs["events"],
            implicit_categories=kwargs["implicit_categories_by_user"].get(
                user_id, set()
            ),
        )
        users[user_id] = _UserFeatures(
            city=city,
            interest_tag_weights=kwargs["interest_tag_weights_by_user"].get(
                user_id, {}
            ),
            history_tags=history_tags,
            history_categories=history_categories,
            history_organizer_ids=history_organizers,
            category_weights=kwargs["category_weights_by_user"].get(user_id, {}),
            city_weights=kwargs["city_weights_by_user"].get(user_id, {}),
        )

    return users, user_lang, holdout


@dataclass(frozen=True)
class _PreparedUserStateInputs:
    """Dependencies needed to build the prepared user feature state."""

    students: list[object]
    args: object
    events: dict[int, _EventFeatures]
    positive_weights: dict[tuple[int, int], float]
    implicit_categories_by_user: dict[int, set[str]]
    implicit_city_by_user: dict[int, str]
    category_weights_by_user: dict[int, dict[str, float]]
    city_weights_by_user: dict[int, dict[str, float]]
    interest_tag_weights_by_user: dict[int, dict[str, float]]


@dataclass(frozen=True)
class _PreparedAssemblyInputs:
    """Dependencies needed to assemble the final prepared recommendation state."""

    user_ids: list[int]
    events: dict[int, _EventFeatures]
    all_event_ids: list[int]
    registered_event_ids_by_user: dict[int, set[int]]
    positive_weights: dict[tuple[int, int], float]
    negative_weights: dict[tuple[int, int], float]
    seen_by_user: dict[int, set[int]]
    impression_position_by_user_event: dict[tuple[int, int], int]
    implicit_interest_tags_by_user: dict[int, set[str]]
    implicit_categories_by_user: dict[int, set[str]]
    implicit_city_by_user: dict[int, str]
    users: dict[int, _UserFeatures]
    user_lang: dict[int, str]
    holdout: dict[int, int]


@dataclass(frozen=True)
class _PreparedTrainingState:
    """Loaded training signals used to build the prepared recommendation state."""

    interest_tag_weights_by_user: dict[int, dict[str, float]]
    category_weights_by_user: dict[int, dict[str, float]]
    city_weights_by_user: dict[int, dict[str, float]]
    registered_event_ids_by_user: dict[int, set[int]]
    positive_weights: dict[tuple[int, int], float]
    negative_weights: dict[tuple[int, int], float]
    seen_by_user: dict[int, set[int]]
    impression_position_by_user_event: dict[tuple[int, int], int]
    implicit_interest_tags_by_user: dict[int, set[str]]
    implicit_categories_by_user: dict[int, set[str]]
    implicit_city_by_user: dict[int, str]


def _build_prepared_user_state(*, inputs: _PreparedUserStateInputs):
    """Build user feature rows from the loaded interaction state."""
    positives_by_user = _positive_weights_by_user(inputs.positive_weights)
    return _build_users_and_holdout(
        students=inputs.students,
        args=inputs.args,
        events=inputs.events,
        positives_by_user=positives_by_user,
        implicit_categories_by_user=inputs.implicit_categories_by_user,
        implicit_city_by_user=inputs.implicit_city_by_user,
        category_weights_by_user=inputs.category_weights_by_user,
        city_weights_by_user=inputs.city_weights_by_user,
        interest_tag_weights_by_user=inputs.interest_tag_weights_by_user,
    )


def _assemble_prepared_state(*, inputs: _PreparedAssemblyInputs) -> _PreparedState:
    """Assemble the prepared state payload consumed by training and scoring."""
    return _prepared_state_from_loaded_data(
        user_ids=inputs.user_ids,
        events=inputs.events,
        all_event_ids=inputs.all_event_ids,
        registered_event_ids_by_user=inputs.registered_event_ids_by_user,
        positive_weights=inputs.positive_weights,
        negative_weights=inputs.negative_weights,
        seen_by_user=inputs.seen_by_user,
        impression_position_by_user_event=inputs.impression_position_by_user_event,
        implicit_interest_tags_by_user=inputs.implicit_interest_tags_by_user,
        implicit_categories_by_user=inputs.implicit_categories_by_user,
        implicit_city_by_user=inputs.implicit_city_by_user,
        users=inputs.users,
        user_lang=inputs.user_lang,
        holdout=inputs.holdout,
    )


def _load_prepared_entities(*, db, models, func, args):
    """Load the student and event rows needed to build the recommendation state."""
    entity_rows = _student_event_state(db=db, models=models, func=func, args=args)
    if entity_rows[0] is None or entity_rows[1] is None or entity_rows[2] is None:
        return None
    students, events, all_event_ids = entity_rows
    return students, events, all_event_ids, [int(user.id) for user in students]


def _load_prepared_training_state(
    *,
    db,
    models,
    args,
    now: datetime,
    decay_lambda: float,
    max_score: float,
):
    """Load the feature buckets and interaction state consumed by preparation."""
    weight_buckets = _load_decay_weight_buckets(
        db=db,
        models=models,
        args=args,
        now=now,
        decay_lambda=decay_lambda,
        max_score=max_score,
    )
    interaction_state = _interaction_training_state(
        db=db,
        models=models,
        args=args,
    )
    return _PreparedTrainingState(*weight_buckets, *interaction_state)


def _build_prepared_user_context(
    *, students, args, events, training_state: _PreparedTrainingState
):
    """Build user state and holdout data from loaded entity and interaction state."""
    return _build_prepared_user_state(
        inputs=_PreparedUserStateInputs(
            students=list(students),
            args=args,
            events=events,
            positive_weights=training_state.positive_weights,
            implicit_categories_by_user=training_state.implicit_categories_by_user,
            implicit_city_by_user=training_state.implicit_city_by_user,
            category_weights_by_user=training_state.category_weights_by_user,
            city_weights_by_user=training_state.city_weights_by_user,
            interest_tag_weights_by_user=training_state.interest_tag_weights_by_user,
        ),
    )


def _assemble_prepared_runtime_state(
    *,
    user_ids: list[int],
    events: dict[int, _EventFeatures],
    all_event_ids: list[int],
    training_state: _PreparedTrainingState,
    users: dict[int, _UserFeatures],
    user_lang: dict[int, str],
    holdout: dict[int, int],
) -> _PreparedState:
    """Assemble the final state from already loaded entities and training signals."""
    impression_positions = training_state.impression_position_by_user_event
    implicit_tags = training_state.implicit_interest_tags_by_user
    return _assemble_prepared_state(
        inputs=_PreparedAssemblyInputs(
            user_ids=user_ids,
            events=events,
            all_event_ids=all_event_ids,
            registered_event_ids_by_user=training_state.registered_event_ids_by_user,
            positive_weights=training_state.positive_weights,
            negative_weights=training_state.negative_weights,
            seen_by_user=training_state.seen_by_user,
            impression_position_by_user_event=impression_positions,
            implicit_interest_tags_by_user=implicit_tags,
            implicit_categories_by_user=training_state.implicit_categories_by_user,
            implicit_city_by_user=training_state.implicit_city_by_user,
            users=users,
            user_lang=user_lang,
            holdout=holdout,
        ),
    )


def _prepare_state(
    *,
    db,
    models,
    func,
    args,
    now: datetime,
    decay_lambda: float,
    max_score: float,
) -> _PreparedState | None:
    """Load and normalize the runtime state required for recommendation generation."""
    prepared_entities = _load_prepared_entities(
        db=db,
        models=models,
        func=func,
        args=args,
    )
    if prepared_entities is None:
        return None
    students, events, all_event_ids, user_ids = prepared_entities
    training_state = _load_prepared_training_state(
        db=db,
        models=models,
        args=args,
        now=now,
        decay_lambda=decay_lambda,
        max_score=max_score,
    )
    users, user_lang, holdout = _build_prepared_user_context(
        students=students,
        args=args,
        events=events,
        training_state=training_state,
    )
    return _assemble_prepared_runtime_state(
        user_ids=user_ids,
        events=events,
        all_event_ids=all_event_ids,
        training_state=training_state,
        users=users,
        user_lang=user_lang,
        holdout=holdout,
    )
