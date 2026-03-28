from datetime import date, datetime, timedelta, timezone
from typing import Annotated, List, Optional
from contextlib import asynccontextmanager, suppress
import time
import re
import logging
import asyncio
import secrets
import hashlib
import math
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import case, func, text
from sqlalchemy.orm import Session, joinedload

from . import auth, models, schemas
from . import ro_universities
from .config import settings
from .database import engine, get_db, SessionLocal
from .email_service import send_email_async
from .email_templates import (
    render_password_reset_email,
    render_registration_email,
)
from .logging_utils import (
    RequestIdMiddleware,
    configure_logging,
    log_event,
    log_warning,
)

configure_logging()


def _run_migrations():
    """Run Alembic migrations to the latest head when startup settings allow it."""
    try:
        from alembic import command
        from alembic.config import Config

        base_dir = Path(__file__).resolve().parent.parent
        alembic_ini = base_dir / "alembic.ini"
        if not alembic_ini.exists():
            logging.warning("alembic.ini not found; skipping migrations")
            return
        cfg = Config(str(alembic_ini))
        cfg.set_main_option("script_location", str(base_dir / "alembic"))
        command.upgrade(cfg, "head")
        logging.info("Migrations applied to head")
    except Exception:
        logging.exception("Failed to run migrations on startup")


def _check_configuration():
    """Validate required runtime settings before the application starts."""
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY is required")
    if settings.email_enabled and (not settings.smtp_host or not settings.smtp_sender):
        logging.warning("Email enabled but SMTP host/sender missing; disabling email sending")
        settings.email_enabled = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Prepare startup state and cancel background tasks during shutdown."""
    _check_configuration()
    if getattr(settings, "auto_run_migrations", False):
        _run_migrations()
    elif settings.auto_create_tables:
        models.Base.metadata.create_all(bind=engine)

    cleanup_task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(title="Event Link API", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[models.User, Depends(auth.get_current_user)]
OptionalUser = Annotated[Optional[models.User], Depends(auth.get_optional_user)]
OrganizerUser = Annotated[models.User, Depends(auth.require_organizer)]
StudentUser = Annotated[models.User, Depends(auth.require_student)]
AdminUser = Annotated[models.User, Depends(auth.require_admin)]

_ERROR_RESPONSE_DESCRIPTIONS = {
    400: "Bad request.",
    401: "Unauthorized.",
    403: "Forbidden.",
    404: "Not found.",
    503: "Service unavailable.",
}

_TOKEN_TYPE = "".join(("bear", "er"))
_INVALID_REFRESH_TOKEN_DETAIL = "".join(("Refresh ", "token invalid."))
_MIN_PAGE_DETAIL = "Pagina trebuie să fie cel puțin 1."
_PAGE_SIZE_DETAIL = "Dimensiunea paginii trebuie să fie între 1 și 100."
_EVENT_NOT_FOUND_DETAIL = "Evenimentul nu există"


def _responses(*status_codes: int) -> dict[int, dict[str, str]]:
    """Build a FastAPI response description map from shared error metadata."""
    return {code: {"description": _ERROR_RESPONSE_DESCRIPTIONS[code]} for code in status_codes}


def _validate_cover_url(url: str | None) -> None:
    """Reject non-HTTP(S) cover image links before persisting the payload."""
    pattern = re.compile(r"^https?://")
    if url and not pattern.match(str(url)):
        raise HTTPException(
            status_code=400,
            detail="Cover URL trebuie să fie un link http/https valid.",
        )


_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_SHORTENER_DOMAINS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
}
_SUSPICIOUS_KEYWORDS = {
    "crypto",
    "bitcoin",
    "investment",
    "investiție",
    "investitie",
    "profit",
    "giveaway",
    "free money",
    "câștig",
    "castig",
    "premiu",
    "urgent",
    "telegram",
    "whatsapp",
    "dm me",
    "support",
}


def _compute_moderation(
    *,
    title: str,
    description: str | None,
    location: str | None,
) -> tuple[float, list[str], str]:
    """Score event content for lightweight moderation signals."""
    moderation_text = f"{title or ''}\n{description or ''}\n{location or ''}"
    lowered = moderation_text.lower()

    flags: list[str] = []
    score = 0.0

    urls = _URL_PATTERN.findall(lowered)
    score += _moderation_signal(
        condition=len(urls) >= 3,
        flag="many_links",
        flags=flags,
        weight=0.3,
    )
    score += _moderation_signal(
        condition=any(any(domain in url for domain in _SHORTENER_DOMAINS) for url in urls),
        flag="shortener_link",
        flags=flags,
        weight=0.4,
    )
    score += _moderation_signal(
        condition=any(keyword in lowered for keyword in _SUSPICIOUS_KEYWORDS),
        flag="suspicious_keywords",
        flags=flags,
        weight=0.4,
    )
    score += _moderation_signal(
        condition=bool(urls and re.search(r"\b(password|parol|otp|one[- ]time|cod)\b", lowered)),
        flag="credential_request",
        flags=flags,
        weight=0.5,
    )

    score = min(1.0, score)
    moderation_status = "flagged" if score >= 0.5 else "clean"
    return score, flags, moderation_status


def _moderation_signal(
    *,
    condition: bool,
    flag: str,
    flags: list[str],
    weight: float,
) -> float:
    """Append a moderation flag and return its score contribution when matched."""
    if not condition:
        return 0.0
    flags.append(flag)
    return weight


_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Hackathon": ["hackathon", "ctf"],
    "Workshop": ["workshop", "atelier"],
    "Seminar": ["seminar", "webinar"],
    "Presentation": ["presentation", "prezentare", "talk"],
    "Conference": ["conference", "conferin"],
    "Networking": ["networking", "meetup", "network"],
    "Career Fair": ["career fair", "career", "job", "târg", "targ", "cariere"],
    "Music": ["music", "muzic", "concert", "gig", "dj"],
    "Festival": ["festival"],
    "Party": ["party", "petrec", "club"],
    "Sports": ["sport", "marathon", "run", "alerg"],
    "Volunteering": ["volunteer", "volunt"],
    "Cultural": ["cultural", "theatre", "teatru", "film", "art"],
    "Technical": ["tech", "program", "coding", "software", "ai", "ml", "data", "cloud"],
    "Academic": ["academic", "universit", "research", "cercet"],
    "Social": ["social", "community", "comunit"],
}


def _suggest_category_from_text(content: str) -> str | None:
    """Infer the most likely event category from free-form text."""
    lowered = (content or "").lower()
    best: tuple[int, str] | None = None
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = _keyword_match_count(lowered, keywords)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, category)
    return best[1] if best else None


def _keyword_match_count(content: str, keywords: list[str]) -> int:
    """Count how many category keywords appear in the provided text."""
    return sum(1 for kw in keywords if kw in content)


def _suggest_city_from_text(*, content: str, city: str | None) -> str | None:
    """Infer an event city from the university catalog when the payload omits it."""
    if city:
        return city
    catalog_cities = {item.get("city") for item in ro_universities.get_university_catalog() if item.get("city")}
    lowered = content.lower()
    for candidate_city in sorted(
        catalog_cities,
        key=lambda value: len(str(value)),
        reverse=True,
    ):
        if str(candidate_city).lower() in lowered:
            return str(candidate_city)
    return None


def _suggest_tags_from_text(*, db: Session, content: str) -> list[str]:
    """Suggest existing tags whose names already appear in the provided text."""
    lowered = content.lower()
    suggested_tags: list[str] = []
    for tag in db.query(models.Tag).order_by(models.Tag.name).all():
        name = (tag.name or "").strip()
        if name and name.lower() in lowered:
            suggested_tags.append(name)
    return list(dict.fromkeys(suggested_tags))[:10]


def _find_duplicate_candidates(
    *,
    db: Session,
    current_user: models.User,
    payload: schemas.EventSuggestRequest,
    title_tokens: set[str],
) -> list[schemas.EventDuplicateCandidate]:
    """Return likely duplicate organizer events based on title similarity and timing."""
    if not title_tokens:
        return []
    query = db.query(models.Event).filter(models.Event.owner_id == current_user.id, models.Event.deleted_at.is_(None))
    if payload.start_time:
        normalized_start = _normalize_dt(payload.start_time)
        if normalized_start:
            query = query.filter(
                models.Event.start_time >= normalized_start - timedelta(days=30),
                models.Event.start_time <= normalized_start + timedelta(days=30),
            )
    duplicates: list[schemas.EventDuplicateCandidate] = []
    for event in query.order_by(models.Event.start_time.desc()).limit(50).all():
        similarity = _jaccard_similarity(title_tokens, _tokenize(event.title))
        if similarity < 0.6:
            continue
        duplicates.append(
            schemas.EventDuplicateCandidate(
                id=int(event.id),
                title=event.title,
                start_time=event.start_time,
                city=event.city,
                similarity=float(similarity),
            )
        )
    duplicates.sort(key=lambda item: item.similarity, reverse=True)
    return duplicates[:5]


def _tokenize(content: str) -> set[str]:
    """Tokenize free-form text into normalized words for similarity matching."""
    return {t for t in re.findall(r"[a-z0-9ăâîșț]+", (content or "").lower()) if t}


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _ensure_future_date(start_time: datetime) -> None:
    start_time = _normalize_dt(start_time)
    if start_time and start_time < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data evenimentului nu poate fi în trecut.")


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetimes to timezone-aware UTC instances."""
    if not value:
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_ics_dt(value: Optional[datetime]) -> str:
    value = _normalize_dt(value)
    if not value:
        return ""
    return value.strftime("%Y%m%dT%H%M%SZ")


