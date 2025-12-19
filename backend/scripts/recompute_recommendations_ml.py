#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _sigmoid(z: float) -> float:
    if z >= 0:
        exp_neg = math.exp(-z)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(z)
    return exp_pos / (1.0 + exp_pos)


def _dot(weights: list[float], features: list[float]) -> float:
    return sum(w * x for w, x in zip(weights, features, strict=False))


@dataclass(frozen=True)
class _EventFeatures:
    tags: set[str]
    category: str | None
    city: str | None
    owner_id: int
    start_time: datetime | None
    seats_taken: int
    max_seats: int | None
    status: str
    publish_at: datetime | None


@dataclass(frozen=True)
class _UserFeatures:
    city: str | None
    interest_tags: set[str]
    history_tags: set[str]
    history_categories: set[str]
    history_organizer_ids: set[int]


# Must match `_build_feature_vector` output order.
FEATURE_NAMES = [
    "bias",
    "overlap_interest_ratio",
    "overlap_history_ratio",
    "same_city",
    "category_match",
    "organizer_match",
    "popularity",
    "days_until",
]


def _normalize_tag(name: str) -> str:
    return (name or "").strip().lower()


def _normalize_city(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    return name.lower() or None


def _build_feature_vector(
    *,
    user: _UserFeatures,
    event: _EventFeatures,
    now: datetime,
) -> list[float]:
    tags = event.tags
    tag_count = max(1, len(tags))

    overlap_interest = len(user.interest_tags & tags)
    overlap_history = len(user.history_tags & tags)

    overlap_interest_ratio = overlap_interest / tag_count
    overlap_history_ratio = overlap_history / tag_count

    same_city = 0.0
    if user.city and event.city and user.city == _normalize_city(event.city):
        same_city = 1.0

    category_match = 0.0
    if event.category and event.category in user.history_categories:
        category_match = 1.0

    organizer_match = 1.0 if event.owner_id in user.history_organizer_ids else 0.0

    popularity = min(math.log1p(event.seats_taken) / 5.0, 1.0)

    days_until = 0.0
    if event.start_time:
        delta_days = (event.start_time - now).total_seconds() / 86400.0
        days_until = max(0.0, min(delta_days / 180.0, 1.0))

    return [
        1.0,  # bias
        overlap_interest_ratio,
        overlap_history_ratio,
        same_city,
        category_match,
        organizer_match,
        popularity,
        days_until,
    ]


def _reason_for(*, user: _UserFeatures, event: _EventFeatures, lang: str) -> str:
    overlap = list(user.interest_tags & event.tags)
    overlap.sort()
    if overlap:
        top = ", ".join(overlap[:3])
        return f"Your interests: {top}" if lang == "en" else f"Interesele tale: {top}"
    if user.city and event.city and user.city == _normalize_city(event.city):
        return "Near you" if lang == "en" else "În apropiere"
    return "Recommended for you" if lang == "en" else "Recomandat pentru tine"


def _train_log_regression_sgd(
    *,
    examples: list[tuple[list[float], int, float]],
    n_features: int,
    epochs: int,
    lr: float,
    l2: float,
    seed: int,
) -> list[float]:
    random.seed(seed)
    weights = [0.0] * n_features
    eps = 1e-12

    for epoch in range(1, epochs + 1):
        random.shuffle(examples)
        total_loss = 0.0
        for x, y, w in examples:
            z = _dot(weights, x)
            p = _sigmoid(z)
            total_loss += w * (-(y * math.log(p + eps) + (1 - y) * math.log(1 - p + eps)))

            err = (p - y) * w
            for i, xi in enumerate(x):
                weights[i] -= lr * (err * xi + l2 * weights[i])

        avg_loss = total_loss / max(1.0, float(len(examples)))
        print(f"[train] epoch={epoch} loss={avg_loss:.4f} examples={len(examples)}")

    return weights


def _impression_negative_weight(position: int | None) -> float:
    if position is None or position < 0:
        return 0.05
    if position <= 2:
        return 0.25
    if position <= 5:
        return 0.15
    if position <= 10:
        return 0.1
    return 0.05


def _evaluate_hitrate_at_k(
    *,
    weights: list[float],
    users: dict[int, _UserFeatures],
    events: dict[int, _EventFeatures],
    positives_holdout: dict[int, int],
    all_event_ids: list[int],
    now: datetime,
    k: int,
    negatives_per_user: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    hits = 0
    total = 0

    for user_id, pos_event_id in positives_holdout.items():
        user = users.get(user_id)
        pos_event = events.get(pos_event_id)
        if not user or not pos_event:
            continue

        negatives: list[int] = []
        while len(negatives) < negatives_per_user and len(negatives) < len(all_event_ids):
            cand = rng.choice(all_event_ids)
            if cand == pos_event_id:
                continue
            negatives.append(cand)

        candidates = [pos_event_id, *negatives]
        scored: list[tuple[float, int]] = []
        for event_id in candidates:
            ev = events.get(event_id)
            if not ev:
                continue
            x = _build_feature_vector(user=user, event=ev, now=now)
            scored.append((_sigmoid(_dot(weights, x)), event_id))

        scored.sort(key=lambda item: item[0], reverse=True)
        top_k = {event_id for _score, event_id in scored[:k]}
        total += 1
        if pos_event_id in top_k:
            hits += 1

    return hits / max(1, total)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline ML v1: train and cache recommendations to user_recommendations.")
    parser.add_argument("--top-n", type=int, default=50, help="How many recommendations to store per user.")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--lr", type=float, default=0.35)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument("--eval-negatives", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--user-id", type=int, default=None, help="Only recompute recommendations for a single student user.")
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training and load weights from the persisted recommender_models table.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Train/eval but do not write to the DB.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))

    os.environ.setdefault("SECRET_KEY", "offline-ml-secret")
    os.environ.setdefault("EMAIL_ENABLED", "false")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Missing DATABASE_URL. Example:\n  DATABASE_URL=postgresql://... python backend/scripts/recompute_recommendations_ml.py")
        return 2

    from app import models  # noqa: PLC0415
    from app.database import SessionLocal  # noqa: PLC0415
    from sqlalchemy import func  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    requested_model_version = os.environ.get("RECOMMENDER_MODEL_VERSION")

    with SessionLocal() as db:
        students_query = db.query(models.User).filter(models.User.role == models.UserRole.student)
        if args.user_id is not None:
            students_query = students_query.filter(models.User.id == int(args.user_id))
        students = students_query.all()
        if not students:
            print("No student users found; nothing to do.")
            return 0

        user_ids = [int(u.id) for u in students]

        tags_by_event_id: dict[int, set[str]] = {}
        events: dict[int, _EventFeatures] = {}
        all_events = db.query(models.Event).filter(models.Event.deleted_at.is_(None)).all()

        seats_rows = (
            db.query(models.Registration.event_id, func.count(models.Registration.id).label("seats_taken"))
            .filter(models.Registration.deleted_at.is_(None))
            .group_by(models.Registration.event_id)
            .all()
        )
        seats_taken_by_event: dict[int, int] = {}
        for event_id, seats_taken in seats_rows:
            seats_taken_by_event[int(event_id)] = int(seats_taken or 0)

        event_tag_rows = (
            db.query(models.event_tags.c.event_id, models.Tag.name)
            .join(models.Tag, models.Tag.id == models.event_tags.c.tag_id)
            .all()
        )
        for event_id, tag_name in event_tag_rows:
            normalized = _normalize_tag(str(tag_name))
            if not normalized:
                continue
            tags_by_event_id.setdefault(int(event_id), set()).add(normalized)

        for ev in all_events:
            event_id = int(ev.id)
            events[event_id] = _EventFeatures(
                tags=tags_by_event_id.get(event_id, set()),
                category=(ev.category or None),
                city=(ev.city or None),
                owner_id=int(ev.owner_id),
                start_time=ev.start_time,
                seats_taken=int(seats_taken_by_event.get(event_id, 0)),
                max_seats=ev.max_seats,
                status=str(ev.status or "published"),
                publish_at=ev.publish_at,
            )

        all_event_ids = list(events.keys())
        if not all_event_ids:
            print("No events found; nothing to do.")
            return 0

        interest_tag_query = (
            db.query(models.user_interest_tags.c.user_id, models.Tag.name)
            .join(models.Tag, models.Tag.id == models.user_interest_tags.c.tag_id)
        )
        if args.user_id is not None:
            interest_tag_query = interest_tag_query.filter(models.user_interest_tags.c.user_id == int(args.user_id))
        interest_tag_rows = interest_tag_query.all()
        interest_tags_by_user: dict[int, set[str]] = {}
        for user_id, tag_name in interest_tag_rows:
            normalized = _normalize_tag(str(tag_name))
            if not normalized:
                continue
            interest_tags_by_user.setdefault(int(user_id), set()).add(normalized)

        implicit_tag_query = (
            db.query(models.UserImplicitInterestTag.user_id, models.Tag.name)
            .join(models.Tag, models.Tag.id == models.UserImplicitInterestTag.tag_id)
        )
        if args.user_id is not None:
            implicit_tag_query = implicit_tag_query.filter(models.UserImplicitInterestTag.user_id == int(args.user_id))
        for user_id, tag_name in implicit_tag_query.all():
            normalized = _normalize_tag(str(tag_name))
            if not normalized:
                continue
            interest_tags_by_user.setdefault(int(user_id), set()).add(normalized)

        reg_query = (
            db.query(models.Registration.user_id, models.Registration.event_id, models.Registration.attended)
            .filter(models.Registration.deleted_at.is_(None))
        )
        if args.user_id is not None:
            reg_query = reg_query.filter(models.Registration.user_id == int(args.user_id))
        reg_rows = reg_query.all()

        fav_query = db.query(models.FavoriteEvent.user_id, models.FavoriteEvent.event_id)
        if args.user_id is not None:
            fav_query = fav_query.filter(models.FavoriteEvent.user_id == int(args.user_id))
        fav_rows = fav_query.all()

        registered_event_ids_by_user: dict[int, set[int]] = {}
        for user_id, event_id, _attended in reg_rows:
            registered_event_ids_by_user.setdefault(int(user_id), set()).add(int(event_id))

        positive_weights: dict[tuple[int, int], float] = {}
        for user_id, event_id, attended in reg_rows:
            weight = 1.0 + (0.5 if attended else 0.0)
            key = (int(user_id), int(event_id))
            positive_weights[key] = max(positive_weights.get(key, 0.0), weight)
        for user_id, event_id in fav_rows:
            key = (int(user_id), int(event_id))
            positive_weights[key] = max(positive_weights.get(key, 0.0), 1.2)

        negative_weights: dict[tuple[int, int], float] = {}
        seen_by_user: dict[int, set[int]] = {}
        impression_position_by_user_event: dict[tuple[int, int], int] = {}
        implicit_interest_tags_by_user: dict[int, set[str]] = {}
        implicit_categories_by_user: dict[int, set[str]] = {}
        implicit_city_by_user: dict[int, str] = {}

        # Optional implicit-feedback signals from interaction tracking (if enabled/migrated).
        try:
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
            if args.user_id is not None:
                search_filter_query = search_filter_query.filter(models.EventInteraction.user_id == int(args.user_id))
            for user_id, interaction_type, meta in search_filter_query.all():
                user_id_int = int(user_id)
                if not isinstance(meta, dict):
                    continue
                tags_value = meta.get("tags")
                if isinstance(tags_value, list):
                    for tag in tags_value:
                        normalized = _normalize_tag(str(tag))
                        if not normalized:
                            continue
                        implicit_interest_tags_by_user.setdefault(user_id_int, set()).add(normalized)

                category_value = meta.get("category")
                if isinstance(category_value, str) and category_value.strip():
                    implicit_categories_by_user.setdefault(user_id_int, set()).add(category_value.strip())

                city_value = meta.get("city")
                if isinstance(city_value, str):
                    normalized_city = _normalize_city(city_value)
                    if normalized_city:
                        implicit_city_by_user[user_id_int] = normalized_city

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
            if args.user_id is not None:
                interaction_query = interaction_query.filter(models.EventInteraction.user_id == int(args.user_id))
            interaction_rows = interaction_query.all()
            for user_id, event_id, interaction_type, meta in interaction_rows:
                user_id_int = int(user_id)
                event_id_int = int(event_id)
                itype = str(interaction_type or "").strip().lower()
                if itype == "impression":
                    seen_by_user.setdefault(user_id_int, set()).add(event_id_int)
                    position = None
                    if isinstance(meta, dict):
                        pos_val = meta.get("position")
                        if isinstance(pos_val, (int, float)):
                            position = int(pos_val)
                    if position is not None:
                        key = (user_id_int, event_id_int)
                        existing = impression_position_by_user_event.get(key)
                        if existing is None or position < existing:
                            impression_position_by_user_event[key] = position
                    continue
                if itype == "unregister":
                    key = (user_id_int, event_id_int)
                    negative_weights[key] = max(negative_weights.get(key, 0.0), 2.0)
                    continue
                weight = 0.0
                if itype == "click":
                    weight = 0.4
                elif itype == "view":
                    weight = 0.25
                elif itype == "dwell":
                    weight = 0.35
                    if isinstance(meta, dict):
                        seconds = meta.get("seconds")
                        if isinstance(seconds, (int, float)) and seconds > 0:
                            weight = min(0.8, weight + (float(seconds) / 120.0) * 0.25)
                elif itype == "share":
                    weight = 0.6
                elif itype == "favorite":
                    weight = 1.2
                elif itype == "register":
                    weight = 1.0
                else:
                    continue

                key = (user_id_int, event_id_int)
                positive_weights[key] = max(positive_weights.get(key, 0.0), weight)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] could not load event_interactions ({exc}); continuing without interaction signals")

        for key in negative_weights:
            positive_weights.pop(key, None)

        positives_by_user: dict[int, dict[int, float]] = {}
        for (user_id, event_id), weight in positive_weights.items():
            positives_by_user.setdefault(user_id, {})[event_id] = weight

        users: dict[int, _UserFeatures] = {}
        user_lang: dict[int, str] = {}
        holdout: dict[int, int] = {}
        rng = random.Random(args.seed)

        for student in students:
            user_id = int(student.id)
            city = _normalize_city(student.city) or implicit_city_by_user.get(user_id)
            pref_lang = (student.language_preference or "system").strip().lower()
            if pref_lang == "en":
                user_lang[user_id] = "en"
            else:
                user_lang[user_id] = "ro"

            pos_events = list(positives_by_user.get(user_id, {}).keys())
            if len(pos_events) >= 2:
                holdout_event = rng.choice(pos_events)
                holdout[user_id] = holdout_event
                positives_by_user[user_id].pop(holdout_event, None)

            history_tags: set[str] = set()
            history_categories: set[str] = set()
            history_organizers: set[int] = set()

            # Build history from registrations and favorites (including held-out).
            for event_id in pos_events:
                ev = events.get(event_id)
                if not ev:
                    continue
                history_tags |= ev.tags
                if ev.category:
                    history_categories.add(ev.category)
                history_organizers.add(ev.owner_id)

            history_categories |= implicit_categories_by_user.get(user_id, set())
            users[user_id] = _UserFeatures(
                city=city,
                interest_tags=interest_tags_by_user.get(user_id, set()) | implicit_interest_tags_by_user.get(user_id, set()),
                history_tags=history_tags,
                history_categories=history_categories,
                history_organizer_ids=history_organizers,
            )

        model_version: str
        weights: list[float]
        hitrate: float | None = None

        if args.skip_training:
            model_query = db.query(models.RecommenderModel)
            model_row = None
            if requested_model_version:
                model_row = model_query.filter(models.RecommenderModel.model_version == requested_model_version).first()
            if model_row is None:
                model_row = (
                    model_query.filter(models.RecommenderModel.is_active.is_(True))
                    .order_by(models.RecommenderModel.id.desc())
                    .first()
                )
            if model_row is None:
                model_row = model_query.order_by(models.RecommenderModel.id.desc()).first()

            if model_row is None:
                print("[warn] no persisted recommender model found; run the retraining job first")
                return 0

            feature_names = list(model_row.feature_names or [])
            weights = [float(w) for w in (model_row.weights or [])]
            if feature_names != FEATURE_NAMES:
                print(f"[error] persisted model feature_names mismatch: expected={FEATURE_NAMES} got={feature_names}")
                return 2
            if len(weights) != len(FEATURE_NAMES):
                print(f"[error] persisted model weights length mismatch: expected={len(FEATURE_NAMES)} got={len(weights)}")
                return 2

            model_version = str(model_row.model_version)
            print(f"[load] using persisted model_version={model_version}")
        else:
            model_version = requested_model_version or f"ml-v1-{now.date().isoformat()}"

            examples: list[tuple[list[float], int, float]] = []
            for user_id, positives in positives_by_user.items():
                user = users.get(user_id)
                if not user:
                    continue
                user_positive_ids = set(positives.keys()) | ({holdout[user_id]} if user_id in holdout else set())
                impression_candidates = [
                    (event_id, impression_position_by_user_event.get((user_id, event_id), 999))
                    for event_id in (seen_by_user.get(user_id, set()) - user_positive_ids)
                ]
                impression_candidates.sort(key=lambda item: item[1])
                impression_negatives = [event_id for event_id, _pos in impression_candidates[:50]]

                for event_id, weight in positives.items():
                    ev = events.get(event_id)
                    if not ev:
                        continue
                    x_pos = _build_feature_vector(user=user, event=ev, now=now)
                    examples.append((x_pos, 1, float(weight)))

                    neg_added = 0
                    while neg_added < args.negatives_per_positive and neg_added < len(all_event_ids):
                        neg_weight = 1.0
                        if impression_negatives:
                            neg_event_id = rng.choice(impression_negatives)
                            neg_weight = _impression_negative_weight(
                                impression_position_by_user_event.get((user_id, neg_event_id))
                            )
                        else:
                            neg_event_id = rng.choice(all_event_ids)
                        if neg_event_id in user_positive_ids:
                            continue
                        neg_ev = events.get(neg_event_id)
                        if not neg_ev:
                            continue
                        x_neg = _build_feature_vector(user=user, event=neg_ev, now=now)
                        examples.append((x_neg, 0, float(neg_weight)))
                        neg_added += 1

                weak_tags = implicit_interest_tags_by_user.get(user_id, set())
                weak_categories = implicit_categories_by_user.get(user_id, set())
                weak_city = implicit_city_by_user.get(user_id)
                if weak_tags or weak_categories or weak_city:
                    added = 0
                    attempts = 0
                    while added < 3 and attempts < 200 and attempts < len(all_event_ids):
                        attempts += 1
                        cand_id = rng.choice(all_event_ids)
                        if cand_id in user_positive_ids:
                            continue
                        cand_ev = events.get(cand_id)
                        if not cand_ev:
                            continue
                        match = False
                        if weak_city and cand_ev.city and _normalize_city(cand_ev.city) == weak_city:
                            match = True
                        if not match and cand_ev.category and cand_ev.category in weak_categories:
                            match = True
                        if not match and weak_tags and (cand_ev.tags & weak_tags):
                            match = True
                        if not match:
                            continue
                        x_weak = _build_feature_vector(user=user, event=cand_ev, now=now)
                        examples.append((x_weak, 1, 0.15))
                        user_positive_ids.add(cand_id)
                        added += 1

            for (user_id, event_id), weight in negative_weights.items():
                user = users.get(user_id)
                ev = events.get(event_id)
                if not user or not ev:
                    continue
                x_neg = _build_feature_vector(user=user, event=ev, now=now)
                examples.append((x_neg, 0, float(weight)))

            if not examples:
                print("No training data found (no registrations/favorites/interactions); nothing to do.")
                return 0

            n_features = len(examples[0][0])
            if n_features != len(FEATURE_NAMES):
                print(f"[error] feature vector length mismatch: expected={len(FEATURE_NAMES)} got={n_features}")
                return 2

            weights = _train_log_regression_sgd(
                examples=examples,
                n_features=n_features,
                epochs=args.epochs,
                lr=args.lr,
                l2=args.l2,
                seed=args.seed,
            )

            hitrate = _evaluate_hitrate_at_k(
                weights=weights,
                users=users,
                events=events,
                positives_holdout=holdout,
                all_event_ids=all_event_ids,
                now=now,
                k=10,
                negatives_per_user=args.eval_negatives,
                seed=args.seed,
            )
            print(f"[eval] hitrate@10={hitrate:.3f} users={len(holdout)}")

            if args.dry_run:
                print("[write] dry-run enabled; skipping DB writes.")
                return 0

            meta = {
                "hitrate_at_10": float(hitrate),
                "trained_at": now.isoformat(),
                "examples": len(examples),
                "epochs": int(args.epochs),
                "lr": float(args.lr),
                "l2": float(args.l2),
                "negatives_per_positive": int(args.negatives_per_positive),
            }

            existing_model = (
                db.query(models.RecommenderModel)
                .filter(models.RecommenderModel.model_version == model_version)
                .first()
            )
            if existing_model is None:
                existing_model = models.RecommenderModel(
                    model_version=model_version,
                    feature_names=list(FEATURE_NAMES),
                    weights=[float(w) for w in weights],
                    meta=meta,
                    is_active=True,
                )
                db.add(existing_model)
            else:
                existing_model.feature_names = list(FEATURE_NAMES)
                existing_model.weights = [float(w) for w in weights]
                existing_model.meta = meta
                existing_model.is_active = True

            db.query(models.RecommenderModel).filter(models.RecommenderModel.model_version != model_version).update(
                {"is_active": False},
                synchronize_session=False,
            )

        if args.dry_run:
            print("[write] dry-run enabled; skipping DB writes.")
            return 0

        eligible_event_ids: list[int] = []
        for event_id, ev in events.items():
            if ev.status != "published":
                continue
            if ev.publish_at and ev.publish_at > now:
                continue
            if ev.start_time and ev.start_time < now:
                continue
            if ev.max_seats is not None and ev.seats_taken >= ev.max_seats:
                continue
            eligible_event_ids.append(event_id)

        db.query(models.UserRecommendation).filter(models.UserRecommendation.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )

        inserts: list[models.UserRecommendation] = []
        for user_id in user_ids:
            user = users.get(user_id)
            if not user:
                continue

            registered_ids = registered_event_ids_by_user.get(user_id, set())

            scored: list[tuple[float, int]] = []
            for event_id in eligible_event_ids:
                if event_id in registered_ids:
                    continue
                ev = events[event_id]
                x = _build_feature_vector(user=user, event=ev, now=now)
                scored.append((_sigmoid(_dot(weights, x)), event_id))

            scored.sort(key=lambda item: item[0], reverse=True)
            top = scored[: max(0, int(args.top_n))]

            student_lang = user_lang.get(user_id, "ro")
            inserts.extend(
                [
                    models.UserRecommendation(
                        user_id=user_id,
                        event_id=event_id,
                        score=float(score),
                        rank=rank,
                        model_version=model_version,
                        reason=_reason_for(user=user, event=events[event_id], lang=student_lang),
                    )
                    for rank, (score, event_id) in enumerate(top, start=1)
                ]
            )

        db.add_all(inserts)
        db.commit()
        print(f"[write] stored {len(inserts)} recommendations (model_version={model_version})")

    print(f"Done. See docs/recommendations-ml.md for operational guidance (repo: {repo_root}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
