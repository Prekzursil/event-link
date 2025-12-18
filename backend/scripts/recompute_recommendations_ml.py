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
    model_version = os.environ.get("RECOMMENDER_MODEL_VERSION") or f"ml-v1-{now.date().isoformat()}"

    with SessionLocal() as db:
        students = db.query(models.User).filter(models.User.role == models.UserRole.student).all()
        if not students:
            print("No student users found; nothing to do.")
            return 0

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

        interest_tag_rows = (
            db.query(models.user_interest_tags.c.user_id, models.Tag.name)
            .join(models.Tag, models.Tag.id == models.user_interest_tags.c.tag_id)
            .all()
        )
        interest_tags_by_user: dict[int, set[str]] = {}
        for user_id, tag_name in interest_tag_rows:
            normalized = _normalize_tag(str(tag_name))
            if not normalized:
                continue
            interest_tags_by_user.setdefault(int(user_id), set()).add(normalized)

        reg_rows = (
            db.query(models.Registration.user_id, models.Registration.event_id, models.Registration.attended)
            .filter(models.Registration.deleted_at.is_(None))
            .all()
        )
        fav_rows = db.query(models.FavoriteEvent.user_id, models.FavoriteEvent.event_id).all()

        positive_weights: dict[tuple[int, int], float] = {}
        for user_id, event_id, attended in reg_rows:
            weight = 1.0 + (0.5 if attended else 0.0)
            key = (int(user_id), int(event_id))
            positive_weights[key] = max(positive_weights.get(key, 0.0), weight)
        for user_id, event_id in fav_rows:
            key = (int(user_id), int(event_id))
            positive_weights[key] = max(positive_weights.get(key, 0.0), 1.2)

        positives_by_user: dict[int, dict[int, float]] = {}
        for (user_id, event_id), weight in positive_weights.items():
            positives_by_user.setdefault(user_id, {})[event_id] = weight

        users: dict[int, _UserFeatures] = {}
        user_lang: dict[int, str] = {}
        holdout: dict[int, int] = {}
        rng = random.Random(args.seed)

        for student in students:
            user_id = int(student.id)
            city = _normalize_city(student.city)
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

            users[user_id] = _UserFeatures(
                city=city,
                interest_tags=interest_tags_by_user.get(user_id, set()),
                history_tags=history_tags,
                history_categories=history_categories,
                history_organizer_ids=history_organizers,
            )

        examples: list[tuple[list[float], int, float]] = []
        for user_id, positives in positives_by_user.items():
            user = users.get(user_id)
            if not user:
                continue
            user_positive_ids = set(positives.keys()) | ({holdout[user_id]} if user_id in holdout else set())
            for event_id, weight in positives.items():
                ev = events.get(event_id)
                if not ev:
                    continue
                x_pos = _build_feature_vector(user=user, event=ev, now=now)
                examples.append((x_pos, 1, float(weight)))

                neg_added = 0
                while neg_added < args.negatives_per_positive and neg_added < len(all_event_ids):
                    neg_event_id = rng.choice(all_event_ids)
                    if neg_event_id in user_positive_ids:
                        continue
                    neg_ev = events.get(neg_event_id)
                    if not neg_ev:
                        continue
                    x_neg = _build_feature_vector(user=user, event=neg_ev, now=now)
                    examples.append((x_neg, 0, 1.0))
                    neg_added += 1

        if not examples:
            print("No training data found (no registrations/favorites); nothing to do.")
            return 0

        n_features = len(examples[0][0])
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

        user_ids = [int(u.id) for u in students]
        db.query(models.UserRecommendation).filter(models.UserRecommendation.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )

        inserts: list[models.UserRecommendation] = []
        for user_id in user_ids:
            user = users.get(user_id)
            if not user:
                continue

            registered_ids = {
                int(event_id)
                for (uid, event_id), _w in positive_weights.items()
                if int(uid) == user_id
            }

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