def _run_cleanup_once(retention_days: int = 90) -> None:
    """Cleanup expired password reset tokens and very old registrations."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)
    db = SessionLocal()
    try:
        expired_tokens = (
            db.query(models.PasswordResetToken)
            .filter((models.PasswordResetToken.used.is_(True)) | (models.PasswordResetToken.expires_at < now))
            .delete(synchronize_session=False)
        )
        old_regs = (
            db.query(models.Registration)
            .join(models.Event, models.Event.id == models.Registration.event_id)
            .filter(models.Event.start_time < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        log_event("cleanup_completed", expired_tokens=expired_tokens, old_registrations=old_regs)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log_warning("cleanup_failed", error=str(exc))
    finally:
        db.close()


async def _cleanup_loop() -> None:
    while True:
        _run_cleanup_once()
        await asyncio.sleep(3600)


def _event_to_ics(event: models.Event, uid_suffix: str = "") -> str:
    start = _format_ics_dt(event.start_time)
    end = _format_ics_dt(event.end_time) if event.end_time else ""
    lines = [
        "BEGIN:VEVENT",
        f"UID:event-{event.id}{uid_suffix}@eventlink",
        f"DTSTAMP:{_format_ics_dt(datetime.now(timezone.utc))}",
        f"DTSTART:{start}",
        f"SUMMARY:{event.title}",
        f"DESCRIPTION:{event.description or ''}",
        f"LOCATION:{event.location or ''}",
    ]
    if end:
        lines.append(f"DTEND:{end}")
    lines.append("END:VEVENT")
    return "\n".join(lines)


def _attach_tags(db: Session, event: models.Event, tag_names: list[str]) -> None:
    normalized: dict[str, str] = {}
    for raw in tag_names:
        name = raw.strip() if raw else ""
        if not name:
            continue
        key = name.lower()
        normalized.setdefault(key, name)
    tags: list[models.Tag] = []
    for key, name in normalized.items():
        tag = db.query(models.Tag).filter(func.lower(models.Tag.name) == key).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    event.tags = tags


def _events_with_counts_query(db: Session, base_query=None):
    if base_query is None:
        base_query = db.query(models.Event).filter(models.Event.deleted_at.is_(None))
    seats_subquery = (
        db.query(
            models.Registration.event_id,
            func.count(models.Registration.id).label("seats_taken"),
        )
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.event_id)
        .subquery()
    )
    query = base_query.outerjoin(seats_subquery, models.Event.id == seats_subquery.c.event_id).add_columns(
        func.coalesce(seats_subquery.c.seats_taken, 0).label("seats_taken")
    )
    return query, seats_subquery


def _serialize_event(
    event: models.Event, seats_taken: int, recommendation_reason: str | None = None
) -> schemas.EventResponse:
    owner_name = None
    if event.owner:
        owner_name = event.owner.full_name or event.owner.email
    return schemas.EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=event.start_time,
        end_time=event.end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        owner_id=event.owner_id,
        owner_name=owner_name,
        tags=event.tags,
        seats_taken=int(seats_taken or 0),
        cover_url=event.cover_url,
        status=event.status,
        publish_at=event.publish_at,
        recommendation_reason=recommendation_reason,
    )


def _is_student_user(user: models.User | None) -> bool:
    return bool(user is not None and getattr(user, "role", None) == models.UserRole.student)


def _preferred_lang(*, request: Request | None, user: models.User | None, default: str = "ro") -> str:
    lang = getattr(user, "language_preference", None) if user is not None else None
    if not lang or lang == "system":
        header_value = request.headers.get("accept-language") if request is not None else None
        lang = header_value or default
    return (lang or default).split(",")[0][:2].lower()


def _normalized_user_city(user: models.User | None) -> str:
    return (getattr(user, "city", None) or "").strip().lower()


def _append_local_reason(*, reason: str | None, event_city: str | None, user_city: str, lang: str) -> str | None:
    is_local = bool(user_city and event_city and event_city.strip().lower() == user_city)
    if not is_local:
        return reason
    suffix = f"Near you: {event_city}" if lang == "en" else f"În apropiere: {event_city}"
    return f"{reason} • {suffix}" if reason else suffix


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1:
        raise HTTPException(status_code=400, detail=_MIN_PAGE_DETAIL)
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail=_PAGE_SIZE_DETAIL)


def _merged_tag_filters(*, tags: list[str] | None, tags_csv: str | None) -> list[str]:
    tag_filters: list[str] = []
    if tags:
        tag_filters.extend(tags)
    if tags_csv:
        tag_filters.extend([tag.strip() for tag in tags_csv.split(",") if tag.strip()])
    return tag_filters


def _apply_event_visibility_filters(query, *, now: datetime, include_past: bool):  # noqa: ANN001
    if not include_past:
        query = query.filter(models.Event.start_time >= now)
    return query.filter(models.Event.status == "published").filter(
        (models.Event.publish_at == None) | (models.Event.publish_at <= now)  # noqa: E711
    )


def _apply_event_attribute_filters(
    query,
    *,
    search: str | None,
    category: str | None,
    tag_filters: list[str],
    city: str | None,
    location: str | None,
):  # noqa: ANN001
    if search:
        query = query.filter(func.lower(models.Event.title).like(f"%{search.lower()}%"))
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    if tag_filters:
        lowered = [tag.lower() for tag in tag_filters]
        query = query.filter(models.Event.tags.any(func.lower(models.Tag.name).in_(lowered)))
    if city:
        query = query.filter(func.lower(models.Event.city).like(f"%{city.lower()}%"))
    if location:
        query = query.filter(func.lower(models.Event.location).like(f"%{location.lower()}%"))
    return query


def _apply_event_date_filters(
    query,
    *,
    start_date: date | None,
    end_date: date | None,
):  # noqa: ANN001
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time <= end_dt)
    return query


def _apply_event_list_filters(
    query,
    *,
    now: datetime,
    filters: schemas.EventListQuery,
    tag_filters: list[str] | None = None,
):  # noqa: ANN001
    merged_tags = (
        tag_filters if tag_filters is not None else _merged_tag_filters(tags=filters.tags, tags_csv=filters.tags_csv)
    )
    query = _apply_event_visibility_filters(query, now=now, include_past=bool(filters.include_past))
    query = _apply_event_attribute_filters(
        query,
        search=filters.search,
        category=filters.category,
        tag_filters=merged_tags,
        city=filters.city,
        location=filters.location,
    )
    return _apply_event_date_filters(query, start_date=filters.start_date, end_date=filters.end_date)


def _load_personalization_exclusions(*, db: Session, user_id: int) -> tuple[set[int], set[int]]:
    hidden_tag_ids = {
        int(row[0])
        for row in db.query(models.user_hidden_tags.c.tag_id).filter(models.user_hidden_tags.c.user_id == user_id).all()
    }
    blocked_organizer_ids = {
        int(row[0])
        for row in db.query(models.user_blocked_organizers.c.organizer_id)
        .filter(models.user_blocked_organizers.c.user_id == user_id)
        .all()
    }
    return hidden_tag_ids, blocked_organizer_ids


def _apply_personalization_exclusions(
    query, *, hidden_tag_ids: set[int], blocked_organizer_ids: set[int]
):  # noqa: ANN001
    if blocked_organizer_ids:
        query = query.filter(~models.Event.owner_id.in_(sorted(blocked_organizer_ids)))
    if hidden_tag_ids:
        query = query.filter(~models.Event.tags.any(models.Tag.id.in_(sorted(hidden_tag_ids))))
    return query


def _load_cached_recommendations(
    *,
    db: Session,
    user: models.User,
    now: datetime,
    registered_event_ids: list[int],
    lang: str,
) -> list[tuple[models.Event, int, Optional[str]]] | None:
    if not settings.recommendations_use_ml_cache:
        return None

    if not _recommendations_cache_is_fresh(db=db, user_id=user.id, now=now):
        return None

    rec_rows = _recommendation_rows_for_user(db=db, user_id=int(user.id))
    if not rec_rows:
        return None

    rec_by_event_id = {int(row.event_id): row for row in rec_rows}
    base_query = _cached_recommendation_event_query(
        db=db,
        event_ids=list(rec_by_event_id.keys()),
        user_id=int(user.id),
        now=now,
        registered_event_ids=registered_event_ids,
    )
    query, _ = _events_with_counts_query(db, base_query)
    ranked = _rank_cached_recommendation_rows(
        rows=query.all(),
        rec_by_event_id=rec_by_event_id,
        lang=lang,
    )

    if not ranked:
        return None

    ranked.sort(key=lambda row: row[0])
    return [(ev, seats, reason) for _rank, ev, seats, reason in ranked]


def _recommendation_rows_for_user(*, db: Session, user_id: int) -> list[models.UserRecommendation]:
    return (
        db.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == user_id)
        .order_by(models.UserRecommendation.rank)
        .limit(50)
        .all()
    )


def _cached_recommendation_event_query(
    *,
    db: Session,
    event_ids: list[int],
    user_id: int,
    now: datetime,
    registered_event_ids: list[int],
):
    base_query = (
        db.query(models.Event)
        .filter(models.Event.id.in_(event_ids))
        .filter(models.Event.deleted_at.is_(None))
        .filter(models.Event.start_time >= now)
        .filter(models.Event.status == "published")
        .filter((models.Event.publish_at == None) | (models.Event.publish_at <= now))  # noqa: E711
    )
    if registered_event_ids:
        base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
    hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=user_id)
    return _apply_personalization_exclusions(
        base_query,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
    )


def _rank_cached_recommendation_rows(
    *,
    rows: list[tuple[models.Event, int]],
    rec_by_event_id: dict[int, models.UserRecommendation],
    lang: str,
) -> list[tuple[int, models.Event, int, Optional[str]]]:
    default_reason = "Recommended for you" if lang == "en" else "Recomandat pentru tine"
    ranked: list[tuple[int, models.Event, int, Optional[str]]] = []
    for ev, seats in rows:
        rec = rec_by_event_id.get(int(ev.id))
        if not _cached_recommendation_row_visible(event=ev, seats=int(seats or 0), rec=rec):
            continue
        ranked.append((int(rec.rank), ev, int(seats or 0), rec.reason or default_reason))
    return ranked


def _cached_recommendation_row_visible(
    *,
    event: models.Event,
    seats: int,
    rec: models.UserRecommendation | None,
) -> bool:
    if rec is None:
        return False
    if event.max_seats is not None and seats >= event.max_seats:
        return False
    return True


def _recommendations_cache_is_fresh(*, db: Session, user_id: int, now: datetime) -> bool:
    latest_generated_at = (
        db.query(func.max(models.UserRecommendation.generated_at))
        .filter(models.UserRecommendation.user_id == user_id)
        .scalar()
    )
    if not latest_generated_at:
        return False
    if getattr(latest_generated_at, "tzinfo", None) is None:
        latest_generated_at = latest_generated_at.replace(tzinfo=timezone.utc)
    max_age = timedelta(seconds=settings.recommendations_cache_max_age_seconds)
    return latest_generated_at >= (now - max_age)


def _default_events_sort(sort: str | None, *, db: Session, current_user: models.User | None, now: datetime) -> str:
    sort_value = (sort or "").strip().lower()
    if sort_value in {"recommended", "time"}:
        return sort_value
    if (
        _is_student_user(current_user)
        and settings.recommendations_use_ml_cache
        and _recommendations_cache_is_fresh(db=db, user_id=current_user.id, now=now)
        and _in_experiment_treatment(
            "personalization_ml_sort",
            settings.experiments_personalization_ml_percent,
            str(current_user.id),
        )
    ):
        return "recommended"
    return "time"


def _use_recommended_sort(sort_value: str, *, db: Session, current_user: models.User | None, now: datetime) -> bool:
    return bool(
        sort_value == "recommended"
        and _is_student_user(current_user)
        and settings.recommendations_use_ml_cache
        and _recommendations_cache_is_fresh(db=db, user_id=current_user.id, now=now)
    )


def _recommendation_reason_map(*, db: Session, user_id: int, event_ids: list[int]) -> dict[int, str]:
    if not event_ids:
        return {}
    return {
        int(event_id): reason
        for event_id, reason in (
            db.query(models.UserRecommendation.event_id, models.UserRecommendation.reason)
            .filter(models.UserRecommendation.user_id == user_id, models.UserRecommendation.event_id.in_(event_ids))
            .all()
        )
    }


def _experiment_bucket(experiment: str, identity: str) -> int:
    digest = hashlib.sha256(f"{experiment}:{identity}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _in_experiment_treatment(experiment: str, percent: int, identity: str) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    return _experiment_bucket(experiment, identity) < percent


def _serialize_public_event(event: models.Event, seats_taken: int) -> schemas.PublicEventResponse:
    organizer_name = None
    if event.owner:
        organizer_name = event.owner.org_name or event.owner.full_name or event.owner.email
    return schemas.PublicEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=event.start_time,
        end_time=event.end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        organizer_name=organizer_name,
        tags=event.tags,
        seats_taken=int(seats_taken or 0),
    )


def _load_event_with_counts(db: Session, event_id: int) -> tuple[models.Event, int]:
    query, _ = _events_with_counts_query(
        db,
        db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)),
    )
    result = query.first()
    if not result:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    return result


def _event_is_visible_to_user(*, event: models.Event, now: datetime, current_user: models.User | None) -> bool:
    if event.status == "published" and (not event.publish_at or event.publish_at <= now):
        return True
    return bool(current_user and (current_user.id == event.owner_id or _is_admin(current_user)))


def _event_user_flags(*, db: Session, event_id: int, current_user: models.User | None) -> tuple[bool, bool]:
    if current_user is None:
        return False, False
    is_registered = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .filter(models.Registration.deleted_at.is_(None))
        .first()
        is not None
    )
    is_favorite = (
        db.query(models.FavoriteEvent)
        .filter(models.FavoriteEvent.event_id == event_id, models.FavoriteEvent.user_id == current_user.id)
        .first()
        is not None
    )
    return is_registered, is_favorite


def _event_recommendation_reason(
    *,
    request: Request,
    db: Session,
    current_user: models.User | None,
    event: models.Event,
) -> str | None:
    if not _is_student_user(current_user):
        return None
    lang = _preferred_lang(request=request, user=current_user)
    rec_reason = (
        db.query(models.UserRecommendation.reason)
        .filter(models.UserRecommendation.user_id == current_user.id, models.UserRecommendation.event_id == event.id)
        .scalar()
    )
    return _append_local_reason(
        reason=rec_reason,
        event_city=event.city,
        user_city=_normalized_user_city(current_user),
        lang=lang,
    )


def _serialize_event_detail(
    *,
    event: models.Event,
    seats_taken: int,
    current_user: models.User | None,
    is_registered: bool,
    is_favorite: bool,
    recommendation_reason: str | None,
) -> schemas.EventDetailResponse:
    available_seats = event.max_seats - seats_taken if event.max_seats is not None else None
    owner_name = event.owner.full_name or event.owner.email if event.owner else None
    return schemas.EventDetailResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=event.start_time,
        end_time=event.end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        owner_id=event.owner_id,
        owner_name=owner_name,
        tags=event.tags,
        seats_taken=seats_taken or 0,
        recommendation_reason=recommendation_reason,
        is_registered=is_registered,
        is_owner=current_user.id == event.owner_id if current_user else False,
        available_seats=available_seats,
        is_favorite=is_favorite,
    )


def _load_event_for_owner_update(*, db: Session, event_id: int, current_user: models.User) -> models.Event:
    db_event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not db_event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if db_event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați acest eveniment.")
    return db_event


def _apply_event_identity_updates(*, db_event: models.Event, update: schemas.EventUpdate) -> None:
    if update.title is not None:
        db_event.title = update.title
    if update.description is not None:
        db_event.description = update.description
    if update.category is not None:
        db_event.category = update.category
    if update.city is not None:
        db_event.city = update.city
    if update.location is not None:
        db_event.location = update.location


def _apply_event_time_updates(*, db_event: models.Event, update: schemas.EventUpdate) -> None:
    normalized_start_time = _normalize_dt(db_event.start_time)
    if update.start_time is not None:
        update.start_time = _normalize_dt(update.start_time)
        _ensure_future_date(update.start_time)
        db_event.start_time = update.start_time
        normalized_start_time = update.start_time
    if update.end_time is not None:
        update.end_time = _normalize_dt(update.end_time)
        if normalized_start_time and update.end_time and update.end_time <= normalized_start_time:
            raise HTTPException(status_code=400, detail="Ora de sfârșit trebuie să fie după ora de început.")
        db_event.end_time = update.end_time
    if update.publish_at is not None:
        db_event.publish_at = _normalize_dt(update.publish_at)


def _apply_event_capacity_updates(*, db_event: models.Event, update: schemas.EventUpdate) -> None:
    if update.max_seats is not None:
        if update.max_seats <= 0:
            raise HTTPException(status_code=400, detail="Numărul maxim de locuri trebuie să fie pozitiv.")
        db_event.max_seats = update.max_seats


def _apply_event_cover_updates(*, db_event: models.Event, update: schemas.EventUpdate) -> None:
    if update.cover_url is None:
        return
    if update.cover_url:
        if len(update.cover_url) > 500:
            raise HTTPException(status_code=400, detail="Cover URL prea lung.")
        _validate_cover_url(update.cover_url)
    db_event.cover_url = update.cover_url


def _apply_event_metadata_updates(*, db: Session, db_event: models.Event, update: schemas.EventUpdate) -> None:
    if update.tags is not None:
        _attach_tags(db, db_event, update.tags)
    if update.status is not None:
        if update.status not in ("draft", "published"):
            raise HTTPException(status_code=400, detail="Status invalid")
        db_event.status = update.status


def _apply_event_update_fields(*, db: Session, db_event: models.Event, update: schemas.EventUpdate) -> bool:
    _apply_event_identity_updates(db_event=db_event, update=update)
    _apply_event_time_updates(db_event=db_event, update=update)
    _apply_event_capacity_updates(db_event=db_event, update=update)
    _apply_event_cover_updates(db_event=db_event, update=update)
    _apply_event_metadata_updates(db=db, db_event=db_event, update=update)
    return any(value is not None for value in (update.title, update.description, update.location))


def _load_registerable_event(*, db: Session, event_id: int, now: datetime) -> tuple[models.Event, int]:
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    _ensure_registerable_event_is_public(event=event, now=now)
    seats_taken = _event_seats_taken(db=db, event_id=event_id)
    if event.max_seats is not None and seats_taken >= event.max_seats:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evenimentul este plin.")
    return event, int(seats_taken)


def _ensure_registerable_event_is_public(*, event: models.Event, now: datetime) -> None:
    if event.status != "published" or (event.publish_at and event.publish_at > now):
        raise HTTPException(status_code=400, detail="Evenimentul nu este publicat.")
    start_time = _normalize_dt(event.start_time)
    if start_time and start_time < now:
        raise HTTPException(status_code=400, detail="Evenimentul a început deja.")


def _event_seats_taken(*, db: Session, event_id: int) -> int:
    return int(
        db.query(func.count(models.Registration.id))
        .filter(models.Registration.event_id == event_id, models.Registration.deleted_at.is_(None))
        .scalar()
        or 0
    )


def _restore_registration_if_deleted(
    *,
    db: Session,
    event: models.Event,
    event_id: int,
    current_user: models.User,
) -> bool:
    existing = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if not existing:
        return False
    if existing.deleted_at is None:
        raise HTTPException(status_code=400, detail="Ești deja înscris la eveniment.")
    existing.deleted_at = None
    existing.deleted_by_user_id = None
    existing.registration_time = datetime.now(timezone.utc)
    db.add(existing)
    _audit_log(
        db,
        entity_type="registration",
        entity_id=existing.id,
        action="restored",
        actor_user_id=current_user.id,
        meta={"event_id": event.id},
    )
    db.commit()
    log_event("event_reregistered", event_id=event.id, user_id=current_user.id)
    return True


def _queue_registration_email(
    *,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
    event: models.Event,
    current_user: models.User,
) -> None:
    lang = _preferred_lang(request=request, user=current_user)
    subject, body_text, body_html = render_registration_email(event, current_user, lang=lang)
    send_email_async(
        background_tasks,
        db,
        current_user.email,
        subject,
        body_text,
        body_html,
        context={"user_id": current_user.id, "event_id": event.id, "lang": lang},
    )


def _serialize_admin_event(event: models.Event, seats_taken: int) -> schemas.AdminEventResponse:
    owner_email = event.owner.email if event.owner else "unknown@example.com"
    owner_name = None
    if event.owner:
        owner_name = event.owner.org_name or event.owner.full_name or event.owner.email
    return schemas.AdminEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=event.start_time,
        end_time=event.end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        owner_id=event.owner_id,
        owner_email=owner_email,
        owner_name=owner_name,
        tags=event.tags,
        seats_taken=int(seats_taken or 0),
        status=event.status,
        publish_at=event.publish_at,
        moderation_score=float(getattr(event, "moderation_score", 0.0) or 0.0),
        moderation_status=getattr(event, "moderation_status", None),
        moderation_flags=getattr(event, "moderation_flags", None),
        moderation_reviewed_at=getattr(event, "moderation_reviewed_at", None),
        moderation_reviewed_by_user_id=getattr(event, "moderation_reviewed_by_user_id", None),
        deleted_at=event.deleted_at,
    )


@app.post("/register", response_model=schemas.Token, responses=_responses(400))
def register(user: schemas.StudentRegister, request: Request, db: DbSession):
    """Register a new user account and return authentication tokens."""
    _enforce_rate_limit("register", request=request, identifier=user.email.lower())
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Acest email este deja folosit.")
    if user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Parolele nu se potrivesc.")

    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        role=models.UserRole.student,
        full_name=user.full_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    log_event("user_registered", user_id=new_user.id, email=new_user.email)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_expires = timedelta(minutes=settings.refresh_token_expire_minutes)
    token_payload = {"sub": str(new_user.id), "email": new_user.email, "role": new_user.role.value}
    access_token = auth.create_access_token(data=token_payload, expires_delta=access_token_expires)
    refresh_token = auth.create_refresh_token(data=token_payload, expires_delta=refresh_expires)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": _TOKEN_TYPE,
        "role": new_user.role,
        "user_id": new_user.id,
    }


@app.post("/login", response_model=schemas.Token, responses=_responses(401))
def login(user_credentials: schemas.UserLogin, request: Request, db: DbSession):
    """Authenticate a user and return fresh authentication tokens."""
    _enforce_rate_limit("login", request=request, identifier=user_credentials.email.lower())
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    if not user or not auth.verify_password(user_credentials.password, user.password_hash):
        log_warning("login_failed", email=user_credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorectă",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cont dezactivat.")

    user.last_seen_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_expires = timedelta(minutes=settings.refresh_token_expire_minutes)
    token_payload = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    access_token = auth.create_access_token(data=token_payload, expires_delta=access_token_expires)
    refresh_token = auth.create_refresh_token(data=token_payload, expires_delta=refresh_expires)
    log_event("login_success", user_id=user.id, email=user.email, role=user.role.value)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": _TOKEN_TYPE,
        "role": user.role,
        "user_id": user.id,
    }


@app.post("/refresh", response_model=schemas.Token, responses=_responses(401))
def refresh_token(payload: schemas.RefreshRequest):
    """Refresh a user's access and refresh tokens."""
    try:
        decoded = auth.jwt.decode(payload.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
    except auth.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expirat.")
    except auth.JWTError:
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH_TOKEN_DETAIL)

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH_TOKEN_DETAIL)

    user_id = decoded.get("sub")
    email = decoded.get("email")
    role = decoded.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH_TOKEN_DETAIL)

    token_payload = {"sub": str(user_id), "email": email, "role": role}
    access_token = auth.create_access_token(
        data=token_payload, expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    refresh_token = auth.create_refresh_token(
        data=token_payload, expires_delta=timedelta(minutes=settings.refresh_token_expire_minutes)
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": _TOKEN_TYPE,
        "role": role,
        "user_id": int(user_id),
    }


@app.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: CurrentUser):
    """Return the authenticated user profile."""
    return current_user


@app.put("/api/me/theme", response_model=schemas.UserResponse)
def update_theme_preference(
    payload: schemas.ThemePreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update the current user's theme preference."""
    current_user.theme_preference = payload.theme_preference
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    log_event("theme_preference_updated", user_id=current_user.id, theme_preference=current_user.theme_preference)
    return current_user


@app.put("/api/me/language", response_model=schemas.UserResponse)
def update_language_preference(
    payload: schemas.LanguagePreferenceUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update the current user's language preference."""
    current_user.language_preference = payload.language_preference
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    log_event(
        "language_preference_updated",
        user_id=current_user.id,
        language_preference=current_user.language_preference,
    )
    return current_user


@app.get("/")
def read_root():
    """Return the API welcome message."""
    return {"message": "Hello from Event Link API!"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Normalize HTTP exceptions into the API error envelope."""
    code = f"http_{exc.status_code}"
    message = exc.detail if isinstance(exc.detail, str) else "Eroare"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}, "detail": message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Normalize unexpected exceptions into the API error envelope."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "internal_error", "message": "A apărut o eroare neașteptată."}},
    )


_RATE_LIMIT_STORE: dict[str, list[float]] = {}


def _enforce_rate_limit(
    action: str,
    request: Request | None = None,
    limit: int = 20,
    window_seconds: int = 60,
    identifier: str | None = None,
) -> None:
    now = time.time()
    identity = identifier or (request.client.host if request.client else "unknown")
    key = f"{action}:{identity}"
    entries = _RATE_LIMIT_STORE.get(key, [])
    entries = [ts for ts in entries if now - ts < window_seconds]
    if len(entries) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Prea multe cereri. Încearcă din nou în câteva momente.",
        )
    entries.append(now)
    _RATE_LIMIT_STORE[key] = entries


def _audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_user_id: int | None = None,
    meta: dict | None = None,
) -> None:
    db.add(
        models.AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_user_id,
            meta=meta,
        )
    )


def _is_admin(user: models.User) -> bool:
    if not user:
        return False
    if getattr(user, "role", None) == models.UserRole.admin:
        return True
    if user.email and settings.admin_emails:
        return user.email.strip().lower() in set(settings.admin_emails)
    return False


def _ensure_registrations_enabled() -> None:
    if getattr(settings, "maintenance_mode_registrations_disabled", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Înscrierile sunt temporar dezactivate. Încearcă din nou mai târziu.",
        )


def _event_list_search_filters(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict[str, Optional[str] | date]:
    return {
        "search": search,
        "category": category,
        "start_date": start_date,
        "end_date": end_date,
    }


def _event_list_tag_filters(
    tags: Annotated[Optional[list[str]], Query()] = None,
    tags_csv: Optional[str] = None,
) -> dict[str, list[str] | str | None]:
    return {
        "tags": tags or [],
        "tags_csv": tags_csv,
    }


def _event_list_location_filters(
    city: Optional[str] = None,
    location: Optional[str] = None,
    include_past: bool = False,
    sort: Optional[str] = None,
) -> dict[str, str | bool | None]:
    return {
        "city": city,
        "location": location,
        "include_past": include_past,
        "sort": sort,
    }


def _event_list_pagination_filters(
    page: int = 1,
    page_size: int = 10,
) -> dict[str, int]:
    return {
        "page": page,
        "page_size": page_size,
    }


def _build_event_list_query(
    search_filters: Annotated[dict[str, Optional[str] | date], Depends(_event_list_search_filters)],
    tag_filters: Annotated[dict[str, list[str] | str | None], Depends(_event_list_tag_filters)],
    location_filters: Annotated[dict[str, str | bool | None], Depends(_event_list_location_filters)],
    pagination_filters: Annotated[dict[str, int], Depends(_event_list_pagination_filters)],
) -> schemas.EventListQuery:
    return schemas.EventListQuery(
        **search_filters,
        **tag_filters,
        **location_filters,
        **pagination_filters,
    )


def _ordered_event_list_query(
    query,
    *,
    db: Session,
    current_user: models.User | None,
    use_recommended_sort: bool,
):  # noqa: ANN001
    if not use_recommended_sort:
        return query.order_by(models.Event.start_time.asc(), models.Event.id.asc())
    rec = models.UserRecommendation
    return query.outerjoin(
        rec,
        (rec.user_id == current_user.id) & (rec.event_id == models.Event.id),
    ).order_by(
        case((rec.rank.is_(None), 1), else_=0),
        rec.rank.asc(),
        models.Event.start_time.asc(),
        models.Event.id.asc(),
    )


def _recommended_event_items(
    *,
    request: Request,
    current_user: models.User,
    db: Session,
    events: list[tuple[models.Event, int]],
) -> list[dict[str, object]]:
    lang = _preferred_lang(request=request, user=current_user)
    user_city = _normalized_user_city(current_user)
    event_ids = [event.id for event, _seats in events]
    reason_by_event_id = _recommendation_reason_map(db=db, user_id=current_user.id, event_ids=event_ids)
    return [
        _serialize_event(
            event,
            seats,
            recommendation_reason=_append_local_reason(
                reason=reason_by_event_id.get(event.id),
                event_city=event.city,
                user_city=user_city,
                lang=lang,
            ),
        )
        for event, seats in events
    ]


@app.get("/api/events", response_model=schemas.PaginatedEvents, responses=_responses(400))
def get_events(
    request: Request,
    filters: Annotated[schemas.EventListQuery, Depends(_build_event_list_query)],
    *,
    db: DbSession,
    current_user: OptionalUser,
):
    """List events visible to the current user."""
    _validate_pagination(filters.page, filters.page_size)
    now = datetime.now(timezone.utc)
    query = _apply_event_list_filters(
        db.query(models.Event).filter(models.Event.deleted_at.is_(None)),
        now=now,
        filters=filters,
    )

    if _is_student_user(current_user):
        hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=current_user.id)
        query = _apply_personalization_exclusions(
            query,
            hidden_tag_ids=hidden_tag_ids,
            blocked_organizer_ids=blocked_organizer_ids,
        )
    total = query.count()
    sort_value = _default_events_sort(filters.sort, db=db, current_user=current_user, now=now)
    use_recommended_sort = _use_recommended_sort(sort_value, db=db, current_user=current_user, now=now)
    query = _ordered_event_list_query(
        query,
        db=db,
        current_user=current_user,
        use_recommended_sort=use_recommended_sort,
    )
    query, _ = _events_with_counts_query(db, query)
    query = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)
    events = query.all()
    if use_recommended_sort:
        items = _recommended_event_items(request=request, current_user=current_user, db=db, events=events)
    else:
        items = [_serialize_event(event, seats) for event, seats in events]
    return {"items": items, "total": total, "page": filters.page, "page_size": filters.page_size}


_REFRESHING_INTERACTION_TYPES = {"click", "view", "share", "favorite", "register", "unregister", "search", "filter"}


def _normalize_interest_value(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _coerce_utc_datetime(value: datetime | None, *, fallback: datetime) -> datetime:
    dt = value or fallback
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _event_learning_delta(*, interaction_type: str, meta: object) -> float:
    normalized_type = (interaction_type or "").strip().lower()
    signal_delta = {
        "click": 1.0,
        "view": 0.6,
        "share": 1.3,
        "favorite": 2.0,
        "register": 2.5,
    }.get(normalized_type)
    if signal_delta is not None:
        return signal_delta
    if normalized_type != "dwell" or not isinstance(meta, dict):
        return 0.0
    seconds = meta.get("seconds")
    if not isinstance(seconds, (int, float)):
        return 0.0
    if float(seconds) < float(settings.recommendations_online_learning_dwell_threshold_seconds):
        return 0.0
    return 0.8 + min(1.0, float(seconds) / 60.0) * 0.4


def _load_existing_interaction_event_ids(*, db: Session, payload: schemas.InteractionBatchIn) -> set[int]:
    event_ids = {event.event_id for event in payload.events if event.event_id is not None}
    if not event_ids:
        return set()
    return {row[0] for row in db.query(models.Event.id).filter(models.Event.id.in_(event_ids)).all()}


def _build_event_interactions(
    *,
    db: Session,
    payload: schemas.InteractionBatchIn,
    current_user: models.User | None,
    now: datetime,
) -> list[models.EventInteraction]:
    existing_event_ids = _load_existing_interaction_event_ids(db=db, payload=payload)
    interactions: list[models.EventInteraction] = []
    for event in payload.events:
        if event.event_id is not None and event.event_id not in existing_event_ids:
            continue
        interactions.append(
            models.EventInteraction(
                user_id=current_user.id if current_user else None,
                event_id=event.event_id,
                interaction_type=event.interaction_type,
                occurred_at=_coerce_utc_datetime(event.occurred_at, fallback=now),
                meta=event.meta,
            )
        )
    return interactions


def _collect_search_filter_deltas(
    *,
    meta: dict[str, object],
    tag_name_deltas: dict[str, float],
    category_deltas: dict[str, float],
    city_deltas: dict[str, float],
) -> None:
    _collect_tag_name_deltas(meta.get("tags"), tag_name_deltas)
    _collect_scalar_interest_delta(meta.get("category"), category_deltas)
    _collect_scalar_interest_delta(meta.get("city"), city_deltas)


def _collect_tag_name_deltas(value: object, deltas: dict[str, float]) -> None:
    if not isinstance(value, list):
        return
    for name in value:
        _collect_scalar_interest_delta(name, deltas)


def _collect_scalar_interest_delta(value: object, deltas: dict[str, float]) -> None:
    if not isinstance(value, str):
        return
    key = _normalize_interest_value(value)
    if key:
        deltas[key] = max(deltas.get(key, 0.0), 0.2)


def _collect_online_learning_deltas(
    payload: schemas.InteractionBatchIn,
) -> tuple[dict[int, float], dict[str, float], dict[str, float], dict[str, float]]:
    event_deltas: dict[int, float] = {}
    tag_name_deltas: dict[str, float] = {}
    category_deltas: dict[str, float] = {}
    city_deltas: dict[str, float] = {}

    for event in payload.events:
        if event.event_id is not None:
            delta = _event_learning_delta(interaction_type=str(event.interaction_type), meta=event.meta)
            if delta > 0:
                event_id = int(event.event_id)
                event_deltas[event_id] = max(event_deltas.get(event_id, 0.0), float(delta))

        if event.interaction_type in {"search", "filter"} and isinstance(event.meta, dict):
            _collect_search_filter_deltas(
                meta=event.meta,
                tag_name_deltas=tag_name_deltas,
                category_deltas=category_deltas,
                city_deltas=city_deltas,
            )

    return event_deltas, tag_name_deltas, category_deltas, city_deltas


def _load_event_delta_context(
    *,
    db: Session,
    event_ids: list[int],
) -> tuple[dict[int, str | None], dict[int, str | None], dict[int, list[int]]]:
    if not event_ids:
        return {}, {}, {}

    event_rows = (
        db.query(models.Event.id, models.Event.category, models.Event.city).filter(models.Event.id.in_(event_ids)).all()
    )
    event_category_by_id = {
        int(event_id): _normalize_interest_value(category) for event_id, category, _city in event_rows
    }
    event_city_by_id = {int(event_id): _normalize_interest_value(city) for event_id, _category, city in event_rows}

    tag_rows = (
        db.query(models.event_tags.c.event_id, models.event_tags.c.tag_id)
        .filter(models.event_tags.c.event_id.in_(event_ids))
        .all()
    )
    tag_ids_by_event: dict[int, list[int]] = {}
    for event_id, tag_id in tag_rows:
        tag_ids_by_event.setdefault(int(event_id), []).append(int(tag_id))
    return event_category_by_id, event_city_by_id, tag_ids_by_event


def _merge_event_signal_deltas(
    *,
    event_deltas: dict[int, float],
    event_category_by_id: dict[int, str | None],
    event_city_by_id: dict[int, str | None],
    tag_ids_by_event: dict[int, list[int]],
    hidden_tag_ids: set[int],
    tag_delta_by_id: dict[int, float],
    category_deltas: dict[str, float],
    city_deltas: dict[str, float],
) -> None:
    for event_id, delta in event_deltas.items():
        category_key = event_category_by_id.get(event_id)
        if category_key:
            category_deltas[category_key] = category_deltas.get(category_key, 0.0) + float(delta)

        city_key = event_city_by_id.get(event_id)
        if city_key:
            city_deltas[city_key] = city_deltas.get(city_key, 0.0) + float(delta)

        tag_ids = tag_ids_by_event.get(event_id, [])
        per_tag = float(delta) / float(max(1, len(tag_ids)))
        for tag_id in tag_ids:
            if tag_id in hidden_tag_ids:
                continue
            tag_delta_by_id[tag_id] = tag_delta_by_id.get(tag_id, 0.0) + per_tag


def _merge_named_tag_deltas(
    *,
    db: Session,
    tag_name_deltas: dict[str, float],
    hidden_tag_ids: set[int],
    tag_delta_by_id: dict[int, float],
) -> None:
    if not tag_name_deltas:
        return
    tag_name_rows = (
        db.query(models.Tag.id, func.lower(models.Tag.name))
        .filter(func.lower(models.Tag.name).in_(sorted(tag_name_deltas.keys())))
        .all()
    )
    for tag_id, tag_name_lower in tag_name_rows:
        if tag_id in hidden_tag_ids:
            continue
        key = str(tag_name_lower or "").strip().lower()
        delta = float(tag_name_deltas.get(key, 0.0))
        tag_delta_by_id[int(tag_id)] = tag_delta_by_id.get(int(tag_id), 0.0) + delta


def _decay_interest_score(
    *,
    score: float,
    last_seen_at: datetime,
    now: datetime,
    decay_lambda: float,
) -> float:
    delta_seconds = (now - last_seen_at).total_seconds()
    if delta_seconds <= 0:
        return float(score)
    return float(score) * math.exp(-decay_lambda * float(delta_seconds))


def _upsert_implicit_tag_scores(
    *,
    db: Session,
    user_id: int,
    tag_delta_by_id: dict[int, float],
    now: datetime,
    max_score: float,
    decay_lambda: float,
) -> None:
    if not tag_delta_by_id:
        return
    existing_rows = (
        db.query(models.UserImplicitInterestTag)
        .filter(
            models.UserImplicitInterestTag.user_id == user_id,
            models.UserImplicitInterestTag.tag_id.in_(sorted(tag_delta_by_id.keys())),
        )
        .all()
    )
    existing_by_tag_id = {int(row.tag_id): row for row in existing_rows}
    for tag_id, row in existing_by_tag_id.items():
        last_seen_at = _coerce_utc_datetime(row.last_seen_at, fallback=now)
        delta = float(tag_delta_by_id.get(tag_id, 0.0))
        row.score = min(
            max_score,
            _decay_interest_score(
                score=float(row.score or 0.0), last_seen_at=last_seen_at, now=now, decay_lambda=decay_lambda
            )
            + delta,
        )
        row.last_seen_at = now
        db.add(row)

    for tag_id, delta in tag_delta_by_id.items():
        if tag_id in existing_by_tag_id:
            continue
        db.add(
            models.UserImplicitInterestTag(
                user_id=user_id,
                tag_id=int(tag_id),
                score=min(max_score, float(delta)),
                last_seen_at=now,
            )
        )


def _upsert_named_interest_scores(
    *,
    db: Session,
    user_id: int,
    deltas: dict[str, float],
    now: datetime,
    max_score: float,
    decay_lambda: float,
    model_cls,
    key_field: str,
) -> None:
    if not deltas:
        return
    column = getattr(model_cls, key_field)
    existing_rows = db.query(model_cls).filter(model_cls.user_id == user_id, column.in_(sorted(deltas.keys()))).all()
    existing_by_key = {str(getattr(row, key_field)): row for row in existing_rows}
    for key, row in existing_by_key.items():
        last_seen_at = _coerce_utc_datetime(getattr(row, "last_seen_at", None), fallback=now)
        delta = float(deltas.get(str(key), 0.0))
        row.score = min(
            max_score,
            _decay_interest_score(
                score=float(row.score or 0.0), last_seen_at=last_seen_at, now=now, decay_lambda=decay_lambda
            )
            + delta,
        )
        row.last_seen_at = now
        db.add(row)
    for key, delta in deltas.items():
        if str(key) in existing_by_key:
            continue
        db.add(
            model_cls(
                user_id=user_id,
                **{
                    key_field: str(key),
                    "score": min(max_score, float(delta)),
                    "last_seen_at": now,
                },
            )
        )


def _apply_online_learning(
    *,
    db: Session,
    payload: schemas.InteractionBatchIn,
    current_user: models.User | None,
    now: datetime,
) -> None:
    if not _online_learning_enabled_for_user(current_user):
        return

    decay_lambda, max_score = _online_learning_settings()
    event_deltas, tag_name_deltas, category_deltas, city_deltas = _collect_online_learning_deltas(payload)
    if not any((event_deltas, tag_name_deltas, category_deltas, city_deltas)):
        return

    hidden_tag_ids, _blocked = _load_personalization_exclusions(db=db, user_id=int(current_user.id))
    tag_delta_by_id: dict[int, float] = {}
    event_ids = sorted(event_deltas.keys())
    event_category_by_id, event_city_by_id, tag_ids_by_event = _load_event_delta_context(db=db, event_ids=event_ids)
    _merge_event_signal_deltas(
        event_deltas=event_deltas,
        event_category_by_id=event_category_by_id,
        event_city_by_id=event_city_by_id,
        tag_ids_by_event=tag_ids_by_event,
        hidden_tag_ids=hidden_tag_ids,
        tag_delta_by_id=tag_delta_by_id,
        category_deltas=category_deltas,
        city_deltas=city_deltas,
    )
    _merge_named_tag_deltas(
        db=db,
        tag_name_deltas=tag_name_deltas,
        hidden_tag_ids=hidden_tag_ids,
        tag_delta_by_id=tag_delta_by_id,
    )
    _upsert_online_learning_scores(
        db=db,
        user_id=int(current_user.id),
        tag_delta_by_id=tag_delta_by_id,
        category_deltas=category_deltas,
        city_deltas=city_deltas,
        now=now,
        max_score=max_score,
        decay_lambda=decay_lambda,
    )
    db.commit()


def _online_learning_enabled_for_user(user: models.User | None) -> bool:
    return bool(
        user is not None
        and getattr(user, "role", None) == models.UserRole.student
        and settings.recommendations_online_learning_enabled
    )


def _online_learning_settings() -> tuple[float, float]:
    half_life_hours = max(1, int(settings.recommendations_online_learning_decay_half_life_hours))
    decay_lambda = math.log(2.0) / (float(half_life_hours) * 3600.0)
    return decay_lambda, float(settings.recommendations_online_learning_max_score)


def _upsert_online_learning_scores(
    *,
    db: Session,
    user_id: int,
    tag_delta_by_id: dict[int, float],
    category_deltas: dict[str, float],
    city_deltas: dict[str, float],
    now: datetime,
    max_score: float,
    decay_lambda: float,
) -> None:
    _upsert_implicit_tag_scores(
        db=db,
        user_id=user_id,
        tag_delta_by_id=tag_delta_by_id,
        now=now,
        max_score=max_score,
        decay_lambda=decay_lambda,
    )
    _upsert_named_interest_scores(
        db=db,
        user_id=user_id,
        deltas=category_deltas,
        now=now,
        max_score=max_score,
        decay_lambda=decay_lambda,
        model_cls=models.UserImplicitInterestCategory,
        key_field="category",
    )
    _upsert_named_interest_scores(
        db=db,
        user_id=user_id,
        deltas=city_deltas,
        now=now,
        max_score=max_score,
        decay_lambda=decay_lambda,
        model_cls=models.UserImplicitInterestCity,
        key_field="city",
    )


def _interaction_should_refresh(event: schemas.InteractionEventIn) -> bool:
    if event.interaction_type in _REFRESHING_INTERACTION_TYPES:
        return True
    if event.interaction_type != "dwell" or not isinstance(event.meta, dict):
        return False
    seconds = event.meta.get("seconds")
    return isinstance(seconds, (int, float)) and float(seconds) >= 10.0


def _refresh_recommendations_too_soon(*, db: Session, user_id: int, now: datetime) -> bool:
    latest_generated_at = (
        db.query(func.max(models.UserRecommendation.generated_at))
        .filter(models.UserRecommendation.user_id == user_id)
        .scalar()
    )
    if latest_generated_at is None:
        return False
    latest_generated_at = _coerce_utc_datetime(latest_generated_at, fallback=now)
    age_seconds = (now - latest_generated_at).total_seconds()
    return age_seconds < float(settings.recommendations_realtime_refresh_min_interval_seconds)


def _maybe_enqueue_realtime_recommendation_refresh(
    *,
    db: Session,
    payload: schemas.InteractionBatchIn,
    current_user: models.User | None,
    now: datetime,
) -> None:
    if not _should_enqueue_realtime_recommendation_refresh(
        db=db,
        payload=payload,
        current_user=current_user,
        now=now,
    ):
        return

    from .task_queue import enqueue_job, JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML  # noqa: PLC0415

    enqueue_job(
        db,
        JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML,
        {
            "user_id": int(current_user.id),
            "top_n": int(settings.recommendations_realtime_refresh_top_n),
            "skip_training": True,
        },
        dedupe_key=str(int(current_user.id)),
    )


def _should_enqueue_realtime_recommendation_refresh(
    *,
    db: Session,
    payload: schemas.InteractionBatchIn,
    current_user: models.User | None,
    now: datetime,
) -> bool:
    if current_user is None or getattr(current_user, "role", None) != models.UserRole.student:
        return False
    if not settings.task_queue_enabled or not settings.recommendations_use_ml_cache:
        return False
    if not settings.recommendations_realtime_refresh_enabled:
        return False
    if not any(_interaction_should_refresh(event) for event in payload.events):
        return False
    return not _refresh_recommendations_too_soon(db=db, user_id=int(current_user.id), now=now)


@app.post("/api/analytics/interactions", status_code=status.HTTP_204_NO_CONTENT)
def record_interactions(
    payload: schemas.InteractionBatchIn,
    request: Request,
    db: DbSession,
    current_user: OptionalUser,
):
    """Record analytics interactions and trigger recommendation refreshes."""
    if not settings.analytics_enabled:
        return

    identifier = str(current_user.id) if current_user else None
    _enforce_rate_limit(
        "analytics_interactions",
        request=request,
        identifier=identifier,
        limit=settings.analytics_rate_limit,
        window_seconds=settings.analytics_rate_window_seconds,
    )

    now = datetime.now(timezone.utc)
    interactions = _build_event_interactions(db=db, payload=payload, current_user=current_user, now=now)
    if not interactions:
        return

    db.add_all(interactions)
    db.commit()
    _apply_online_learning(db=db, payload=payload, current_user=current_user, now=now)
    _maybe_enqueue_realtime_recommendation_refresh(db=db, payload=payload, current_user=current_user, now=now)


@app.get("/api/public/events", response_model=schemas.PaginatedPublicEvents, responses=_responses(400, 404))
def get_public_events(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tags: Annotated[Optional[list[str]], Query()] = None,
    tags_csv: Optional[str] = None,
    city: Optional[str] = None,
    location: Optional[str] = None,
    include_past: bool = False,
    page: int = 1,
    page_size: int = 10,
    *,
    db: DbSession,
):
    """List public events."""
    _enforce_rate_limit(
        "public_events_list",
        request=request,
        limit=settings.public_api_rate_limit,
        window_seconds=settings.public_api_rate_window_seconds,
    )
    _validate_pagination(page, page_size)
    now = datetime.now(timezone.utc)
    filters = schemas.EventListQuery(
        search=search,
        category=category,
        start_date=start_date,
        end_date=end_date,
        tags=tags or [],
        tags_csv=tags_csv,
        city=city,
        location=location,
        include_past=include_past,
        page=page,
        page_size=page_size,
    )
    query = _apply_event_list_filters(
        db.query(models.Event).filter(models.Event.deleted_at.is_(None)),
        now=now,
        filters=filters,
    )
    total = query.count()
    query = query.order_by(models.Event.id, models.Event.start_time)
    query, _ = _events_with_counts_query(db, query)
    query = query.offset((page - 1) * page_size).limit(page_size)
    events = query.all()
    items = [_serialize_public_event(event, seats) for event, seats in events]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/public/events/{event_id}", response_model=schemas.PublicEventDetailResponse, responses=_responses(404))
def get_public_event(event_id: int, request: Request, db: DbSession):
    """Return a public event by identifier."""
    _enforce_rate_limit(
        "public_events_detail",
        request=request,
        limit=settings.public_api_rate_limit,
        window_seconds=settings.public_api_rate_window_seconds,
    )
    query, _ = _events_with_counts_query(
        db,
        db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)),
    )
    result = query.first()
    if not result:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    event, seats_taken = result
    now = datetime.now(timezone.utc)
    if event.status != "published" or (event.publish_at and event.publish_at > now):
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    available_seats = event.max_seats - seats_taken if event.max_seats is not None else None
    base = _serialize_public_event(event, seats_taken)
    return schemas.PublicEventDetailResponse(**base.model_dump(), available_seats=available_seats)


@app.get("/api/events/{event_id}", response_model=schemas.EventDetailResponse, responses=_responses(400))
def get_event(
    event_id: int,
    request: Request,
    db: DbSession,
    current_user: OptionalUser,
):
    """Return an event detail payload for the current user."""
    event, seats_taken = _load_event_with_counts(db, event_id)
    now = datetime.now(timezone.utc)
    if not _event_is_visible_to_user(event=event, now=now, current_user=current_user):
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    is_registered, is_favorite = _event_user_flags(db=db, event_id=event_id, current_user=current_user)
    return _serialize_event_detail(
        event=event,
        seats_taken=seats_taken,
        current_user=current_user,
        is_registered=is_registered,
        is_favorite=is_favorite,
        recommendation_reason=_event_recommendation_reason(
            request=request,
            db=db,
            current_user=current_user,
            event=event,
        ),
    )


def _validate_event_create_payload(
    *,
    event: schemas.EventCreate,
    start_time: datetime | None,
    end_time: datetime | None,
    cover_url: str | None,
) -> None:
    _validate_event_create_times(start_time=start_time, end_time=end_time)
    if event.max_seats is None or event.max_seats <= 0:
        raise HTTPException(status_code=400, detail="Numărul maxim de locuri trebuie să fie pozitiv.")
    _validate_event_create_cover_url(cover_url)


def _validate_event_create_times(*, start_time: datetime | None, end_time: datetime | None) -> None:
    if start_time:
        _ensure_future_date(start_time)
    if end_time and start_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="Ora de sfârșit trebuie să fie după ora de început.")


def _validate_event_create_cover_url(cover_url: str | None) -> None:
    if not cover_url:
        return
    if len(cover_url) > 500:
        raise HTTPException(status_code=400, detail="Cover URL prea lung.")
    _validate_cover_url(cover_url)


def _new_event_from_payload(
    *,
    event: schemas.EventCreate,
    current_user: models.User,
    start_time: datetime | None,
    end_time: datetime | None,
    cover_url: str | None,
) -> models.Event:
    return models.Event(
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=start_time,
        end_time=end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=cover_url,
        owner_id=current_user.id,
        status=event.status or "published",
        publish_at=_normalize_dt(event.publish_at) if event.publish_at else None,
    )


@app.post(
    "/api/events",
    response_model=schemas.EventResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_responses(403, 404),
)
def create_event(event: schemas.EventCreate, db: DbSession, current_user: OrganizerUser):
    """Create a new organizer event."""
    start_time = _normalize_dt(event.start_time)
    end_time = _normalize_dt(event.end_time)
    cover_url = str(event.cover_url) if event.cover_url else None
    _validate_event_create_payload(event=event, start_time=start_time, end_time=end_time, cover_url=cover_url)
    new_event = _new_event_from_payload(
        event=event,
        current_user=current_user,
        start_time=start_time,
        end_time=end_time,
        cover_url=cover_url,
    )
    score, flags, moderation_status = _compute_moderation(
        title=new_event.title,
        description=new_event.description,
        location=new_event.location,
    )
    new_event.moderation_score = float(score)
    new_event.moderation_flags = flags or None
    new_event.moderation_status = moderation_status
    _attach_tags(db, new_event, event.tags or [])
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    log_event("event_created", event_id=new_event.id, owner_id=current_user.id)
    return _serialize_event(new_event, 0)


@app.put("/api/events/{event_id}", response_model=schemas.EventResponse, responses=_responses(400, 403, 404))
def update_event(
    event_id: int,
    update: schemas.EventUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Update an existing organizer event."""
    db_event = _load_event_for_owner_update(db=db, event_id=event_id, current_user=current_user)
    content_changed = _apply_event_update_fields(db=db, db_event=db_event, update=update)
    if content_changed:
        score, flags, moderation_status = _compute_moderation(
            title=db_event.title,
            description=db_event.description,
            location=db_event.location,
        )
        db_event.moderation_score = float(score)
        db_event.moderation_flags = flags or None
        db_event.moderation_status = moderation_status
        db_event.moderation_reviewed_at = None
        db_event.moderation_reviewed_by_user_id = None

    db.commit()
    db.refresh(db_event)
    log_event("event_updated", event_id=db_event.id, owner_id=db_event.owner_id, actor_user_id=current_user.id)
    seats_count = (
        db.query(func.count(models.Registration.id))
        .filter(models.Registration.event_id == db_event.id, models.Registration.deleted_at.is_(None))
        .scalar()
    ) or 0
    return _serialize_event(db_event, seats_count)


@app.delete("/api/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_responses(403, 404))
def delete_event(event_id: int, db: DbSession, current_user: OrganizerUser):
    """Soft-delete an organizer event."""
    db_event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not db_event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if db_event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să ștergeți acest eveniment.")

    now = datetime.now(timezone.utc)
    db_event.deleted_at = now
    db_event.deleted_by_user_id = current_user.id

    registrations = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == db_event.id,
            models.Registration.deleted_at.is_(None),
        )
        .all()
    )
    for registration in registrations:
        registration.deleted_at = now
        registration.deleted_by_user_id = current_user.id
        _audit_log(
            db,
            entity_type="registration",
            entity_id=registration.id,
            action="soft_deleted",
            actor_user_id=current_user.id,
            meta={"event_id": db_event.id, "reason": "event_deleted"},
        )

    _audit_log(
        db,
        entity_type="event",
        entity_id=db_event.id,
        action="soft_deleted",
        actor_user_id=current_user.id,
        meta={"registrations_soft_deleted": len(registrations)},
    )

    db.commit()
    log_event(
        "event_soft_deleted",
        event_id=db_event.id,
        owner_id=db_event.owner_id,
        actor_user_id=current_user.id,
    )


def _authorize_event_restore(*, event: models.Event, current_user: models.User) -> None:
    if _is_admin(current_user):
        return
    if current_user.role != models.UserRole.organizator:
        raise HTTPException(status_code=403, detail="Acces doar pentru organizatori.")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să restaurați acest eveniment.")


def _restore_event_registrations(
    *,
    db: Session,
    event: models.Event,
    current_user: models.User,
    deleted_by_user_id: int | None,
) -> int:
    if not deleted_by_user_id:
        return 0
    regs = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event.id,
            models.Registration.deleted_at.is_not(None),
            models.Registration.deleted_by_user_id == deleted_by_user_id,
        )
        .all()
    )
    for reg in regs:
        reg.deleted_at = None
        reg.deleted_by_user_id = None
        _audit_log(
            db,
            entity_type="registration",
            entity_id=reg.id,
            action="restored",
            actor_user_id=current_user.id,
            meta={"event_id": event.id, "reason": "event_restored"},
        )
    return len(regs)


@app.post("/api/events/{event_id}/restore", responses=_responses(403, 404))
def restore_event(
    event_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Restore a previously deleted organizer event."""
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event or db_event.deleted_at is None:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)

    _authorize_event_restore(event=db_event, current_user=current_user)

    deleted_by_user_id = db_event.deleted_by_user_id
    db_event.deleted_at = None
    db_event.deleted_by_user_id = None

    restored_registrations = _restore_event_registrations(
        db=db,
        event=db_event,
        current_user=current_user,
        deleted_by_user_id=deleted_by_user_id,
    )

    _audit_log(
        db,
        entity_type="event",
        entity_id=db_event.id,
        action="restored",
        actor_user_id=current_user.id,
        meta={"restored_registrations": restored_registrations},
    )

    db.commit()
    log_event(
        "event_restored",
        event_id=db_event.id,
        owner_id=db_event.owner_id,
        actor_user_id=current_user.id,
        restored_registrations=restored_registrations,
    )
    return {"status": "restored", "restored_registrations": restored_registrations}


@app.post("/api/events/{event_id}/clone", response_model=schemas.EventResponse, responses=_responses(400))
def clone_event(
    event_id: int,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Clone an existing organizer event."""
    orig = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not orig:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if orig.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să clonați acest eveniment.")

    start_time = _normalize_dt(orig.start_time)
    if start_time and start_time < datetime.now(timezone.utc):
        start_time = datetime.now(timezone.utc) + timedelta(days=7)

    new_event = models.Event(
        title=f"Copie - {orig.title}",
        description=orig.description,
        category=orig.category,
        start_time=start_time,
        end_time=_normalize_dt(orig.end_time) if orig.end_time else None,
        city=orig.city,
        location=orig.location,
        max_seats=orig.max_seats,
        cover_url=orig.cover_url,
        owner_id=current_user.id,
        status="draft",
        publish_at=None,
    )
    _attach_tags(db, new_event, [t.name for t in orig.tags])
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    log_event("event_cloned", source_event_id=orig.id, new_event_id=new_event.id, owner_id=current_user.id)
    seats = (
        db.query(func.count(models.Registration.id))
        .filter(models.Registration.event_id == new_event.id, models.Registration.deleted_at.is_(None))
        .scalar()
    ) or 0
    return _serialize_event(new_event, seats)


@app.get("/api/organizer/events", response_model=List[schemas.EventResponse], responses=_responses(403, 404))
def organizer_events(
    include_deleted: bool = False,
    *,
    db: DbSession,
    current_user: OrganizerUser,
):
    """List events owned by the current organizer."""
    base_query = db.query(models.Event).filter(models.Event.owner_id == current_user.id)
    if not include_deleted:
        base_query = base_query.filter(models.Event.deleted_at.is_(None))
    base_query = base_query.order_by(models.Event.start_time)
    query, _ = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


@app.post("/api/organizer/events/bulk/status", responses=_responses(400, 403, 404))
def organizer_bulk_update_status(
    payload: schemas.OrganizerBulkStatusUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Bulk-update publish status for organizer events."""
    event_ids = list(dict.fromkeys(payload.event_ids))
    if not event_ids:
        raise HTTPException(status_code=400, detail="Nu ați selectat niciun eveniment.")

    events = db.query(models.Event).filter(models.Event.id.in_(event_ids), models.Event.deleted_at.is_(None)).all()
    if len(events) != len(set(event_ids)):
        raise HTTPException(status_code=404, detail="Unele evenimente nu există.")
    if not _is_admin(current_user) and any(ev.owner_id != current_user.id for ev in events):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați toate evenimentele selectate.")

    for ev in events:
        if ev.status == payload.status:
            continue
        old = ev.status
        ev.status = payload.status
        _audit_log(
            db,
            entity_type="event",
            entity_id=ev.id,
            action="status_updated",
            actor_user_id=current_user.id,
            meta={"from": old, "to": payload.status, "bulk": True},
        )

    db.commit()
    log_event(
        "organizer_bulk_event_status_updated",
        actor_user_id=current_user.id,
        status=payload.status,
        event_ids=event_ids,
    )
    return {"updated": len(events)}


def _organizer_bulk_events(
    *,
    db: Session,
    event_ids: list[int],
    current_user: models.User,
) -> list[models.Event]:
    events = db.query(models.Event).filter(models.Event.id.in_(event_ids), models.Event.deleted_at.is_(None)).all()
    if len(events) != len(set(event_ids)):
        raise HTTPException(status_code=404, detail="Unele evenimente nu există.")
    if not _is_admin(current_user) and any(ev.owner_id != current_user.id for ev in events):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați toate evenimentele selectate.")
    return events


def _validate_bulk_tag_names(tags: list[str]) -> None:
    for tag in tags:
        if tag and len(tag.strip()) > 100:
            raise HTTPException(status_code=400, detail="Etichetele trebuie să aibă maxim 100 de caractere.")


@app.post("/api/organizer/events/bulk/tags", responses=_responses(400, 403, 404))
def organizer_bulk_update_tags(
    payload: schemas.OrganizerBulkTagsUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Bulk-update tags for organizer events."""
    event_ids = list(dict.fromkeys(payload.event_ids))
    if not event_ids:
        raise HTTPException(status_code=400, detail="Nu ați selectat niciun eveniment.")

    events = _organizer_bulk_events(db=db, event_ids=event_ids, current_user=current_user)
    _validate_bulk_tag_names(payload.tags)

    for ev in events:
        _attach_tags(db, ev, payload.tags)
        _audit_log(
            db,
            entity_type="event",
            entity_id=ev.id,
            action="tags_updated",
            actor_user_id=current_user.id,
            meta={"tags": payload.tags, "bulk": True},
        )

    db.commit()
    log_event(
        "organizer_bulk_event_tags_updated",
        actor_user_id=current_user.id,
        event_ids=event_ids,
        tags=payload.tags,
    )
    return {"updated": len(events)}


@app.post("/api/organizer/events/suggest", response_model=schemas.EventSuggestResponse, responses=_responses(403, 404))
def organizer_suggest_event(
    payload: schemas.EventSuggestRequest,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Suggest metadata and duplicates for an organizer event draft."""
    combined_text = " ".join(
        [
            payload.title or "",
            payload.description or "",
            payload.city or "",
            payload.location or "",
        ]
    ).strip()

    suggested_category = payload.category or _suggest_category_from_text(combined_text)
    suggested_city = _suggest_city_from_text(content=combined_text, city=payload.city)
    suggested_tags = _suggest_tags_from_text(db=db, content=combined_text)
    duplicates = _find_duplicate_candidates(
        db=db,
        current_user=current_user,
        payload=payload,
        title_tokens=_tokenize(payload.title),
    )

    moderation_score, moderation_flags, moderation_status = _compute_moderation(
        title=payload.title,
        description=payload.description,
        location=payload.location,
    )

    return schemas.EventSuggestResponse(
        suggested_category=suggested_category,
        suggested_city=suggested_city,
        suggested_tags=suggested_tags,
        duplicates=duplicates,
        moderation_score=float(moderation_score),
        moderation_flags=moderation_flags,
        moderation_status=moderation_status,
    )


def _load_owned_event_for_email(*, db: Session, event_id: int, current_user: models.User) -> models.Event:
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să trimiteți email pentru acest eveniment.")
    return event


def _participant_email_addresses(*, db: Session, event_id: int) -> list[str]:
    rows = (
        db.query(models.User.email)
        .join(models.Registration, models.Registration.user_id == models.User.id)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.deleted_at.is_(None),
        )
        .all()
    )
    return [str(email) for (email,) in rows]


@app.post(
    "/api/organizer/events/{event_id}/participants/email",
    response_model=schemas.OrganizerEmailParticipantsResponse,
    responses=_responses(400, 404),
)
def email_event_participants(
    event_id: int,
    payload: schemas.OrganizerEmailParticipantsRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Queue participant emails for an organizer event."""
    _enforce_rate_limit(
        "organizer_email_participants",
        request=request,
        identifier=current_user.email.lower(),
        limit=5,
        window_seconds=60,
    )
    event = _load_owned_event_for_email(db=db, event_id=event_id, current_user=current_user)
    recipient_emails = _participant_email_addresses(db=db, event_id=event_id)
    for email in recipient_emails:
        send_email_async(
            background_tasks,
            db,
            email,
            payload.subject,
            payload.message,
            None,
            context={"event_id": event_id, "actor_user_id": current_user.id},
        )

    _audit_log(
        db,
        entity_type="event",
        entity_id=event.id,
        action="participants_emailed",
        actor_user_id=current_user.id,
        meta={"recipients": len(recipient_emails)},
    )
    db.commit()
    log_event(
        "organizer_participants_emailed",
        event_id=event.id,
        owner_id=event.owner_id,
        actor_user_id=current_user.id,
        recipients=len(recipient_emails),
    )
    return {"recipients": len(recipient_emails)}


def _serialize_profile(user: models.User, db: Session) -> schemas.OrganizerProfileResponse:
    base_query = db.query(models.Event).filter(models.Event.owner_id == user.id, models.Event.deleted_at.is_(None))
    now = datetime.now(timezone.utc)
    base_query = base_query.filter(
        models.Event.status == "published",
        (models.Event.publish_at == None) | (models.Event.publish_at <= now),  # noqa: E711
    ).order_by(models.Event.start_time)
    query, _ = _events_with_counts_query(db, base_query)
    events = [_serialize_event(ev, seats) for ev, seats in query.all()]
    return schemas.OrganizerProfileResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_name=user.org_name,
        org_description=user.org_description,
        org_logo_url=user.org_logo_url,
        org_website=user.org_website,
        events=events,
    )


@app.get("/api/organizers/{organizer_id}", response_model=schemas.OrganizerProfileResponse, responses=_responses(404))
def get_organizer_profile(organizer_id: int, db: DbSession):
    """Return a public organizer profile."""
    user = (
        db.query(models.User)
        .filter(models.User.id == organizer_id, models.User.role == models.UserRole.organizator)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Organizatorul nu există")
    return _serialize_profile(user, db)


@app.put("/api/organizers/me/profile", response_model=schemas.OrganizerProfileResponse, responses=_responses(400))
def update_organizer_profile(
    payload: schemas.OrganizerProfileUpdate,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Update the current organizer profile."""
    logo_url = str(payload.org_logo_url) if payload.org_logo_url else None
    if logo_url and len(logo_url) > 500:
        raise HTTPException(status_code=400, detail="URL logo prea lung")
    current_user.org_name = payload.org_name or current_user.org_name
    current_user.org_description = payload.org_description
    current_user.org_logo_url = logo_url
    current_user.org_website = payload.org_website
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user, db)


# ===================== TAGS =====================


@app.get("/api/metadata/universities", response_model=schemas.UniversityCatalogResponse)
def list_university_catalog():
    """Return the university catalog metadata."""
    return {"items": ro_universities.get_university_catalog()}


@app.get("/api/tags", response_model=schemas.TagListResponse)
def get_all_tags(db: DbSession):
    """Get all available tags for filtering and student interests."""
    tags = db.query(models.Tag).order_by(models.Tag.name).all()
    return {"items": [{"id": t.id, "name": t.name} for t in tags]}


# ===================== STUDENT PROFILE =====================


@app.get("/api/me/profile", response_model=schemas.StudentProfileResponse, responses=_responses(400))
def get_student_profile(
    db: DbSession,
    current_user: CurrentUser,
):
    """Get current user's profile with interest tags."""
    return _serialize_student_profile(current_user)


def _serialize_student_profile(user: models.User) -> dict[str, object]:
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "city": user.city,
        "university": ro_universities.normalize_university_name(user.university),
        "faculty": user.faculty,
        "study_level": user.study_level,
        "study_year": user.study_year,
        "interest_tags": [{"id": t.id, "name": t.name} for t in user.interest_tags],
    }


def _apply_student_profile_payload(*, current_user: models.User, payload: schemas.StudentProfileUpdate) -> None:
    field_updates = (
        ("full_name", payload.full_name, None),
        ("city", payload.city, lambda value: value.strip() or None),
        ("faculty", payload.faculty, lambda value: value.strip() or None),
        ("study_level", payload.study_level, None),
        ("study_year", payload.study_year, None),
    )
    for attr, value, transformer in field_updates:
        if value is None:
            continue
        setattr(current_user, attr, transformer(value) if transformer else value)
    if payload.university is not None:
        current_user.university = ro_universities.normalize_university_name(payload.university)


def _validate_student_study_year(current_user: models.User) -> None:
    if not current_user.study_level or not current_user.study_year:
        return
    max_year = {"bachelor": 4, "master": 2, "phd": 4, "medicine": 6}.get(current_user.study_level, 10)
    if current_user.study_year < 1 or current_user.study_year > max_year:
        raise HTTPException(
            status_code=400,
            detail=f"An invalid pentru nivelul {current_user.study_level}. (1-{max_year})",
        )


def _replace_student_interest_tags(
    *,
    db: Session,
    current_user: models.User,
    interest_tag_ids: list[int] | None,
) -> None:
    if interest_tag_ids is None:
        return
    tags = db.query(models.Tag).filter(models.Tag.id.in_(interest_tag_ids)).all()
    current_user.interest_tags = tags


@app.put("/api/me/profile", response_model=schemas.StudentProfileResponse, responses=_responses(400))
def update_student_profile(
    payload: schemas.StudentProfileUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update current user's profile and interest tags."""
    _apply_student_profile_payload(current_user=current_user, payload=payload)
    _validate_student_study_year(current_user)
    _replace_student_interest_tags(db=db, current_user=current_user, interest_tag_ids=payload.interest_tag_ids)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _serialize_student_profile(current_user)


# ===================== PERSONALIZATION SETTINGS =====================


@app.get("/api/me/personalization", response_model=schemas.PersonalizationSettingsResponse, responses=_responses(404))
def get_personalization_settings(
    db: DbSession,
    current_user: StudentUser,
):
    """Return the current student's personalization settings."""
    hidden_tags = (
        db.query(models.Tag)
        .join(models.user_hidden_tags, models.user_hidden_tags.c.tag_id == models.Tag.id)
        .filter(models.user_hidden_tags.c.user_id == current_user.id)
        .order_by(models.Tag.name)
        .all()
    )
    blocked_organizers = (
        db.query(models.User)
        .join(
            models.user_blocked_organizers,
            models.user_blocked_organizers.c.organizer_id == models.User.id,
        )
        .filter(models.user_blocked_organizers.c.user_id == current_user.id)
        .order_by(models.User.email)
        .all()
    )
    return {"hidden_tags": hidden_tags, "blocked_organizers": blocked_organizers}


@app.post(
    "/api/me/personalization/hidden-tags/{tag_id}", status_code=status.HTTP_201_CREATED, responses=_responses(404)
)
def add_hidden_tag(
    tag_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Hide a tag from the current student's recommendations."""
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Eticheta nu există.")

    existing = (
        db.query(models.user_hidden_tags.c.user_id)
        .filter(models.user_hidden_tags.c.user_id == current_user.id, models.user_hidden_tags.c.tag_id == tag_id)
        .first()
    )
    if existing:
        return {"status": "exists"}

    db.execute(models.user_hidden_tags.insert().values(user_id=current_user.id, tag_id=tag_id))
    _audit_log(
        db,
        entity_type="user",
        entity_id=current_user.id,
        action="hide_tag",
        actor_user_id=current_user.id,
        meta={"tag_id": tag_id},
    )
    db.commit()
    return {"status": "hidden"}


@app.delete(
    "/api/me/personalization/hidden-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_responses(404)
)
def remove_hidden_tag(
    tag_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Remove a hidden tag from the current student's recommendations."""
    result = db.execute(
        models.user_hidden_tags.delete().where(
            (models.user_hidden_tags.c.user_id == current_user.id) & (models.user_hidden_tags.c.tag_id == tag_id)
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Eticheta nu este ascunsă.")
    _audit_log(
        db,
        entity_type="user",
        entity_id=current_user.id,
        action="unhide_tag",
        actor_user_id=current_user.id,
        meta={"tag_id": tag_id},
    )
    db.commit()


@app.post(
    "/api/me/personalization/blocked-organizers/{organizer_id}",
    status_code=status.HTTP_201_CREATED,
    responses=_responses(404),
)
def add_blocked_organizer(
    organizer_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Block an organizer in the current student's recommendations."""
    organizer = db.query(models.User).filter(models.User.id == organizer_id).first()
    if not organizer or organizer.role not in {models.UserRole.organizator, models.UserRole.admin}:
        raise HTTPException(status_code=404, detail="Organizatorul nu există.")

    existing = (
        db.query(models.user_blocked_organizers.c.user_id)
        .filter(
            models.user_blocked_organizers.c.user_id == current_user.id,
            models.user_blocked_organizers.c.organizer_id == organizer_id,
        )
        .first()
    )
    if existing:
        return {"status": "exists"}

    db.execute(models.user_blocked_organizers.insert().values(user_id=current_user.id, organizer_id=organizer_id))
    _audit_log(
        db,
        entity_type="user",
        entity_id=current_user.id,
        action="block_organizer",
        actor_user_id=current_user.id,
        meta={"organizer_id": organizer_id},
    )
    db.commit()
    return {"status": "blocked"}


@app.delete(
    "/api/me/personalization/blocked-organizers/{organizer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_responses(404),
)
def remove_blocked_organizer(
    organizer_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Unblock an organizer in the current student's recommendations."""
    result = db.execute(
        models.user_blocked_organizers.delete().where(
            (models.user_blocked_organizers.c.user_id == current_user.id)
            & (models.user_blocked_organizers.c.organizer_id == organizer_id)
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Organizatorul nu este blocat.")
    _audit_log(
        db,
        entity_type="user",
        entity_id=current_user.id,
        action="unblock_organizer",
        actor_user_id=current_user.id,
        meta={"organizer_id": organizer_id},
    )
    db.commit()


# ===================== NOTIFICATION PREFERENCES =====================


@app.get("/api/me/notifications", response_model=schemas.NotificationPreferencesResponse)
def get_notification_preferences(
    db: DbSession,
    current_user: StudentUser,
):
    """Return the current student's notification preferences."""
    return {
        "email_digest_enabled": getattr(current_user, "email_digest_enabled", False),
        "email_filling_fast_enabled": getattr(current_user, "email_filling_fast_enabled", False),
    }


@app.put("/api/me/notifications", response_model=schemas.NotificationPreferencesResponse)
def update_notification_preferences(
    payload: schemas.NotificationPreferencesUpdate,
    db: DbSession,
    current_user: StudentUser,
):
    """Update the current student's notification preferences."""
    updates: dict[str, bool] = {}
    if payload.email_digest_enabled is not None:
        current_user.email_digest_enabled = bool(payload.email_digest_enabled)
        updates["email_digest_enabled"] = bool(payload.email_digest_enabled)
    if payload.email_filling_fast_enabled is not None:
        current_user.email_filling_fast_enabled = bool(payload.email_filling_fast_enabled)
        updates["email_filling_fast_enabled"] = bool(payload.email_filling_fast_enabled)

    db.add(current_user)
    _audit_log(
        db,
        entity_type="user",
        entity_id=current_user.id,
        action="notification_preferences_updated",
        actor_user_id=current_user.id,
        meta=updates or None,
    )
    db.commit()
    db.refresh(current_user)
    return {
        "email_digest_enabled": current_user.email_digest_enabled,
        "email_filling_fast_enabled": current_user.email_filling_fast_enabled,
    }


def _serialize_event_for_export(event: models.Event) -> dict:
    start_time = _normalize_dt(event.start_time)
    end_time = _normalize_dt(event.end_time)
    publish_at = _normalize_dt(event.publish_at)
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "category": event.category,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "city": event.city,
        "location": event.location,
        "max_seats": event.max_seats,
        "cover_url": event.cover_url,
        "status": event.status,
        "publish_at": publish_at.isoformat() if publish_at else None,
        "owner_id": event.owner_id,
        "tags": [t.name for t in (event.tags or [])],
        "created_at": _normalize_dt(event.created_at).isoformat() if event.created_at else None,
    }


def _user_export_payload(user: models.User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "full_name": user.full_name,
        "theme_preference": user.theme_preference,
        "city": user.city,
        "university": user.university,
        "faculty": user.faculty,
        "study_level": user.study_level,
        "study_year": user.study_year,
        "org_name": user.org_name,
        "org_description": user.org_description,
        "org_logo_url": user.org_logo_url,
        "org_website": user.org_website,
        "interest_tags": [{"id": t.id, "name": t.name} for t in user.interest_tags],
    }


def _registration_export_rows(rows: list[tuple[models.Registration, models.Event]]) -> list[dict[str, object]]:
    return [
        {
            "registration_time": _normalize_dt(reg.registration_time).isoformat() if reg.registration_time else None,
            "attended": bool(reg.attended),
            "event": _serialize_event_for_export(ev),
        }
        for reg, ev in rows
    ]


def _favorite_export_rows(rows: list[tuple[models.FavoriteEvent, models.Event]]) -> list[dict[str, object]]:
    return [
        {
            "favorited_at": _normalize_dt(fav.created_at).isoformat() if fav.created_at else None,
            "event": _serialize_event_for_export(ev),
        }
        for fav, ev in rows
    ]


def _organized_event_export_rows(*, db: Session, current_user: models.User) -> list[dict[str, object]]:
    events = (
        db.query(models.Event)
        .filter(models.Event.owner_id == current_user.id)
        .order_by(models.Event.start_time.desc())
        .all()
    )
    event_ids = [e.id for e in events]
    if not event_ids:
        return []
    reg_counts = dict(
        db.query(models.Registration.event_id, func.count(models.Registration.id))
        .filter(models.Registration.event_id.in_(event_ids))
        .group_by(models.Registration.event_id)
        .all()
    )
    fav_counts = dict(
        db.query(models.FavoriteEvent.event_id, func.count(models.FavoriteEvent.id))
        .filter(models.FavoriteEvent.event_id.in_(event_ids))
        .group_by(models.FavoriteEvent.event_id)
        .all()
    )
    return [
        {
            **_serialize_event_for_export(ev),
            "registrations_count": int(reg_counts.get(ev.id, 0)),
            "favorites_count": int(fav_counts.get(ev.id, 0)),
        }
        for ev in events
    ]


@app.get("/api/me/export", responses=_responses(400))
def export_my_data(
    *,
    db: DbSession,
    current_user: CurrentUser,
):
    """Export the current user's account data."""
    exported_at = datetime.now(timezone.utc)

    registrations = (
        db.query(models.Registration, models.Event)
        .join(models.Event, models.Event.id == models.Registration.event_id)
        .filter(models.Registration.user_id == current_user.id)
        .order_by(models.Registration.registration_time.desc())
        .all()
    )
    favorites = (
        db.query(models.FavoriteEvent, models.Event)
        .join(models.Event, models.Event.id == models.FavoriteEvent.event_id)
        .filter(models.FavoriteEvent.user_id == current_user.id)
        .order_by(models.FavoriteEvent.created_at.desc())
        .all()
    )

    export_payload: dict = {
        "exported_at": exported_at.isoformat(),
        "user": _user_export_payload(current_user),
        "registrations": _registration_export_rows(registrations),
        "favorites": _favorite_export_rows(favorites),
    }

    if current_user.role == models.UserRole.organizator:
        export_payload["organized_events"] = _organized_event_export_rows(db=db, current_user=current_user)

    filename_date = exported_at.strftime("%Y%m%d")
    headers = {"Content-Disposition": f'attachment; filename="eventlink-export-{filename_date}.json"'}
    return JSONResponse(content=export_payload, headers=headers)


def _deleted_organizer_placeholder(*, db: Session):
    deleted_organizer_email = "deleted-organizer@eventlink.invalid"
    placeholder = db.query(models.User).filter(func.lower(models.User.email) == deleted_organizer_email).first()
    if placeholder:
        return placeholder
    placeholder = models.User(
        email=deleted_organizer_email,
        password_hash=auth.get_password_hash(secrets.token_urlsafe(32)),
        role=models.UserRole.organizator,
        full_name="Organizator șters",
        org_name="Organizator șters",
        org_description=None,
        org_logo_url=None,
        org_website=None,
    )
    db.add(placeholder)
    db.commit()
    db.refresh(placeholder)
    return placeholder


def _delete_user_relations(*, db: Session, user_id: int) -> None:
    db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(models.Registration).filter(models.Registration.user_id == user_id).delete(synchronize_session=False)
    db.query(models.FavoriteEvent).filter(models.FavoriteEvent.user_id == user_id).delete(synchronize_session=False)
    db.execute(models.user_interest_tags.delete().where(models.user_interest_tags.c.user_id == user_id))


@app.delete("/api/me", responses=_responses(403, 404))
def delete_my_account(
    payload: schemas.AccountDeleteRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete the current user's account and personal data."""
    if not auth.verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Parolă incorectă.")

    deleted_user_id = current_user.id
    deleted_role = current_user.role

    deleted_organizer_email = "deleted-organizer@eventlink.invalid"
    if current_user.email.lower() == deleted_organizer_email:
        raise HTTPException(status_code=400, detail="Acest cont nu poate fi șters.")

    if deleted_role == models.UserRole.organizator:
        placeholder = _deleted_organizer_placeholder(db=db)
        db.query(models.Event).filter(models.Event.owner_id == current_user.id).update(
            {"owner_id": placeholder.id},
            synchronize_session=False,
        )

    _delete_user_relations(db=db, user_id=current_user.id)
    db.delete(current_user)
    db.commit()
    log_event("account_deleted", user_id=deleted_user_id, role=str(deleted_role))
    return {"status": "deleted"}


def _participant_sort_column(sort_by: str):
    if sort_by == "email":
        return models.User.email
    if sort_by == "name":
        return models.User.full_name
    return models.Registration.registration_time


def _participant_response_items(
    rows: list[tuple[models.User, datetime | None, bool | None]],
) -> list[schemas.ParticipantResponse]:
    return [
        schemas.ParticipantResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            registration_time=reg_time,
            attended=attended,
        )
        for user, reg_time, attended in rows
    ]


@app.get(
    "/api/organizer/events/{event_id}/participants",
    response_model=schemas.ParticipantListResponse,
    responses=_responses(403, 404),
)
def event_participants(
    event_id: int,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "registration_time",
    sort_dir: str = "asc",
    *,
    db: DbSession,
    current_user: OrganizerUser,
):
    """List participants for an organizer event."""
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să accesați acest eveniment.")

    sort_column = _participant_sort_column(sort_by)
    order_clause = sort_column.asc() if sort_dir.lower() != "desc" else sort_column.desc()

    base_query = (
        db.query(models.User, models.Registration.registration_time, models.Registration.attended)
        .join(models.Registration, models.User.id == models.Registration.user_id)
        .filter(models.Registration.event_id == event_id, models.Registration.deleted_at.is_(None))
    )
    total = base_query.count()
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))
    participants = base_query.order_by(order_clause).offset((page - 1) * page_size).limit(page_size).all()
    participant_list = _participant_response_items(participants)
    seats_taken = total
    return schemas.ParticipantListResponse(
        event_id=event.id,
        title=event.title,
        cover_url=event.cover_url,
        seats_taken=seats_taken,
        max_seats=event.max_seats,
        city=event.city,
        participants=participant_list,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.put(
    "/api/organizer/events/{event_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_responses(400, 404),
)
def update_participant_attendance(
    event_id: int,
    user_id: int,
    attended: bool,
    db: DbSession,
    current_user: OrganizerUser,
):
    """Update attendance for an event participant."""
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    if event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați acest eveniment.")

    registration = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == user_id,
            models.Registration.deleted_at.is_(None),
        )
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Participarea nu a fost găsită.")

    registration.attended = attended
    db.add(registration)
    db.commit()
    log_event(
        "attendance_updated",
        event_id=registration.event_id,
        user_id=user_id,
        owner_id=event.owner_id,
        actor_user_id=current_user.id,
        attended=attended,
    )


@app.post("/api/events/{event_id}/register", status_code=status.HTTP_201_CREATED, responses=_responses(400, 404))
def register_for_event(
    event_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
    current_user: StudentUser,
):
    """Register the current student for an event."""
    _ensure_registrations_enabled()
    now = datetime.now(timezone.utc)
    event, _seats_taken = _load_registerable_event(db=db, event_id=event_id, now=now)
    if _restore_registration_if_deleted(db=db, event=event, event_id=event_id, current_user=current_user):
        return {"status": "registered"}

    registration = models.Registration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    db.commit()
    log_event("event_registered", event_id=event.id, user_id=current_user.id)
    _queue_registration_email(
        background_tasks=background_tasks,
        request=request,
        db=db,
        event=event,
        current_user=current_user,
    )
    return {"status": "registered"}


@app.post("/api/events/{event_id}/register/resend", status_code=status.HTTP_200_OK, responses=_responses(400, 404))
def resend_registration_email(
    event_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
    current_user: StudentUser,
):
    """Resend the registration email for an event."""
    _ensure_registrations_enabled()
    _enforce_rate_limit(
        "resend_registration", request=request, identifier=current_user.email.lower(), limit=3, window_seconds=600
    )
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    registration = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == current_user.id,
            models.Registration.deleted_at.is_(None),
        )
        .first()
    )
    if not registration:
        raise HTTPException(status_code=400, detail="Nu ești înscris la acest eveniment.")

    lang = current_user.language_preference
    if not lang or lang == "system":
        lang = request.headers.get("accept-language") or "ro"
    subject, body_text, body_html = render_registration_email(event, current_user, lang=lang)
    send_email_async(
        background_tasks,
        db,
        current_user.email,
        subject,
        body_text,
        body_html,
        context={"user_id": current_user.id, "event_id": event.id, "lang": lang, "resend": True},
    )
    return {"status": "resent"}


@app.delete("/api/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT, responses=_responses(403, 404))
def unregister_from_event(
    event_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Cancel the current student's registration for an event."""
    _ensure_registrations_enabled()
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    now = datetime.now(timezone.utc)
    start_time = _normalize_dt(event.start_time)
    if start_time and start_time < now:
        raise HTTPException(status_code=400, detail="Nu te poți dezabona după ce evenimentul a început.")

    registration = (
        db.query(models.Registration)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.user_id == current_user.id,
            models.Registration.deleted_at.is_(None),
        )
        .first()
    )
    if not registration:
        raise HTTPException(status_code=400, detail="Nu ești înscris la acest eveniment.")

    registration.deleted_at = datetime.now(timezone.utc)
    registration.deleted_by_user_id = current_user.id
    db.add(registration)
    _audit_log(
        db,
        entity_type="registration",
        entity_id=registration.id,
        action="soft_deleted",
        actor_user_id=current_user.id,
        meta={"event_id": event.id, "reason": "unregistered"},
    )
    db.commit()
    log_event("event_unregistered", event_id=event.id, user_id=current_user.id)


@app.post("/api/admin/events/{event_id}/registrations/{user_id}/restore", responses=_responses(400))
def admin_restore_registration(
    event_id: int,
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Restore a deleted registration as an admin."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Acces doar pentru administratori.")

    registration = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == user_id)
        .first()
    )
    if not registration or registration.deleted_at is None:
        raise HTTPException(status_code=404, detail="Participarea nu există.")

    registration.deleted_at = None
    registration.deleted_by_user_id = None
    db.add(registration)
    _audit_log(
        db,
        entity_type="registration",
        entity_id=registration.id,
        action="restored",
        actor_user_id=current_user.id,
        meta={"event_id": event_id, "user_id": user_id, "reason": "admin_restore"},
    )
    db.commit()
    log_event("registration_restored", event_id=event_id, user_id=user_id, actor_user_id=current_user.id)
    return {"status": "restored"}


def _validate_admin_days(days: int) -> None:
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="`days` trebuie să fie între 1 și 365.")


def _validate_top_tags_limit(top_tags_limit: int) -> None:
    if top_tags_limit < 1 or top_tags_limit > 100:
        raise HTTPException(status_code=400, detail="`top_tags_limit` trebuie să fie între 1 și 100.")


def _registration_stats_by_day(*, db: Session, start: datetime) -> list[schemas.RegistrationDayStat]:
    rows = (
        db.query(
            func.date(models.Registration.registration_time).label("day"),
            func.count(models.Registration.id).label("registrations"),
        )
        .filter(models.Registration.deleted_at.is_(None), models.Registration.registration_time >= start)
        .group_by("day")
        .order_by("day")
        .all()
    )
    return [schemas.RegistrationDayStat(date=str(row.day), registrations=int(row.registrations or 0)) for row in rows]


def _top_tag_stats(*, db: Session, top_tags_limit: int) -> list[schemas.TagPopularityStat]:
    rows = (
        db.query(
            models.Tag.name.label("name"),
            func.count(models.Registration.id).label("registrations"),
            func.count(func.distinct(models.Event.id)).label("events"),
        )
        .select_from(models.Tag)
        .join(models.event_tags, models.Tag.id == models.event_tags.c.tag_id)
        .join(models.Event, models.Event.id == models.event_tags.c.event_id)
        .outerjoin(
            models.Registration,
            (models.Registration.event_id == models.Event.id) & (models.Registration.deleted_at.is_(None)),
        )
        .filter(models.Event.deleted_at.is_(None))
        .group_by(models.Tag.id, models.Tag.name)
        .order_by(func.count(models.Registration.id).desc(), func.count(func.distinct(models.Event.id)).desc())
        .limit(top_tags_limit)
        .all()
    )
    return [
        schemas.TagPopularityStat(
            name=row.name,
            registrations=int(row.registrations or 0),
            events=int(row.events or 0),
        )
        for row in rows
    ]


@app.get("/api/admin/stats", response_model=schemas.AdminStatsResponse, responses=_responses(400))
def admin_stats(
    days: int = 30,
    top_tags_limit: int = 10,
    *,
    db: DbSession,
    current_user: AdminUser,
):
    """Return admin dashboard statistics."""
    _validate_admin_days(days)
    _validate_top_tags_limit(top_tags_limit)

    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_events = db.query(func.count(models.Event.id)).filter(models.Event.deleted_at.is_(None)).scalar() or 0
    total_registrations = (
        db.query(func.count(models.Registration.id)).filter(models.Registration.deleted_at.is_(None)).scalar() or 0
    )

    start = datetime.now(timezone.utc) - timedelta(days=days)
    return {
        "total_users": int(total_users),
        "total_events": int(total_events),
        "total_registrations": int(total_registrations),
        "registrations_by_day": _registration_stats_by_day(db=db, start=start),
        "top_tags": _top_tag_stats(db=db, top_tags_limit=top_tags_limit),
    }


def _personalization_metric_counts_by_day(*, db: Session, start: datetime) -> dict[str, dict[str, int]]:
    rows = (
        db.query(
            func.date(models.EventInteraction.occurred_at).label("day"),
            models.EventInteraction.interaction_type.label("type"),
            func.count(models.EventInteraction.id).label("count"),
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.interaction_type.in_(["impression", "click", "register"]))
        .group_by("day", "type")
        .order_by("day")
        .all()
    )
    by_day: dict[str, dict[str, int]] = {}
    for day, interaction_type, count in rows:
        bucket = by_day.setdefault(str(day), {"impression": 0, "click": 0, "register": 0})
        bucket[str(interaction_type)] = int(count or 0)
    return by_day


def _personalization_metrics_items(
    by_day: dict[str, dict[str, int]],
) -> tuple[list[schemas.PersonalizationMetricsDay], int, int, int]:
    items: list[schemas.PersonalizationMetricsDay] = []
    total_impressions = 0
    total_clicks = 0
    total_registrations = 0
    for day in sorted(by_day.keys()):
        impressions = int(by_day[day].get("impression", 0))
        clicks = int(by_day[day].get("click", 0))
        registrations = int(by_day[day].get("register", 0))
        total_impressions += impressions
        total_clicks += clicks
        total_registrations += registrations
        items.append(
            schemas.PersonalizationMetricsDay(
                date=day,
                impressions=impressions,
                clicks=clicks,
                registrations=registrations,
                ctr=(clicks / impressions) if impressions else 0.0,
                registration_conversion=(registrations / clicks) if clicks else 0.0,
            )
        )
    return items, total_impressions, total_clicks, total_registrations


@app.get(
    "/api/admin/personalization/metrics",
    response_model=schemas.PersonalizationMetricsResponse,
    responses=_responses(400),
)
def admin_personalization_metrics(
    days: int = 30,
    *,
    db: DbSession,
    current_user: AdminUser,
):
    """Return admin personalization metrics."""
    _validate_admin_days(days)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    by_day = _personalization_metric_counts_by_day(db=db, start=start)
    items, total_impressions, total_clicks, total_registrations = _personalization_metrics_items(by_day)
    totals_ctr = (total_clicks / total_impressions) if total_impressions else 0.0
    totals_conversion = (total_registrations / total_clicks) if total_clicks else 0.0
    return {
        "items": items,
        "totals": {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "registrations": total_registrations,
            "ctr": totals_ctr,
            "registration_conversion": totals_conversion,
        },
    }


@app.get("/api/admin/personalization/status", response_model=schemas.AdminPersonalizationStatusResponse)
def admin_personalization_status(
    db: DbSession,
    current_user: AdminUser,
):
    """Return the current personalization system status."""
    active = (
        db.query(models.RecommenderModel)
        .filter(getattr(models.RecommenderModel, "is_active").is_(True))
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    return {
        "task_queue_enabled": bool(settings.task_queue_enabled),
        "recommendations_realtime_refresh_enabled": bool(settings.recommendations_realtime_refresh_enabled),
        "recommendations_online_learning_enabled": bool(settings.recommendations_online_learning_enabled),
        "active_model_version": str(active.model_version) if active else None,
        "active_model_created_at": active.created_at if active else None,
    }


@app.post(
    "/api/admin/personalization/guardrails/evaluate",
    response_model=schemas.EnqueuedJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_responses(404),
)
def admin_enqueue_guardrails_evaluate(
    payload: schemas.AdminEvaluateGuardrailsRequest,
    db: DbSession,
    current_user: AdminUser,
):
    """Queue a personalization guardrail evaluation job."""
    from .task_queue import enqueue_job, JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS  # noqa: PLC0415

    job = enqueue_job(
        db,
        JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS,
        payload.model_dump(exclude_none=True),
        dedupe_key="global",
    )
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.post(
    "/api/admin/personalization/models/activate",
    response_model=schemas.AdminActivatePersonalizationModelResponse,
    responses=_responses(404),
)
def admin_activate_personalization_model(
    payload: schemas.AdminActivatePersonalizationModelRequest,
    db: DbSession,
    current_user: AdminUser,
):
    """Activate a saved personalization model."""
    model = (
        db.query(models.RecommenderModel).filter(models.RecommenderModel.model_version == payload.model_version).first()
    )
    if not model:
        raise HTTPException(status_code=404, detail="Modelul nu există.")

    db.query(models.RecommenderModel).update({"is_active": False}, synchronize_session=False)
    setattr(model, "is_active", True)
    db.add(model)
    db.commit()

    recompute_job = None
    if payload.recompute:
        from .task_queue import enqueue_job, JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML  # noqa: PLC0415

        job = enqueue_job(
            db,
            JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
            {"top_n": int(payload.top_n), "skip_training": True},
            dedupe_key="global",
        )
        recompute_job = {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}

    return {"active_model_version": str(model.model_version), "recompute_job": recompute_job}


@app.post(
    "/api/admin/personalization/retrain",
    response_model=schemas.EnqueuedJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_enqueue_retrain_recommendations(
    payload: schemas.AdminRetrainRecommendationsRequest,
    db: DbSession,
    current_user: AdminUser,
):
    """Queue a recommendation retraining job."""
    from .task_queue import enqueue_job, JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML  # noqa: PLC0415

    job = enqueue_job(
        db,
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        payload.model_dump(exclude_none=True),
        dedupe_key="global",
    )
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.post(
    "/api/admin/notifications/weekly-digest",
    response_model=schemas.EnqueuedJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_responses(400),
)
def admin_enqueue_weekly_digest(
    payload: schemas.AdminWeeklyDigestRequest,
    db: DbSession,
    current_user: AdminUser,
):
    """Queue the weekly digest notification job."""
    from .task_queue import enqueue_job, JOB_TYPE_SEND_WEEKLY_DIGEST  # noqa: PLC0415

    job = enqueue_job(db, JOB_TYPE_SEND_WEEKLY_DIGEST, payload.model_dump(exclude_none=True), dedupe_key="global")
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.post(
    "/api/admin/notifications/filling-fast",
    response_model=schemas.EnqueuedJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_responses(400),
)
def admin_enqueue_filling_fast(
    payload: schemas.AdminFillingFastRequest,
    db: DbSession,
    current_user: AdminUser,
):
    """Queue the filling-fast notification job."""
    from .task_queue import enqueue_job, JOB_TYPE_SEND_FILLING_FAST_ALERTS  # noqa: PLC0415

    job = enqueue_job(db, JOB_TYPE_SEND_FILLING_FAST_ALERTS, payload.model_dump(exclude_none=True), dedupe_key="global")
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


def _validate_admin_user_pagination(page: int, page_size: int) -> None:
    if page < 1:
        raise HTTPException(status_code=400, detail=_MIN_PAGE_DETAIL)
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail=_PAGE_SIZE_DETAIL)


def _admin_user_filters(
    *,
    search: str | None,
    role: models.UserRole | None,
    is_active: bool | None,
) -> list[object]:
    filters: list[object] = []
    if search:
        needle = f"%{search.strip().lower()}%"
        filters.append(
            (func.lower(models.User.email).like(needle))
            | (func.lower(models.User.full_name).like(needle))
            | (func.lower(models.User.org_name).like(needle))
        )
    if role:
        filters.append(models.User.role == role)
    if is_active is not None:
        filters.append(getattr(models.User, "is_active") == is_active)
    return filters


def _admin_user_count_subqueries(db: Session):
    reg_counts = (
        db.query(
            models.Registration.user_id.label("user_id"),
            func.count(models.Registration.id).label("registrations_count"),
            func.coalesce(
                func.sum(case((models.Registration.attended.is_(True), 1), else_=0)),
                0,
            ).label("attended_count"),
        )
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.user_id)
        .subquery()
    )
    events_counts = (
        db.query(
            models.Event.owner_id.label("user_id"),
            func.count(models.Event.id).label("events_created_count"),
        )
        .filter(models.Event.deleted_at.is_(None))
        .group_by(models.Event.owner_id)
        .subquery()
    )
    return reg_counts, events_counts


def _admin_user_response_from_row(row: tuple[models.User, int, int, int]) -> schemas.AdminUserResponse:
    user, registrations_count, attended_count, events_created_count = row
    return schemas.AdminUserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        org_name=user.org_name,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        is_active=bool(getattr(user, "is_active")),
        registrations_count=int(registrations_count or 0),
        attended_count=int(attended_count or 0),
        events_created_count=int(events_created_count or 0),
    )


def _admin_user_rows_query(
    *,
    db: Session,
    reg_counts,
    events_counts,
):
    return (
        db.query(
            models.User,
            func.coalesce(reg_counts.c.registrations_count, 0).label("registrations_count"),
            func.coalesce(reg_counts.c.attended_count, 0).label("attended_count"),
            func.coalesce(events_counts.c.events_created_count, 0).label("events_created_count"),
        )
        .outerjoin(reg_counts, reg_counts.c.user_id == models.User.id)
        .outerjoin(events_counts, events_counts.c.user_id == models.User.id)
    )


@app.get("/api/admin/users", response_model=schemas.PaginatedAdminUsers, responses=_responses(404))
def admin_list_users(
    search: Optional[str] = None,
    role: Optional[models.UserRole] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    *,
    db: DbSession,
    current_user: AdminUser,
):
    """List users for the admin dashboard."""
    _validate_admin_user_pagination(page, page_size)
    filters = _admin_user_filters(search=search, role=role, is_active=is_active)

    total = db.query(func.count(models.User.id)).filter(*filters).scalar() or 0
    reg_counts, events_counts = _admin_user_count_subqueries(db)
    rows = (
        _admin_user_rows_query(db=db, reg_counts=reg_counts, events_counts=events_counts)
        .filter(*filters)
        .order_by(models.User.created_at.desc(), models.User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_admin_user_response_from_row(row) for row in rows]

    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


def _apply_admin_user_patch(*, user: models.User, payload: schemas.AdminUserUpdate) -> bool:
    changed = False
    if payload.role is not None:
        user.role = payload.role
        changed = True
    payload_is_active = getattr(payload, "is_active")
    if payload_is_active is not None:
        setattr(user, "is_active", payload_is_active)
        changed = True
    return changed


@app.patch("/api/admin/users/{user_id}", response_model=schemas.AdminUserResponse, responses=_responses(400))
def admin_update_user(
    user_id: int,
    payload: schemas.AdminUserUpdate,
    db: DbSession,
    current_user: AdminUser,
):
    """Update a user's admin-managed fields."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu există.")

    changed = _apply_admin_user_patch(user=user, payload=payload)
    if changed:
        db.add(user)
        db.commit()
        db.refresh(user)
        _audit_log(
            db,
            entity_type="user",
            entity_id=user.id,
            action="admin_update",
            actor_user_id=current_user.id,
            meta={"role": user.role.value, "is_active": bool(getattr(user, "is_active"))},
        )
        db.commit()

    reg_counts, events_counts = _admin_user_count_subqueries(db)
    row = (
        _admin_user_rows_query(db=db, reg_counts=reg_counts, events_counts=events_counts)
        .filter(models.User.id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Utilizatorul nu există.")
    return _admin_user_response_from_row(row)


def _validate_admin_event_status(status_value: str | None) -> None:
    if status_value and status_value not in {"draft", "published"}:
        raise HTTPException(status_code=400, detail="Status invalid.")


def _apply_admin_event_filters(
    query,
    *,
    search: str | None,
    category: str | None,
    city: str | None,
    status_value: str | None,
    include_deleted: bool,
    flagged_only: bool,
):  # noqa: ANN001
    if not include_deleted:
        query = query.filter(models.Event.deleted_at.is_(None))
    if flagged_only:
        query = query.filter(models.Event.moderation_status == "flagged")
    if status_value:
        query = query.filter(models.Event.status == status_value)
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    if city:
        query = query.filter(func.lower(models.Event.city).like(f"%{city.lower()}%"))
    if search:
        needle = f"%{search.strip().lower()}%"
        query = query.join(models.Event.owner).filter(
            (func.lower(models.Event.title).like(needle))
            | (func.lower(models.User.email).like(needle))
            | (func.lower(models.User.org_name).like(needle))
        )
    return query


def _admin_event_list_filters(
    search: Optional[str] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    flagged_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> schemas.AdminEventListQuery:
    return schemas.AdminEventListQuery(
        search=search,
        category=category,
        city=city,
        status=status,
        include_deleted=include_deleted,
        flagged_only=flagged_only,
        page=page,
        page_size=page_size,
    )


@app.get("/api/admin/events", response_model=schemas.PaginatedAdminEvents, responses=_responses(404))
def admin_list_events(
    filters: Annotated[schemas.AdminEventListQuery, Depends(_admin_event_list_filters)],
    *,
    db: DbSession,
    current_user: AdminUser,
):
    """List events for the admin dashboard."""
    _validate_admin_user_pagination(filters.page, filters.page_size)
    _validate_admin_event_status(filters.status)

    query = db.query(models.Event).options(joinedload(models.Event.owner), joinedload(models.Event.tags))
    query = _apply_admin_event_filters(
        query,
        search=filters.search,
        category=filters.category,
        city=filters.city,
        status_value=filters.status,
        include_deleted=filters.include_deleted,
        flagged_only=filters.flagged_only,
    )

    total = query.count()

    query = query.order_by(models.Event.start_time.desc(), models.Event.id.desc())
    query, _ = _events_with_counts_query(db, query)
    rows = query.offset((filters.page - 1) * filters.page_size).limit(filters.page_size).all()

    items = [_serialize_admin_event(event, seats_taken) for event, seats_taken in rows]
    return {"items": items, "total": int(total), "page": filters.page, "page_size": filters.page_size}


@app.post("/api/admin/events/{event_id}/moderation/review", responses=_responses(404))
def admin_review_event_moderation(
    event_id: int,
    db: DbSession,
    current_user: AdminUser,
):
    """Mark an event moderation review as completed."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există.")

    now = datetime.now(timezone.utc)
    event.moderation_status = "reviewed"
    event.moderation_reviewed_at = now
    event.moderation_reviewed_by_user_id = current_user.id
    db.add(event)
    _audit_log(
        db,
        entity_type="event",
        entity_id=event.id,
        action="moderation_reviewed",
        actor_user_id=current_user.id,
        meta={"moderation_score": float(getattr(event, "moderation_score", 0.0) or 0.0)},
    )
    db.commit()
    return {"status": "reviewed"}


@app.post("/api/events/{event_id}/favorite", status_code=status.HTTP_201_CREATED, responses=_responses(404))
def favorite_event(
    event_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Favorite an event for the current student."""
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    existing = (
        db.query(models.FavoriteEvent)
        .filter(models.FavoriteEvent.event_id == event_id, models.FavoriteEvent.user_id == current_user.id)
        .first()
    )
    if existing:
        return {"status": "exists"}
    fav = models.FavoriteEvent(user_id=current_user.id, event_id=event_id)
    db.add(fav)
    db.commit()
    return {"status": "added"}


@app.delete("/api/events/{event_id}/favorite", status_code=status.HTTP_204_NO_CONTENT, responses=_responses(404))
def unfavorite_event(
    event_id: int,
    db: DbSession,
    current_user: StudentUser,
):
    """Remove an event from the current student's favorites."""
    fav = (
        db.query(models.FavoriteEvent)
        .filter(models.FavoriteEvent.event_id == event_id, models.FavoriteEvent.user_id == current_user.id)
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favoritul nu există")
    db.delete(fav)
    db.commit()


@app.get("/api/me/favorites", response_model=schemas.FavoriteListResponse)
def list_favorites(db: DbSession, current_user: StudentUser):
    """List the current student's favorite events."""
    base_query = (
        db.query(models.Event)
        .join(models.FavoriteEvent, models.Event.id == models.FavoriteEvent.event_id)
        .filter(models.FavoriteEvent.user_id == current_user.id)
    )
    now = datetime.now(timezone.utc)
    base_query = base_query.filter(
        models.Event.deleted_at.is_(None),
        models.Event.status == "published",
        (models.Event.publish_at == None) | (models.Event.publish_at <= now),  # noqa: E711
    )
    query, _ = _events_with_counts_query(db, base_query)
    items = [_serialize_event(ev, seats) for ev, seats in query.order_by(models.Event.start_time).all()]
    return {"items": items}


@app.get("/api/me/events", response_model=List[schemas.EventResponse])
def my_events(db: DbSession, current_user: CurrentUser):
    # Allow both students and organizers to see events they registered for
    """List the events associated with the current user."""
    base_query = (
        db.query(models.Event)
        .join(models.Registration, models.Event.id == models.Registration.event_id)
        .filter(
            models.Event.deleted_at.is_(None),
            models.Registration.user_id == current_user.id,
            models.Registration.deleted_at.is_(None),
        )
        .order_by(models.Event.start_time)
    )
    query, _ = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


def _registered_event_ids(*, db: Session, user_id: int) -> list[int]:
    return [
        event_id
        for event_id, in db.query(models.Registration.event_id)
        .filter(models.Registration.user_id == user_id, models.Registration.deleted_at.is_(None))
        .all()
    ]


def _recommendation_history_tag_names(*, db: Session, user_id: int) -> list[str]:
    return [
        tag_name
        for tag_name, in (
            db.query(models.Tag.name)
            .join(models.event_tags, models.Tag.id == models.event_tags.c.tag_id)
            .join(models.Event, models.Event.id == models.event_tags.c.event_id)
            .join(models.Registration, models.Registration.event_id == models.Event.id)
            .filter(
                models.Registration.user_id == user_id,
                models.Registration.deleted_at.is_(None),
                models.Event.deleted_at.is_(None),
            )
            .all()
        )
    ]


def _recommendation_reason(
    *,
    history_tag_names: list[str],
    profile_tag_names: list[str],
    lang: str,
) -> str | None:
    reason_parts: list[str] = []
    if history_tag_names:
        tags = ", ".join(sorted(set(history_tag_names))[:3])
        reason_parts.append(f"Similar tags: {tags}" if lang == "en" else f"Etichete similare: {tags}")
    if profile_tag_names:
        tags = ", ".join(sorted(set(profile_tag_names))[:3])
        reason_parts.append(f"Your interests: {tags}" if lang == "en" else f"Interesele tale: {tags}")
    return " • ".join(reason_parts[:2]) if reason_parts else None


def _tag_based_recommendations(**kwargs) -> list[tuple[models.Event, int, Optional[str]]]:
    context = _tag_recommendation_context(kwargs)
    if context is None:
        return []
    base_query = _tag_recommendation_base_query(
        db=context["db"],
        match_tag_names=context["match_tag_names"],
        now=context["now"],
    )
    registered_event_ids = context["registered_event_ids"]
    if registered_event_ids:
        base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
    base_query = _apply_personalization_exclusions(
        base_query,
        hidden_tag_ids=context["hidden_tag_ids"],
        blocked_organizer_ids=context["blocked_organizer_ids"],
    )
    query, _ = _events_with_counts_query(context["db"], base_query.order_by(models.Event.start_time, models.Event.id))
    reason = _recommendation_reason(
        history_tag_names=context["history_tag_names"],
        profile_tag_names=context["profile_tag_names"],
        lang=context["lang"],
    )
    return [(event, seats, reason) for event, seats in query.limit(10).all()]


def _tag_recommendation_context(kwargs: dict[str, object]) -> dict[str, object] | None:
    match_tag_names = list(kwargs.get("match_tag_names") or [])
    if not match_tag_names:
        return None
    return {
        "db": kwargs["db"],
        "match_tag_names": match_tag_names,
        "registered_event_ids": list(kwargs.get("registered_event_ids") or []),
        "hidden_tag_ids": set(kwargs.get("hidden_tag_ids") or set()),
        "blocked_organizer_ids": set(kwargs.get("blocked_organizer_ids") or set()),
        "now": kwargs["now"],
        "lang": str(kwargs["lang"]),
        "history_tag_names": list(kwargs.get("history_tag_names") or []),
        "profile_tag_names": list(kwargs.get("profile_tag_names") or []),
    }


def _tag_recommendation_base_query(*, db: Session, match_tag_names: list[str], now: datetime):
    lowered_match_tags = [name.lower() for name in match_tag_names]
    return (
        db.query(models.Event)
        .filter(models.Event.tags.any(func.lower(models.Tag.name).in_(lowered_match_tags)))
        .filter(models.Event.deleted_at.is_(None))
        .filter(models.Event.start_time >= now)
        .filter(models.Event.status == "published")
        .filter((models.Event.publish_at == None) | (models.Event.publish_at <= now))  # noqa: E711
    )


def _popular_recommendations(
    *,
    db: Session,
    registered_event_ids: list[int],
    hidden_tag_ids: set[int],
    blocked_organizer_ids: set[int],
    now: datetime,
    lang: str,
) -> list[tuple[models.Event, int, Optional[str]]]:
    base_query = db.query(models.Event).filter(models.Event.deleted_at.is_(None), models.Event.start_time >= now)
    if registered_event_ids:
        base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
    base_query = _apply_personalization_exclusions(
        base_query,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
    )
    base_query = base_query.filter(models.Event.status == "published").filter(
        (models.Event.publish_at == None) | (models.Event.publish_at <= now)  # noqa: E711
    )
    query, seats_subquery = _events_with_counts_query(db, base_query)
    fallback_reason = "Popular / upcoming events" if lang == "en" else "Evenimente populare / viitoare"
    return [
        (event, seats, fallback_reason)
        for event, seats in query.order_by(
            func.coalesce(seats_subquery.c.seats_taken, 0).desc(),
            models.Event.start_time,
        )
        .limit(10)
        .all()
    ]


def _fallback_recommendations(
    *,
    db: Session,
    current_user: models.User,
    now: datetime,
    lang: str,
    registered_event_ids: list[int],
    hidden_tag_ids: set[int],
    blocked_organizer_ids: set[int],
) -> list[tuple[models.Event, int, Optional[str]]]:
    history_tag_names = _recommendation_history_tag_names(db=db, user_id=int(current_user.id))
    profile_tag_names = [tag.name for tag in current_user.interest_tags]
    match_tag_names = list(dict.fromkeys([*history_tag_names, *profile_tag_names]))
    events = _tag_based_recommendations(
        db=db,
        match_tag_names=match_tag_names,
        registered_event_ids=registered_event_ids,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
        now=now,
        lang=lang,
        history_tag_names=history_tag_names,
        profile_tag_names=profile_tag_names,
    )
    if events:
        return events
    return _popular_recommendations(
        db=db,
        registered_event_ids=registered_event_ids,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
        now=now,
        lang=lang,
    )


def _serialize_recommendations(
    *,
    events: list[tuple[models.Event, int, Optional[str]]],
    user_city: str,
    lang: str,
) -> list[schemas.EventResponse]:
    localized: list[tuple[bool, schemas.EventResponse]] = []
    for event, seats, reason in events:
        if event.max_seats is not None and seats >= event.max_seats:
            continue
        localized.append(
            (
                bool(user_city and event.city and event.city.strip().lower() == user_city),
                _serialize_event(
                    event,
                    seats,
                    recommendation_reason=_append_local_reason(
                        reason=reason,
                        event_city=event.city,
                        user_city=user_city,
                        lang=lang,
                    ),
                ),
            )
        )
    localized.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in localized[:10]]


@app.get("/api/recommendations", response_model=List[schemas.EventResponse], responses=_responses(404, 503))
def recommended_events(
    request: Request,
    db: DbSession,
    current_user: StudentUser,
):
    """Return personalized event recommendations."""
    lang = _preferred_lang(request=request, user=current_user)
    now = datetime.now(timezone.utc)
    user_city = _normalized_user_city(current_user)
    registered_event_ids = _registered_event_ids(db=db, user_id=int(current_user.id))
    hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=current_user.id)
    events = _load_cached_recommendations(
        db=db,
        user=current_user,
        now=now,
        registered_event_ids=registered_event_ids,
        lang=lang,
    )

    if not events:
        events = _fallback_recommendations(
            db=db,
            current_user=current_user,
            now=now,
            lang=lang,
            registered_event_ids=registered_event_ids,
            hidden_tag_ids=hidden_tag_ids,
            blocked_organizer_ids=blocked_organizer_ids,
        )

    return _serialize_recommendations(events=events, user_city=user_city, lang=lang)


@app.get("/api/health", responses=_responses(503))
def health_check(db: DbSession):
    """Report API health and database availability."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/events/{event_id}/ics", responses=_responses(404))
def event_ics(event_id: int, db: DbSession):
    """Return an ICS calendar entry for an event."""
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail=_EVENT_NOT_FOUND_DETAIL)
    ics = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//EventLink//EN",
            _event_to_ics(event),
            "END:VCALENDAR",
        ]
    )
    return Response(content=ics, media_type="text/calendar")


@app.get("/api/me/calendar")
def user_calendar(db: DbSession, current_user: CurrentUser):
    """Return an ICS calendar containing the current user's events."""
    regs = (
        db.query(models.Event)
        .join(models.Registration, models.Registration.event_id == models.Event.id)
        .filter(
            models.Event.deleted_at.is_(None),
            models.Registration.user_id == current_user.id,
            models.Registration.deleted_at.is_(None),
        )
        .all()
    )
    vevents = [_event_to_ics(e, uid_suffix=f"-u{current_user.id}") for e in regs]
    ics = "\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//EventLink//EN",
            *vevents,
            "END:VCALENDAR",
        ]
    )
    return Response(content=ics, media_type="text/calendar")


@app.post("/password/forgot", responses=_responses(400))
def password_forgot(
    payload: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
):
    """Start the password reset flow."""
    _enforce_rate_limit(
        "password_forgot", request=request, identifier=payload.email.lower(), limit=5, window_seconds=300
    )
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if user:
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id, models.PasswordResetToken.used.is_(False)
        ).update({"used": True})
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset = models.PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at, used=False)
        db.add(reset)
        db.commit()
        frontend_hint = settings.allowed_origins[0] if settings.allowed_origins else ""
        link = f"{frontend_hint}/reset-password?token={token}" if frontend_hint else token
        lang = user.language_preference
        if not lang or lang == "system":
            lang = (request.headers.get("accept-language") if request else None) or "ro"
        subject, body, body_html = render_password_reset_email(user, link, lang=lang)
        send_email_async(
            background_tasks, db, user.email, subject, body, body_html, context={"user_id": user.id, "lang": lang}
        )
    return {"status": "ok"}


@app.post("/password/reset", responses=_responses(400))
def password_reset(payload: schemas.PasswordResetConfirm, request: Request, db: DbSession):
    """Complete the password reset flow."""
    _enforce_rate_limit("password_reset", request=request, limit=10, window_seconds=300)
    token_row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == payload.token, models.PasswordResetToken.used.is_(False))
        .first()
    )
    expires_at = _normalize_dt(token_row.expires_at) if token_row else None
    if not token_row or (expires_at and expires_at < datetime.now(timezone.utc)):
        raise HTTPException(status_code=400, detail="Token invalid sau expirat.")

    user = db.query(models.User).filter(models.User.id == token_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utilizator inexistent.")

    user.password_hash = auth.get_password_hash(payload.new_password)
    token_row.used = True
    db.add(user)
    db.add(token_row)
    db.commit()
    log_event("password_reset", user_id=user.id)
    return {"status": "password_reset"}
