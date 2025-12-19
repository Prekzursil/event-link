from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from contextlib import asynccontextmanager, suppress
import time
import re
import logging
import asyncio
import secrets
import hashlib
import math
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, text, case
from sqlalchemy.orm import Session, joinedload

from . import auth, models, schemas
from . import ro_universities
from .config import settings
from .database import engine, get_db, SessionLocal
from .email_service import send_email_async
from .email_templates import render_registration_email, render_password_reset_email
from .logging_utils import configure_logging, RequestIdMiddleware, log_event, log_warning

configure_logging()





def _run_migrations():
    """Run Alembic migrations to latest head. Controlled via settings.auto_run_migrations."""
    try:
        from alembic import command
        from alembic.config import Config
        base_dir = Path(__file__).resolve().parent.parent
        alembic_ini = base_dir / 'alembic.ini'
        if not alembic_ini.exists():
            logging.warning('alembic.ini not found; skipping migrations')
            return
        cfg = Config(str(alembic_ini))
        cfg.set_main_option('script_location', str(base_dir / 'alembic'))
        command.upgrade(cfg, 'head')
        logging.info('Migrations applied to head')
    except Exception:
        logging.exception('Failed to run migrations on startup')

def _check_configuration():
    if not settings.database_url:
        raise RuntimeError('DATABASE_URL is required')
    if not settings.secret_key:
        raise RuntimeError('SECRET_KEY is required')
    if settings.email_enabled and (not settings.smtp_host or not settings.smtp_sender):
        logging.warning('Email enabled but SMTP host/sender missing; disabling email sending')
        settings.email_enabled = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
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

def _validate_cover_url(url: str | None) -> None:
    pattern = re.compile(r"^https?://")
    if url and not pattern.match(str(url)):
        raise HTTPException(status_code=400, detail="Cover URL trebuie să fie un link http/https valid.")


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


def _compute_moderation(*, title: str, description: str | None, location: str | None) -> tuple[float, list[str], str]:
    text = f"{title or ''}\n{description or ''}\n{location or ''}"
    lowered = text.lower()

    flags: list[str] = []
    score = 0.0

    urls = _URL_PATTERN.findall(lowered)
    if len(urls) >= 3:
        flags.append("many_links")
        score += 0.3

    if any(any(domain in url for domain in _SHORTENER_DOMAINS) for url in urls):
        flags.append("shortener_link")
        score += 0.4

    if any(keyword in lowered for keyword in _SUSPICIOUS_KEYWORDS):
        flags.append("suspicious_keywords")
        score += 0.4

    if urls and re.search(r"\b(password|parol|otp|one[- ]time|cod)\b", lowered):
        flags.append("credential_request")
        score += 0.5

    score = min(1.0, score)
    status = "flagged" if score >= 0.5 else "clean"
    return score, flags, status


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


def _suggest_category_from_text(text: str) -> str | None:
    lowered = (text or "").lower()
    best: tuple[int, str] | None = None
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lowered)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, category)
    return best[1] if best else None


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9ăâîșț]+", (text or "").lower()) if t}


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
    query = (
        base_query.outerjoin(seats_subquery, models.Event.id == seats_subquery.c.event_id)
        .add_columns(func.coalesce(seats_subquery.c.seats_taken, 0).label("seats_taken"))
    )
    return query, seats_subquery


def _serialize_event(event: models.Event, seats_taken: int, recommendation_reason: str | None = None) -> schemas.EventResponse:
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


def _load_personalization_exclusions(*, db: Session, user_id: int) -> tuple[set[int], set[int]]:
    hidden_tag_ids = {
        int(row[0])
        for row in db.query(models.user_hidden_tags.c.tag_id)
        .filter(models.user_hidden_tags.c.user_id == user_id)
        .all()
    }
    blocked_organizer_ids = {
        int(row[0])
        for row in db.query(models.user_blocked_organizers.c.organizer_id)
        .filter(models.user_blocked_organizers.c.user_id == user_id)
        .all()
    }
    return hidden_tag_ids, blocked_organizer_ids


def _apply_personalization_exclusions(query, *, hidden_tag_ids: set[int], blocked_organizer_ids: set[int]):  # noqa: ANN001
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

    rec_rows = (
        db.query(models.UserRecommendation)
        .filter(models.UserRecommendation.user_id == user.id)
        .order_by(models.UserRecommendation.rank)
        .limit(50)
        .all()
    )
    if not rec_rows:
        return None

    rec_by_event_id: dict[int, models.UserRecommendation] = {row.event_id: row for row in rec_rows}
    event_ids = list(rec_by_event_id.keys())

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

    hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=user.id)
    base_query = _apply_personalization_exclusions(
        base_query,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
    )

    query, seats_subquery = _events_with_counts_query(db, base_query)
    default_reason = "Recommended for you" if lang == "en" else "Recomandat pentru tine"
    ranked: list[tuple[int, models.Event, int, Optional[str]]] = []
    for ev, seats in query.all():
        rec = rec_by_event_id.get(ev.id)
        if not rec:
            continue
        if ev.max_seats is not None and int(seats or 0) >= ev.max_seats:
            continue
        ranked.append((int(rec.rank), ev, int(seats or 0), rec.reason or default_reason))

    if not ranked:
        return None

    ranked.sort(key=lambda row: row[0])
    return [(ev, seats, reason) for _rank, ev, seats, reason in ranked]


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


@app.post("/register", response_model=schemas.Token)
def register(user: schemas.StudentRegister, request: Request, db: Session = Depends(get_db)):
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
        "token_type": "bearer",
        "role": new_user.role,
        "user_id": new_user.id,
    }


@app.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
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
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
    }


@app.post("/refresh", response_model=schemas.Token)
def refresh_token(payload: schemas.RefreshRequest):
    try:
        decoded = auth.jwt.decode(payload.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
    except auth.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expirat.")
    except auth.JWTError:
        raise HTTPException(status_code=401, detail="Refresh token invalid.")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token invalid.")

    user_id = decoded.get("sub")
    email = decoded.get("email")
    role = decoded.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Refresh token invalid.")

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
        "token_type": "bearer",
        "role": role,
        "user_id": int(user_id),
    }


@app.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.put("/api/me/theme", response_model=schemas.UserResponse)
def update_theme_preference(
    payload: schemas.ThemePreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    current_user.theme_preference = payload.theme_preference
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    log_event("theme_preference_updated", user_id=current_user.id, theme_preference=current_user.theme_preference)
    return current_user


@app.put("/api/me/language", response_model=schemas.UserResponse)
def update_language_preference(
    payload: schemas.LanguagePreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
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
    return {"message": "Hello from Event Link API!"}



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = f"http_{exc.status_code}"
    message = exc.detail if isinstance(exc.detail, str) else "Eroare"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}, "detail": message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
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


@app.get("/api/events", response_model=schemas.PaginatedEvents)
def get_events(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tags: Optional[list[str]] = Query(None),
    tags_csv: Optional[str] = None,
    city: Optional[str] = None,
    location: Optional[str] = None,
    include_past: bool = False,
    sort: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_user),
):
    if page < 1:
        raise HTTPException(status_code=400, detail="Pagina trebuie să fie cel puțin 1.")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Dimensiunea paginii trebuie să fie între 1 și 100.")
    now = datetime.now(timezone.utc)
    query = db.query(models.Event).filter(models.Event.deleted_at.is_(None))
    if not include_past:
        query = query.filter(models.Event.start_time >= now)
    # only published and already live
    query = query.filter(models.Event.status == "published").filter(
        (models.Event.publish_at == None) | (models.Event.publish_at <= now)  # noqa: E711
    )
    if search:
        query = query.filter(func.lower(models.Event.title).like(f"%{search.lower()}%"))
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    tag_filters: list[str] = []
    if tags:
        tag_filters.extend(tags)
    if tags_csv:
        tag_filters.extend([t.strip() for t in tags_csv.split(",") if t.strip()])
    if tag_filters:
        lowered = [t.lower() for t in tag_filters]
        query = query.filter(models.Event.tags.any(func.lower(models.Tag.name).in_(lowered)))
    if city:
        query = query.filter(func.lower(models.Event.city).like(f"%{city.lower()}%"))
    if location:
        query = query.filter(func.lower(models.Event.location).like(f"%{location.lower()}%"))
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time <= end_dt)

    if current_user is not None and getattr(current_user, "role", None) == models.UserRole.student:
        hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=current_user.id)
        query = _apply_personalization_exclusions(
            query,
            hidden_tag_ids=hidden_tag_ids,
            blocked_organizer_ids=blocked_organizer_ids,
        )
    total = query.count()
    sort_value = (sort or "").strip().lower()
    if sort_value not in {"recommended", "time"}:
        sort_value = "time"

        if (
            current_user is not None
            and getattr(current_user, "role", None) == models.UserRole.student
            and settings.recommendations_use_ml_cache
            and _recommendations_cache_is_fresh(db=db, user_id=current_user.id, now=now)
            and _in_experiment_treatment(
                "personalization_ml_sort",
                settings.experiments_personalization_ml_percent,
                str(current_user.id),
            )
        ):
            sort_value = "recommended"

    use_recommended_sort = (
        sort_value == "recommended"
        and current_user is not None
        and getattr(current_user, "role", None) == models.UserRole.student
        and settings.recommendations_use_ml_cache
        and _recommendations_cache_is_fresh(db=db, user_id=current_user.id, now=now)
    )

    if use_recommended_sort:
        rec = models.UserRecommendation
        query = query.outerjoin(
            rec,
            (rec.user_id == current_user.id) & (rec.event_id == models.Event.id),
        )
        query = query.order_by(
            case((rec.rank.is_(None), 1), else_=0),
            rec.rank.asc(),
            models.Event.start_time.asc(),
            models.Event.id.asc(),
        )
    else:
        query = query.order_by(models.Event.start_time.asc(), models.Event.id.asc())
    query, _ = _events_with_counts_query(db, query)
    query = query.offset((page - 1) * page_size).limit(page_size)
    events = query.all()
    if use_recommended_sort:
        lang = current_user.language_preference
        if not lang or lang == "system":
            lang = request.headers.get("accept-language") or "ro"
        lang = (lang or "ro").split(",")[0][:2].lower()

        user_city = (current_user.city or "").strip().lower()
        event_ids = [event.id for event, _seats in events]
        reason_by_event_id = {
            int(event_id): reason
            for event_id, reason in (
                db.query(models.UserRecommendation.event_id, models.UserRecommendation.reason)
                .filter(models.UserRecommendation.user_id == current_user.id, models.UserRecommendation.event_id.in_(event_ids))
                .all()
            )
        }
        items = []
        for event, seats in events:
            reason = reason_by_event_id.get(event.id)
            final_reason = reason
            is_local = bool(user_city and event.city and event.city.strip().lower() == user_city)
            if is_local:
                suffix = f"Near you: {event.city}" if lang == "en" else f"În apropiere: {event.city}"
                final_reason = f"{reason} • {suffix}" if reason else suffix
            items.append(_serialize_event(event, seats, recommendation_reason=final_reason))
    else:
        items = [_serialize_event(event, seats) for event, seats in events]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.post("/api/analytics/interactions", status_code=status.HTTP_204_NO_CONTENT)
def record_interactions(
    payload: schemas.InteractionBatchIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_user),
):
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

    event_ids = {event.event_id for event in payload.events if event.event_id is not None}
    existing_event_ids: set[int] = set()
    if event_ids:
        existing_event_ids = {row[0] for row in db.query(models.Event.id).filter(models.Event.id.in_(event_ids)).all()}

    now = datetime.now(timezone.utc)
    interactions: list[models.EventInteraction] = []
    for event in payload.events:
        if event.event_id is not None and event.event_id not in existing_event_ids:
            continue
        occurred_at = event.occurred_at or now
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        interactions.append(
            models.EventInteraction(
                user_id=current_user.id if current_user else None,
                event_id=event.event_id,
                interaction_type=event.interaction_type,
                occurred_at=occurred_at,
                meta=event.meta,
            )
        )

    if not interactions:
        return

    db.add_all(interactions)
    db.commit()

    if (
        current_user is not None
        and getattr(current_user, "role", None) == models.UserRole.student
        and settings.recommendations_online_learning_enabled
    ):
        half_life_hours = max(1, int(settings.recommendations_online_learning_decay_half_life_hours))
        half_life_seconds = float(half_life_hours) * 3600.0
        decay_lambda = math.log(2.0) / half_life_seconds
        max_score = float(settings.recommendations_online_learning_max_score)

        def _normalize_city(value: str | None) -> str | None:
            if not value:
                return None
            s = value.strip().lower()
            return s or None

        def _normalize_category(value: str | None) -> str | None:
            if not value:
                return None
            s = value.strip().lower()
            return s or None

        def _decay(score: float, last_seen_at: datetime) -> float:
            delta_seconds = (now - last_seen_at).total_seconds()
            if delta_seconds <= 0:
                return float(score)
            return float(score) * math.exp(-decay_lambda * float(delta_seconds))

        def _event_delta(*, interaction_type: str, meta: object) -> float:
            itype = (interaction_type or "").strip().lower()
            if itype == "click":
                return 1.0
            if itype == "view":
                return 0.6
            if itype == "share":
                return 1.3
            if itype == "favorite":
                return 2.0
            if itype == "register":
                return 2.5
            if itype == "dwell":
                seconds = None
                if isinstance(meta, dict):
                    seconds = meta.get("seconds")
                if isinstance(seconds, (int, float)) and float(seconds) >= float(
                    settings.recommendations_online_learning_dwell_threshold_seconds
                ):
                    return 0.8 + min(1.0, float(seconds) / 60.0) * 0.4
            return 0.0

        event_deltas: dict[int, float] = {}
        tag_name_deltas: dict[str, float] = {}
        category_deltas: dict[str, float] = {}
        city_deltas: dict[str, float] = {}

        for event in payload.events:
            if event.event_id is not None:
                delta = _event_delta(interaction_type=str(event.interaction_type), meta=event.meta)
                if delta > 0:
                    event_id = int(event.event_id)
                    event_deltas[event_id] = max(event_deltas.get(event_id, 0.0), float(delta))

            if event.interaction_type in {"search", "filter"} and isinstance(event.meta, dict):
                tags_value = event.meta.get("tags")
                if isinstance(tags_value, list):
                    for name in tags_value:
                        s = str(name or "").strip()
                        if not s:
                            continue
                        key = s.lower()
                        tag_name_deltas[key] = max(tag_name_deltas.get(key, 0.0), 0.2)

                cat_value = _normalize_category(event.meta.get("category"))
                if cat_value:
                    category_deltas[cat_value] = max(category_deltas.get(cat_value, 0.0), 0.2)

                city_value = _normalize_city(event.meta.get("city"))
                if city_value:
                    city_deltas[city_value] = max(city_deltas.get(city_value, 0.0), 0.2)

        if event_deltas or tag_name_deltas or category_deltas or city_deltas:
            hidden_tag_ids, _blocked = _load_personalization_exclusions(db=db, user_id=int(current_user.id))

            tag_delta_by_id: dict[int, float] = {}
            if event_deltas:
                event_ids = sorted(event_deltas.keys())
                event_rows = (
                    db.query(models.Event.id, models.Event.category, models.Event.city)
                    .filter(models.Event.id.in_(event_ids))
                    .all()
                )
                event_category_by_id: dict[int, str | None] = {}
                event_city_by_id: dict[int, str | None] = {}
                for event_id, category, city in event_rows:
                    event_category_by_id[int(event_id)] = _normalize_category(category)
                    event_city_by_id[int(event_id)] = _normalize_city(city)

                tag_rows = (
                    db.query(models.event_tags.c.event_id, models.event_tags.c.tag_id)
                    .filter(models.event_tags.c.event_id.in_(event_ids))
                    .all()
                )
                tag_ids_by_event: dict[int, list[int]] = {}
                for event_id, tag_id in tag_rows:
                    tag_ids_by_event.setdefault(int(event_id), []).append(int(tag_id))

                for event_id, delta in event_deltas.items():
                    cat_key = event_category_by_id.get(int(event_id))
                    if cat_key:
                        category_deltas[cat_key] = category_deltas.get(cat_key, 0.0) + float(delta)
                    city_key = event_city_by_id.get(int(event_id))
                    if city_key:
                        city_deltas[city_key] = city_deltas.get(city_key, 0.0) + float(delta)

                    tag_ids = tag_ids_by_event.get(int(event_id), [])
                    per_tag = float(delta) / float(max(1, len(tag_ids)))
                    for tag_id in tag_ids:
                        if tag_id in hidden_tag_ids:
                            continue
                        tag_delta_by_id[int(tag_id)] = tag_delta_by_id.get(int(tag_id), 0.0) + per_tag

            if tag_name_deltas:
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
                    if delta > 0:
                        tag_delta_by_id[int(tag_id)] = tag_delta_by_id.get(int(tag_id), 0.0) + delta

            if tag_delta_by_id:
                existing_rows = (
                    db.query(models.UserImplicitInterestTag)
                    .filter(
                        models.UserImplicitInterestTag.user_id == current_user.id,
                        models.UserImplicitInterestTag.tag_id.in_(sorted(tag_delta_by_id.keys())),
                    )
                    .all()
                )
                existing_by_tag_id = {int(row.tag_id): row for row in existing_rows}
                for tag_id, row in existing_by_tag_id.items():
                    last_seen_at = row.last_seen_at or now
                    if last_seen_at.tzinfo is None:
                        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
                    delta = float(tag_delta_by_id.get(tag_id, 0.0))
                    row.score = min(max_score, _decay(float(row.score or 0.0), last_seen_at) + delta)
                    row.last_seen_at = now
                    db.add(row)

                for tag_id, delta in tag_delta_by_id.items():
                    if tag_id in existing_by_tag_id:
                        continue
                    db.add(
                        models.UserImplicitInterestTag(
                            user_id=current_user.id,
                            tag_id=int(tag_id),
                            score=min(max_score, float(delta)),
                            last_seen_at=now,
                        )
                    )

            if category_deltas:
                existing_rows = (
                    db.query(models.UserImplicitInterestCategory)
                    .filter(
                        models.UserImplicitInterestCategory.user_id == current_user.id,
                        models.UserImplicitInterestCategory.category.in_(sorted(category_deltas.keys())),
                    )
                    .all()
                )
                existing_by_key = {str(row.category): row for row in existing_rows}
                for key, row in existing_by_key.items():
                    last_seen_at = row.last_seen_at or now
                    if last_seen_at.tzinfo is None:
                        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
                    delta = float(category_deltas.get(str(key), 0.0))
                    row.score = min(max_score, _decay(float(row.score or 0.0), last_seen_at) + delta)
                    row.last_seen_at = now
                    db.add(row)
                for key, delta in category_deltas.items():
                    if str(key) in existing_by_key:
                        continue
                    db.add(
                        models.UserImplicitInterestCategory(
                            user_id=current_user.id,
                            category=str(key),
                            score=min(max_score, float(delta)),
                            last_seen_at=now,
                        )
                    )

            if city_deltas:
                existing_rows = (
                    db.query(models.UserImplicitInterestCity)
                    .filter(
                        models.UserImplicitInterestCity.user_id == current_user.id,
                        models.UserImplicitInterestCity.city.in_(sorted(city_deltas.keys())),
                    )
                    .all()
                )
                existing_by_key = {str(row.city): row for row in existing_rows}
                for key, row in existing_by_key.items():
                    last_seen_at = row.last_seen_at or now
                    if last_seen_at.tzinfo is None:
                        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
                    delta = float(city_deltas.get(str(key), 0.0))
                    row.score = min(max_score, _decay(float(row.score or 0.0), last_seen_at) + delta)
                    row.last_seen_at = now
                    db.add(row)
                for key, delta in city_deltas.items():
                    if str(key) in existing_by_key:
                        continue
                    db.add(
                        models.UserImplicitInterestCity(
                            user_id=current_user.id,
                            city=str(key),
                            score=min(max_score, float(delta)),
                            last_seen_at=now,
                        )
                    )

            db.commit()

    if (
        current_user is not None
        and getattr(current_user, "role", None) == models.UserRole.student
        and settings.task_queue_enabled
        and settings.recommendations_use_ml_cache
        and settings.recommendations_realtime_refresh_enabled
    ):
        should_refresh = False
        for event in payload.events:
            if event.interaction_type in {"click", "view", "share", "favorite", "register", "unregister", "search", "filter"}:
                should_refresh = True
                break
            if event.interaction_type == "dwell":
                seconds = None
                if isinstance(event.meta, dict):
                    seconds = event.meta.get("seconds")
                if isinstance(seconds, (int, float)) and float(seconds) >= 10.0:
                    should_refresh = True
                    break

        if should_refresh:
            from .task_queue import enqueue_job, JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML  # noqa: PLC0415

            latest_generated_at = (
                db.query(func.max(models.UserRecommendation.generated_at))
                .filter(models.UserRecommendation.user_id == current_user.id)
                .scalar()
            )
            if latest_generated_at is not None:
                if latest_generated_at.tzinfo is None:
                    latest_generated_at = latest_generated_at.replace(tzinfo=timezone.utc)
                age_seconds = (now - latest_generated_at).total_seconds()
                if age_seconds < float(settings.recommendations_realtime_refresh_min_interval_seconds):
                    return

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
    return


@app.get("/api/public/events", response_model=schemas.PaginatedPublicEvents)
def get_public_events(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    tags: Optional[list[str]] = Query(None),
    tags_csv: Optional[str] = None,
    city: Optional[str] = None,
    location: Optional[str] = None,
    include_past: bool = False,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    _enforce_rate_limit(
        "public_events_list",
        request=request,
        limit=settings.public_api_rate_limit,
        window_seconds=settings.public_api_rate_window_seconds,
    )
    if page < 1:
        raise HTTPException(status_code=400, detail="Pagina trebuie să fie cel puțin 1.")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Dimensiunea paginii trebuie să fie între 1 și 100.")
    now = datetime.now(timezone.utc)
    query = db.query(models.Event).filter(models.Event.deleted_at.is_(None))
    if not include_past:
        query = query.filter(models.Event.start_time >= now)
    query = query.filter(models.Event.status == "published").filter(
        (models.Event.publish_at == None) | (models.Event.publish_at <= now)  # noqa: E711
    )
    if search:
        query = query.filter(func.lower(models.Event.title).like(f"%{search.lower()}%"))
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    tag_filters: list[str] = []
    if tags:
        tag_filters.extend(tags)
    if tags_csv:
        tag_filters.extend([t.strip() for t in tags_csv.split(",") if t.strip()])
    if tag_filters:
        lowered = [t.lower() for t in tag_filters]
        query = query.filter(models.Event.tags.any(func.lower(models.Tag.name).in_(lowered)))
    if city:
        query = query.filter(func.lower(models.Event.city).like(f"%{city.lower()}%"))
    if location:
        query = query.filter(func.lower(models.Event.location).like(f"%{location.lower()}%"))
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time <= end_dt)
    total = query.count()
    query = query.order_by(models.Event.id, models.Event.start_time)
    query, seats_subquery = _events_with_counts_query(db, query)
    query = query.offset((page - 1) * page_size).limit(page_size)
    events = query.all()
    items = [_serialize_public_event(event, seats) for event, seats in events]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/public/events/{event_id}", response_model=schemas.PublicEventDetailResponse)
def get_public_event(event_id: int, request: Request, db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    event, seats_taken = result
    now = datetime.now(timezone.utc)
    if event.status != "published" or (event.publish_at and event.publish_at > now):
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    available_seats = event.max_seats - seats_taken if event.max_seats is not None else None
    base = _serialize_public_event(event, seats_taken)
    return schemas.PublicEventDetailResponse(**base.model_dump(), available_seats=available_seats)


@app.get("/api/events/{event_id}", response_model=schemas.EventDetailResponse)
def get_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_user),
):
    query, seats_subquery = _events_with_counts_query(
        db,
        db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)),
    )
    result = query.first()
    if not result:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    event, seats_taken = result
    now = datetime.now(timezone.utc)
    if (event.status != "published" or (event.publish_at and event.publish_at > now)) and not (
        current_user and (current_user.id == event.owner_id or _is_admin(current_user))
    ):
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    is_registered = False
    is_favorite = False
    if current_user:
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
    recommendation_reason: str | None = None
    if current_user and getattr(current_user, "role", None) == models.UserRole.student:
        lang = current_user.language_preference
        if not lang or lang == "system":
            lang = request.headers.get("accept-language") or "ro"
        lang = (lang or "ro").split(",")[0][:2].lower()

        rec_reason = (
            db.query(models.UserRecommendation.reason)
            .filter(models.UserRecommendation.user_id == current_user.id, models.UserRecommendation.event_id == event.id)
            .scalar()
        )
        recommendation_reason = rec_reason

        user_city = (current_user.city or "").strip().lower()
        is_local = bool(user_city and event.city and event.city.strip().lower() == user_city)
        if is_local:
            suffix = f"Near you: {event.city}" if lang == "en" else f"În apropiere: {event.city}"
            recommendation_reason = f"{rec_reason} • {suffix}" if rec_reason else suffix
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


@app.post("/api/events", response_model=schemas.EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event: schemas.EventCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_organizer)
):
    start_time = _normalize_dt(event.start_time)
    end_time = _normalize_dt(event.end_time)
    if start_time:
        _ensure_future_date(start_time)
    if end_time and start_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="Ora de sfârșit trebuie să fie după ora de început.")
    if event.max_seats is None or event.max_seats <= 0:
        raise HTTPException(status_code=400, detail="Numărul maxim de locuri trebuie să fie pozitiv.")
    if event.cover_url:
        if len(event.cover_url) > 500:
            raise HTTPException(status_code=400, detail="Cover URL prea lung.")
        _validate_cover_url(event.cover_url)

    new_event = models.Event(
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=start_time,
        end_time=end_time,
        city=event.city,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        owner_id=current_user.id,
        status=event.status or "published",
        publish_at=_normalize_dt(event.publish_at) if event.publish_at else None,
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


@app.put("/api/events/{event_id}", response_model=schemas.EventResponse)
def update_event(
    event_id: int,
    update: schemas.EventUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    db_event = (
        db.query(models.Event)
        .filter(models.Event.id == event_id, models.Event.deleted_at.is_(None))
        .first()
    )
    if not db_event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if db_event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați acest eveniment.")

    if update.title is not None:
        db_event.title = update.title
    if update.description is not None:
        db_event.description = update.description
    if update.category is not None:
        db_event.category = update.category
    if update.start_time is not None:
        update.start_time = _normalize_dt(update.start_time)
        _ensure_future_date(update.start_time)
        db_event.start_time = update.start_time
    if update.end_time is not None:
        update.end_time = _normalize_dt(update.end_time)
        if db_event.start_time and update.end_time and update.end_time <= db_event.start_time:
            raise HTTPException(status_code=400, detail="Ora de sfârșit trebuie să fie după ora de început.")
        db_event.end_time = update.end_time
    if update.city is not None:
        db_event.city = update.city
    if update.location is not None:
        db_event.location = update.location
    if update.max_seats is not None:
        if update.max_seats <= 0:
            raise HTTPException(status_code=400, detail="Numărul maxim de locuri trebuie să fie pozitiv.")
        db_event.max_seats = update.max_seats
    if update.cover_url is not None:
        if update.cover_url:
            if len(update.cover_url) > 500:
                raise HTTPException(status_code=400, detail="Cover URL prea lung.")
            _validate_cover_url(update.cover_url)
        db_event.cover_url = update.cover_url
    if update.tags is not None:
        _attach_tags(db, db_event, update.tags)
    if update.status is not None:
        if update.status not in ("draft", "published"):
            raise HTTPException(status_code=400, detail="Status invalid")
        db_event.status = update.status
    if update.publish_at is not None:
        db_event.publish_at = _normalize_dt(update.publish_at)

    content_changed = update.title is not None or update.description is not None or update.location is not None
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


@app.delete("/api/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_organizer)):
    db_event = (
        db.query(models.Event)
        .filter(models.Event.id == event_id, models.Event.deleted_at.is_(None))
        .first()
    )
    if not db_event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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
    return


@app.post("/api/events/{event_id}/restore")
def restore_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event or db_event.deleted_at is None:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")

    if not _is_admin(current_user):
        if current_user.role != models.UserRole.organizator:
            raise HTTPException(status_code=403, detail="Acces doar pentru organizatori.")
        if db_event.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Nu aveți dreptul să restaurați acest eveniment.")

    deleted_by_user_id = db_event.deleted_by_user_id
    db_event.deleted_at = None
    db_event.deleted_by_user_id = None

    restored_registrations = 0
    if deleted_by_user_id:
        regs = (
            db.query(models.Registration)
            .filter(
                models.Registration.event_id == db_event.id,
                models.Registration.deleted_at.is_not(None),
                models.Registration.deleted_by_user_id == deleted_by_user_id,
            )
            .all()
        )
        for reg in regs:
            reg.deleted_at = None
            reg.deleted_by_user_id = None
            restored_registrations += 1
            _audit_log(
                db,
                entity_type="registration",
                entity_id=reg.id,
                action="restored",
                actor_user_id=current_user.id,
                meta={"event_id": db_event.id, "reason": "event_restored"},
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


@app.post("/api/events/{event_id}/clone", response_model=schemas.EventResponse)
def clone_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    orig = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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


@app.get("/api/organizer/events", response_model=List[schemas.EventResponse])
def organizer_events(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    base_query = db.query(models.Event).filter(models.Event.owner_id == current_user.id)
    if not include_deleted:
        base_query = base_query.filter(models.Event.deleted_at.is_(None))
    base_query = base_query.order_by(models.Event.start_time)
    query, seats_subquery = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


@app.post("/api/organizer/events/bulk/status")
def organizer_bulk_update_status(
    payload: schemas.OrganizerBulkStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    event_ids = list(dict.fromkeys(payload.event_ids))
    if not event_ids:
        raise HTTPException(status_code=400, detail="Nu ați selectat niciun eveniment.")

    events = (
        db.query(models.Event)
        .filter(models.Event.id.in_(event_ids), models.Event.deleted_at.is_(None))
        .all()
    )
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


@app.post("/api/organizer/events/bulk/tags")
def organizer_bulk_update_tags(
    payload: schemas.OrganizerBulkTagsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    event_ids = list(dict.fromkeys(payload.event_ids))
    if not event_ids:
        raise HTTPException(status_code=400, detail="Nu ați selectat niciun eveniment.")

    events = (
        db.query(models.Event)
        .filter(models.Event.id.in_(event_ids), models.Event.deleted_at.is_(None))
        .all()
    )
    if len(events) != len(set(event_ids)):
        raise HTTPException(status_code=404, detail="Unele evenimente nu există.")
    if not _is_admin(current_user) and any(ev.owner_id != current_user.id for ev in events):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați toate evenimentele selectate.")

    for tag in payload.tags:
        if tag and len(tag.strip()) > 100:
            raise HTTPException(status_code=400, detail="Etichetele trebuie să aibă maxim 100 de caractere.")

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


@app.post("/api/organizer/events/suggest", response_model=schemas.EventSuggestResponse)
def organizer_suggest_event(
    payload: schemas.EventSuggestRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    text = " ".join(
        [
            payload.title or "",
            payload.description or "",
            payload.city or "",
            payload.location or "",
        ]
    ).strip()

    suggested_category = payload.category or _suggest_category_from_text(text)
    suggested_city = payload.city
    if not suggested_city:
        cities = {item.get("city") for item in ro_universities.get_university_catalog() if item.get("city")}
        lowered = text.lower()
        for city in sorted(cities, key=lambda c: len(str(c)), reverse=True):
            if str(city).lower() in lowered:
                suggested_city = str(city)
                break

    all_tags = db.query(models.Tag).order_by(models.Tag.name).all()
    lowered = text.lower()
    suggested_tags: list[str] = []
    for tag in all_tags:
        name = (tag.name or "").strip()
        if not name:
            continue
        if name.lower() in lowered:
            suggested_tags.append(name)
    suggested_tags = list(dict.fromkeys(suggested_tags))[:10]

    duplicates: list[schemas.EventDuplicateCandidate] = []
    title_tokens = _tokenize(payload.title)
    if title_tokens:
        query = db.query(models.Event).filter(models.Event.owner_id == current_user.id, models.Event.deleted_at.is_(None))
        if payload.start_time:
            st = _normalize_dt(payload.start_time)
            if st:
                query = query.filter(models.Event.start_time >= st - timedelta(days=30), models.Event.start_time <= st + timedelta(days=30))
        candidates = query.order_by(models.Event.start_time.desc()).limit(50).all()
        for ev in candidates:
            sim = _jaccard_similarity(title_tokens, _tokenize(ev.title))
            if sim < 0.6:
                continue
            duplicates.append(
                schemas.EventDuplicateCandidate(
                    id=int(ev.id),
                    title=ev.title,
                    start_time=ev.start_time,
                    city=ev.city,
                    similarity=float(sim),
                )
            )
        duplicates.sort(key=lambda item: item.similarity, reverse=True)
        duplicates = duplicates[:5]

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


@app.post(
    "/api/organizer/events/{event_id}/participants/email",
    response_model=schemas.OrganizerEmailParticipantsResponse,
)
def email_event_participants(
    event_id: int,
    payload: schemas.OrganizerEmailParticipantsRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    _enforce_rate_limit(
        "organizer_email_participants",
        request=request,
        identifier=current_user.email.lower(),
        limit=5,
        window_seconds=60,
    )
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să trimiteți email pentru acest eveniment.")

    recipients = (
        db.query(models.User.email)
        .join(models.Registration, models.Registration.user_id == models.User.id)
        .filter(
            models.Registration.event_id == event_id,
            models.Registration.deleted_at.is_(None),
        )
        .all()
    )

    for (email,) in recipients:
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
        meta={"recipients": len(recipients)},
    )
    db.commit()
    log_event(
        "organizer_participants_emailed",
        event_id=event.id,
        owner_id=event.owner_id,
        actor_user_id=current_user.id,
        recipients=len(recipients),
    )
    return {"recipients": len(recipients)}


def _serialize_profile(user: models.User, db: Session) -> schemas.OrganizerProfileResponse:
    base_query = db.query(models.Event).filter(models.Event.owner_id == user.id, models.Event.deleted_at.is_(None))
    now = datetime.now(timezone.utc)
    base_query = base_query.filter(
        models.Event.status == "published",
        (models.Event.publish_at == None) | (models.Event.publish_at <= now),  # noqa: E711
    ).order_by(models.Event.start_time)
    query, seats_subquery = _events_with_counts_query(db, base_query)
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


@app.get("/api/organizers/{organizer_id}", response_model=schemas.OrganizerProfileResponse)
def get_organizer_profile(organizer_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == organizer_id, models.User.role == models.UserRole.organizator).first()
    if not user:
        raise HTTPException(status_code=404, detail="Organizatorul nu există")
    return _serialize_profile(user, db)


@app.put("/api/organizers/me/profile", response_model=schemas.OrganizerProfileResponse)
def update_organizer_profile(
    payload: schemas.OrganizerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    if payload.org_logo_url and len(payload.org_logo_url) > 500:
        raise HTTPException(status_code=400, detail="URL logo prea lung")
    current_user.org_name = payload.org_name or current_user.org_name
    current_user.org_description = payload.org_description
    current_user.org_logo_url = payload.org_logo_url
    current_user.org_website = payload.org_website
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user, db)


# ===================== TAGS =====================

@app.get("/api/metadata/universities", response_model=schemas.UniversityCatalogResponse)
def list_university_catalog():
    return {"items": ro_universities.get_university_catalog()}


@app.get("/api/tags", response_model=schemas.TagListResponse)
def get_all_tags(db: Session = Depends(get_db)):
    """Get all available tags for filtering and student interests."""
    tags = db.query(models.Tag).order_by(models.Tag.name).all()
    return {"items": [{"id": t.id, "name": t.name} for t in tags]}


# ===================== STUDENT PROFILE =====================

@app.get("/api/me/profile", response_model=schemas.StudentProfileResponse)
def get_student_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Get current user's profile with interest tags."""
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "city": current_user.city,
        "university": ro_universities.normalize_university_name(current_user.university),
        "faculty": current_user.faculty,
        "study_level": current_user.study_level,
        "study_year": current_user.study_year,
        "interest_tags": [{"id": t.id, "name": t.name} for t in current_user.interest_tags],
    }


@app.put("/api/me/profile", response_model=schemas.StudentProfileResponse)
def update_student_profile(
    payload: schemas.StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Update current user's profile and interest tags."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    if payload.city is not None:
        current_user.city = payload.city.strip() or None
    if payload.university is not None:
        current_user.university = ro_universities.normalize_university_name(payload.university)
    if payload.faculty is not None:
        current_user.faculty = payload.faculty.strip() or None
    if payload.study_level is not None:
        current_user.study_level = payload.study_level
    if payload.study_year is not None:
        current_user.study_year = payload.study_year

    if current_user.study_level and current_user.study_year:
        max_year = {"bachelor": 4, "master": 2, "phd": 4, "medicine": 6}.get(current_user.study_level, 10)
        if current_user.study_year < 1 or current_user.study_year > max_year:
            raise HTTPException(
                status_code=400,
                detail=f"An invalid pentru nivelul {current_user.study_level}. (1-{max_year})",
            )
    
    if payload.interest_tag_ids is not None:
        # Get tags by IDs
        tags = db.query(models.Tag).filter(models.Tag.id.in_(payload.interest_tag_ids)).all()
        current_user.interest_tags = tags
    
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "city": current_user.city,
        "university": ro_universities.normalize_university_name(current_user.university),
        "faculty": current_user.faculty,
        "study_level": current_user.study_level,
        "study_year": current_user.study_year,
        "interest_tags": [{"id": t.id, "name": t.name} for t in current_user.interest_tags],
    }


# ===================== PERSONALIZATION SETTINGS =====================


@app.get("/api/me/personalization", response_model=schemas.PersonalizationSettingsResponse)
def get_personalization_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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


@app.post("/api/me/personalization/hidden-tags/{tag_id}", status_code=status.HTTP_201_CREATED)
def add_hidden_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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


@app.delete("/api/me/personalization/hidden-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_hidden_tag(
    tag_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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
    return


@app.post("/api/me/personalization/blocked-organizers/{organizer_id}", status_code=status.HTTP_201_CREATED)
def add_blocked_organizer(
    organizer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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


@app.delete("/api/me/personalization/blocked-organizers/{organizer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_blocked_organizer(
    organizer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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
    return


# ===================== NOTIFICATION PREFERENCES =====================


@app.get("/api/me/notifications", response_model=schemas.NotificationPreferencesResponse)
def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    return {
        "email_digest_enabled": getattr(current_user, "email_digest_enabled", False),
        "email_filling_fast_enabled": getattr(current_user, "email_filling_fast_enabled", False),
    }


@app.put("/api/me/notifications", response_model=schemas.NotificationPreferencesResponse)
def update_notification_preferences(
    payload: schemas.NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
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


@app.get("/api/me/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
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
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
            "full_name": current_user.full_name,
            "theme_preference": current_user.theme_preference,
            "city": current_user.city,
            "university": current_user.university,
            "faculty": current_user.faculty,
            "study_level": current_user.study_level,
            "study_year": current_user.study_year,
            "org_name": current_user.org_name,
            "org_description": current_user.org_description,
            "org_logo_url": current_user.org_logo_url,
            "org_website": current_user.org_website,
            "interest_tags": [{"id": t.id, "name": t.name} for t in current_user.interest_tags],
        },
        "registrations": [
            {
                "registration_time": _normalize_dt(reg.registration_time).isoformat() if reg.registration_time else None,
                "attended": bool(reg.attended),
                "event": _serialize_event_for_export(ev),
            }
            for reg, ev in registrations
        ],
        "favorites": [
            {
                "favorited_at": _normalize_dt(fav.created_at).isoformat() if fav.created_at else None,
                "event": _serialize_event_for_export(ev),
            }
            for fav, ev in favorites
        ],
    }

    if current_user.role == models.UserRole.organizator:
        events = (
            db.query(models.Event)
            .filter(models.Event.owner_id == current_user.id)
            .order_by(models.Event.start_time.desc())
            .all()
        )
        event_ids = [e.id for e in events]
        reg_counts = {
            event_id: count
            for event_id, count in (
                db.query(models.Registration.event_id, func.count(models.Registration.id))
                .filter(models.Registration.event_id.in_(event_ids))
                .group_by(models.Registration.event_id)
                .all()
                if event_ids
                else []
            )
        }
        fav_counts = {
            event_id: count
            for event_id, count in (
                db.query(models.FavoriteEvent.event_id, func.count(models.FavoriteEvent.id))
                .filter(models.FavoriteEvent.event_id.in_(event_ids))
                .group_by(models.FavoriteEvent.event_id)
                .all()
                if event_ids
                else []
            )
        }
        export_payload["organized_events"] = [
            {
                **_serialize_event_for_export(ev),
                "registrations_count": int(reg_counts.get(ev.id, 0)),
                "favorites_count": int(fav_counts.get(ev.id, 0)),
            }
            for ev in events
        ]

    filename_date = exported_at.strftime("%Y%m%d")
    headers = {"Content-Disposition": f'attachment; filename="eventlink-export-{filename_date}.json"'}
    return JSONResponse(content=export_payload, headers=headers)


@app.delete("/api/me")
def delete_my_account(
    payload: schemas.AccountDeleteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not auth.verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Parolă incorectă.")

    deleted_user_id = current_user.id
    deleted_role = current_user.role

    deleted_organizer_email = "deleted-organizer@eventlink.invalid"
    if current_user.email.lower() == deleted_organizer_email:
        raise HTTPException(status_code=400, detail="Acest cont nu poate fi șters.")

    if deleted_role == models.UserRole.organizator:
        placeholder = (
            db.query(models.User)
            .filter(func.lower(models.User.email) == deleted_organizer_email)
            .first()
        )
        if not placeholder:
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

        db.query(models.Event).filter(models.Event.owner_id == current_user.id).update(
            {"owner_id": placeholder.id},
            synchronize_session=False,
        )

    db.query(models.PasswordResetToken).filter(models.PasswordResetToken.user_id == current_user.id).delete(
        synchronize_session=False
    )
    db.query(models.Registration).filter(models.Registration.user_id == current_user.id).delete(
        synchronize_session=False
    )
    db.query(models.FavoriteEvent).filter(models.FavoriteEvent.user_id == current_user.id).delete(
        synchronize_session=False
    )
    db.execute(models.user_interest_tags.delete().where(models.user_interest_tags.c.user_id == current_user.id))

    db.delete(current_user)
    db.commit()
    log_event("account_deleted", user_id=deleted_user_id, role=str(deleted_role))
    return {"status": "deleted"}


@app.get("/api/organizer/events/{event_id}/participants", response_model=schemas.ParticipantListResponse)
def event_participants(
    event_id: int,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "registration_time",
    sort_dir: str = "asc",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if event.owner_id != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să accesați acest eveniment.")

    sort_column = models.Registration.registration_time
    if sort_by == "email":
        sort_column = models.User.email
    elif sort_by == "name":
        sort_column = models.User.full_name
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
    participant_list = [
        schemas.ParticipantResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            registration_time=reg_time,
            attended=attended,
        )
        for user, reg_time, attended in participants
    ]
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


@app.put("/api/organizer/events/{event_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_participant_attendance(
    event_id: int,
    user_id: int,
    attended: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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
    return


@app.post("/api/events/{event_id}/register", status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    _ensure_registrations_enabled()
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    now = datetime.now(timezone.utc)
    if event.status != "published" or (event.publish_at and event.publish_at > now):
        raise HTTPException(status_code=400, detail="Evenimentul nu este publicat.")
    start_time = _normalize_dt(event.start_time)
    if start_time and start_time < now:
        raise HTTPException(status_code=400, detail="Evenimentul a început deja.")

    seats_taken = (
        db.query(func.count(models.Registration.id))
        .filter(models.Registration.event_id == event_id, models.Registration.deleted_at.is_(None))
        .scalar()
        or 0
    )
    if event.max_seats is not None and seats_taken >= event.max_seats:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evenimentul este plin.")

    existing = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if existing:
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
        return {"status": "registered"}

    registration = models.Registration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    db.commit()
    log_event("event_registered", event_id=event.id, user_id=current_user.id)

    lang = current_user.language_preference
    if not lang or lang == "system":
        lang = (request.headers.get("accept-language") if request else None) or "ro"
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
    return {"status": "registered"}


@app.post("/api/events/{event_id}/register/resend", status_code=status.HTTP_200_OK)
def resend_registration_email(
    event_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    _ensure_registrations_enabled()
    _enforce_rate_limit("resend_registration", request=request, identifier=current_user.email.lower(), limit=3, window_seconds=600)
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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


@app.delete("/api/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT)
def unregister_from_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    _ensure_registrations_enabled()
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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
    return


@app.post("/api/admin/events/{event_id}/registrations/{user_id}/restore")
def admin_restore_registration(
    event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
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


@app.get("/api/admin/stats", response_model=schemas.AdminStatsResponse)
def admin_stats(
    days: int = 30,
    top_tags_limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="`days` trebuie să fie între 1 și 365.")
    if top_tags_limit < 1 or top_tags_limit > 100:
        raise HTTPException(status_code=400, detail="`top_tags_limit` trebuie să fie între 1 și 100.")

    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_events = db.query(func.count(models.Event.id)).filter(models.Event.deleted_at.is_(None)).scalar() or 0
    total_registrations = (
        db.query(func.count(models.Registration.id)).filter(models.Registration.deleted_at.is_(None)).scalar() or 0
    )

    start = datetime.now(timezone.utc) - timedelta(days=days)
    reg_rows = (
        db.query(
            func.date(models.Registration.registration_time).label("day"),
            func.count(models.Registration.id).label("registrations"),
        )
        .filter(models.Registration.deleted_at.is_(None), models.Registration.registration_time >= start)
        .group_by("day")
        .order_by("day")
        .all()
    )
    registrations_by_day = [
        schemas.RegistrationDayStat(date=str(row.day), registrations=int(row.registrations or 0)) for row in reg_rows
    ]

    tag_rows = (
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
    top_tags = [
        schemas.TagPopularityStat(
            name=row.name,
            registrations=int(row.registrations or 0),
            events=int(row.events or 0),
        )
        for row in tag_rows
    ]

    return {
        "total_users": int(total_users),
        "total_events": int(total_events),
        "total_registrations": int(total_registrations),
        "registrations_by_day": registrations_by_day,
        "top_tags": top_tags,
    }


@app.get("/api/admin/personalization/metrics", response_model=schemas.PersonalizationMetricsResponse)
def admin_personalization_metrics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="`days` trebuie să fie între 1 și 365.")

    start = datetime.now(timezone.utc) - timedelta(days=days)
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
        day_key = str(day)
        bucket = by_day.setdefault(day_key, {"impression": 0, "click": 0, "register": 0})
        bucket[str(interaction_type)] = int(count or 0)

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

        ctr = (clicks / impressions) if impressions else 0.0
        registration_conversion = (registrations / clicks) if clicks else 0.0
        items.append(
            schemas.PersonalizationMetricsDay(
                date=day,
                impressions=impressions,
                clicks=clicks,
                registrations=registrations,
                ctr=ctr,
                registration_conversion=registration_conversion,
            )
        )

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    active = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.is_active.is_(True))
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
)
def admin_enqueue_guardrails_evaluate(
    payload: schemas.AdminEvaluateGuardrailsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
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
)
def admin_activate_personalization_model(
    payload: schemas.AdminActivatePersonalizationModelRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    model = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.model_version == payload.model_version)
        .first()
    )
    if not model:
        raise HTTPException(status_code=404, detail="Modelul nu există.")

    db.query(models.RecommenderModel).update({"is_active": False}, synchronize_session=False)
    model.is_active = True
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


@app.post("/api/admin/personalization/retrain", response_model=schemas.EnqueuedJobResponse, status_code=status.HTTP_201_CREATED)
def admin_enqueue_retrain_recommendations(
    payload: schemas.AdminRetrainRecommendationsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    from .task_queue import enqueue_job, JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML  # noqa: PLC0415

    job = enqueue_job(
        db,
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        payload.model_dump(exclude_none=True),
        dedupe_key="global",
    )
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.post("/api/admin/notifications/weekly-digest", response_model=schemas.EnqueuedJobResponse, status_code=status.HTTP_201_CREATED)
def admin_enqueue_weekly_digest(
    payload: schemas.AdminWeeklyDigestRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    from .task_queue import enqueue_job, JOB_TYPE_SEND_WEEKLY_DIGEST  # noqa: PLC0415

    job = enqueue_job(db, JOB_TYPE_SEND_WEEKLY_DIGEST, payload.model_dump(exclude_none=True), dedupe_key="global")
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.post("/api/admin/notifications/filling-fast", response_model=schemas.EnqueuedJobResponse, status_code=status.HTTP_201_CREATED)
def admin_enqueue_filling_fast(
    payload: schemas.AdminFillingFastRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    from .task_queue import enqueue_job, JOB_TYPE_SEND_FILLING_FAST_ALERTS  # noqa: PLC0415

    job = enqueue_job(db, JOB_TYPE_SEND_FILLING_FAST_ALERTS, payload.model_dump(exclude_none=True), dedupe_key="global")
    return {"job_id": int(job.id), "job_type": job.job_type, "status": job.status}


@app.get("/api/admin/users", response_model=schemas.PaginatedAdminUsers)
def admin_list_users(
    search: Optional[str] = None,
    role: Optional[models.UserRole] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    if page < 1:
        raise HTTPException(status_code=400, detail="Pagina trebuie să fie cel puțin 1.")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Dimensiunea paginii trebuie să fie între 1 și 100.")

    filters = []
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
        filters.append(models.User.is_active == is_active)

    total = db.query(func.count(models.User.id)).filter(*filters).scalar() or 0

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

    rows = (
        db.query(
            models.User,
            func.coalesce(reg_counts.c.registrations_count, 0).label("registrations_count"),
            func.coalesce(reg_counts.c.attended_count, 0).label("attended_count"),
            func.coalesce(events_counts.c.events_created_count, 0).label("events_created_count"),
        )
        .outerjoin(reg_counts, reg_counts.c.user_id == models.User.id)
        .outerjoin(events_counts, events_counts.c.user_id == models.User.id)
        .filter(*filters)
        .order_by(models.User.created_at.desc(), models.User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: list[schemas.AdminUserResponse] = []
    for user, registrations_count, attended_count, events_created_count in rows:
        items.append(
            schemas.AdminUserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                full_name=user.full_name,
                org_name=user.org_name,
                created_at=user.created_at,
                last_seen_at=user.last_seen_at,
                is_active=bool(user.is_active),
                registrations_count=int(registrations_count or 0),
                attended_count=int(attended_count or 0),
                events_created_count=int(events_created_count or 0),
            )
        )

    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


@app.patch("/api/admin/users/{user_id}", response_model=schemas.AdminUserResponse)
def admin_update_user(
    user_id: int,
    payload: schemas.AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizatorul nu există.")

    changed = False
    if payload.role is not None:
        user.role = payload.role
        changed = True
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changed = True
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
            meta={"role": user.role.value, "is_active": bool(user.is_active)},
        )
        db.commit()

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

    row = (
        db.query(
            models.User,
            func.coalesce(reg_counts.c.registrations_count, 0).label("registrations_count"),
            func.coalesce(reg_counts.c.attended_count, 0).label("attended_count"),
            func.coalesce(events_counts.c.events_created_count, 0).label("events_created_count"),
        )
        .outerjoin(reg_counts, reg_counts.c.user_id == models.User.id)
        .outerjoin(events_counts, events_counts.c.user_id == models.User.id)
        .filter(models.User.id == user_id)
        .first()
    )
    assert row is not None
    user, registrations_count, attended_count, events_created_count = row
    return schemas.AdminUserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        org_name=user.org_name,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        is_active=bool(user.is_active),
        registrations_count=int(registrations_count or 0),
        attended_count=int(attended_count or 0),
        events_created_count=int(events_created_count or 0),
    )


@app.get("/api/admin/events", response_model=schemas.PaginatedAdminEvents)
def admin_list_events(
    search: Optional[str] = None,
    category: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = None,
    include_deleted: bool = False,
    flagged_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    if page < 1:
        raise HTTPException(status_code=400, detail="Pagina trebuie să fie cel puțin 1.")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Dimensiunea paginii trebuie să fie între 1 și 100.")

    query = db.query(models.Event).options(joinedload(models.Event.owner), joinedload(models.Event.tags))
    if not include_deleted:
        query = query.filter(models.Event.deleted_at.is_(None))
    if flagged_only:
        query = query.filter(models.Event.moderation_status == "flagged")
    if status:
        if status not in {"draft", "published"}:
            raise HTTPException(status_code=400, detail="Status invalid.")
        query = query.filter(models.Event.status == status)
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

    total = query.count()

    query = query.order_by(models.Event.start_time.desc(), models.Event.id.desc())
    query, _ = _events_with_counts_query(db, query)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    items = [_serialize_admin_event(event, seats_taken) for event, seats_taken in rows]
    return {"items": items, "total": int(total), "page": page, "page_size": page_size}


@app.post("/api/admin/events/{event_id}/moderation/review")
def admin_review_event_moderation(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
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


@app.post("/api/events/{event_id}/favorite", status_code=status.HTTP_201_CREATED)
def favorite_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
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


@app.delete("/api/events/{event_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    fav = (
        db.query(models.FavoriteEvent)
        .filter(models.FavoriteEvent.event_id == event_id, models.FavoriteEvent.user_id == current_user.id)
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favoritul nu există")
    db.delete(fav)
    db.commit()
    return


@app.get("/api/me/favorites", response_model=schemas.FavoriteListResponse)
def list_favorites(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_student)):
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
    query, seats_subquery = _events_with_counts_query(db, base_query)
    items = [_serialize_event(ev, seats) for ev, seats in query.order_by(models.Event.start_time).all()]
    return {"items": items}


@app.get("/api/me/events", response_model=List[schemas.EventResponse])
def my_events(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Allow both students and organizers to see events they registered for
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
    query, seats_subquery = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


@app.get("/api/recommendations", response_model=List[schemas.EventResponse])
def recommended_events(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    lang = current_user.language_preference
    if not lang or lang == "system":
        lang = request.headers.get("accept-language") or "ro"
    lang = (lang or "ro").split(",")[0][:2].lower()

    now = datetime.now(timezone.utc)
    user_city = (current_user.city or "").strip().lower()
    registered_event_ids = [
        e.event_id
        for e in db.query(models.Registration.event_id)
        .filter(models.Registration.user_id == current_user.id, models.Registration.deleted_at.is_(None))
        .all()
    ]
    hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=current_user.id)
    events = _load_cached_recommendations(
        db=db,
        user=current_user,
        now=now,
        registered_event_ids=registered_event_ids,
        lang=lang,
    )

    if not events:
        history_tag_names = [
            t[0]
            for t in (
                db.query(models.Tag.name)
                .join(models.event_tags, models.Tag.id == models.event_tags.c.tag_id)
                .join(models.Event, models.Event.id == models.event_tags.c.event_id)
                .join(models.Registration, models.Registration.event_id == models.Event.id)
                .filter(
                    models.Registration.user_id == current_user.id,
                    models.Registration.deleted_at.is_(None),
                    models.Event.deleted_at.is_(None),
                )
                .all()
            )
        ]

        profile_tag_names = [t.name for t in current_user.interest_tags]
        match_tag_names = list(dict.fromkeys([*history_tag_names, *profile_tag_names]))

        events: List[tuple[models.Event, int, Optional[str]]] = []
        if match_tag_names:
            lowered_match_tags = [name.lower() for name in match_tag_names]
            base_query = (
                db.query(models.Event)
                .filter(models.Event.tags.any(func.lower(models.Tag.name).in_(lowered_match_tags)))
                .filter(models.Event.deleted_at.is_(None))
                .filter(models.Event.start_time >= now)
                .filter(models.Event.status == "published")
                .filter((models.Event.publish_at == None) | (models.Event.publish_at <= now))  # noqa: E711
            )
            if registered_event_ids:
                base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
            base_query = _apply_personalization_exclusions(
                base_query,
                hidden_tag_ids=hidden_tag_ids,
                blocked_organizer_ids=blocked_organizer_ids,
            )
            base_query = base_query.order_by(models.Event.start_time, models.Event.id)
            query, seats_subquery = _events_with_counts_query(db, base_query)
            reason_parts: list[str] = []
            if history_tag_names:
                reason_parts.append(
                    (
                        f"Similar tags: {', '.join(sorted(set(history_tag_names))[:3])}"
                        if lang == "en"
                        else f"Etichete similare: {', '.join(sorted(set(history_tag_names))[:3])}"
                    )
                )
            if profile_tag_names:
                reason_parts.append(
                    (
                        f"Your interests: {', '.join(sorted(set(profile_tag_names))[:3])}"
                        if lang == "en"
                        else f"Interesele tale: {', '.join(sorted(set(profile_tag_names))[:3])}"
                    )
                )
            reason = " • ".join(reason_parts[:2]) if reason_parts else None
            events = [(ev, seats, reason) for ev, seats in query.limit(10).all()]

        if not events:
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
            events = [
                (ev, seats, fallback_reason)
                for ev, seats in query.order_by(
                    func.coalesce(seats_subquery.c.seats_taken, 0).desc(), models.Event.start_time
                )
                .limit(10)
                .all()
            ]

    filtered = []
    for event, seats, reason in events:
        if event.max_seats is not None and seats >= event.max_seats:
            continue
        is_local = bool(user_city and event.city and event.city.strip().lower() == user_city)
        final_reason = reason
        if is_local:
            suffix = f"Near you: {event.city}" if lang == "en" else f"În apropiere: {event.city}"
            final_reason = f"{reason} • {suffix}" if reason else suffix
        filtered.append((is_local, _serialize_event(event, seats, recommendation_reason=final_reason)))

    filtered.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in filtered[:10]]

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/events/{event_id}/ics")
def event_ics(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id, models.Event.deleted_at.is_(None)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    ics = "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EventLink//EN",
        _event_to_ics(event),
        "END:VCALENDAR",
    ])
    return Response(content=ics, media_type="text/calendar")


@app.get("/api/me/calendar")
def user_calendar(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
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
    vevents = [ _event_to_ics(e, uid_suffix=f"-u{current_user.id}") for e in regs ]
    ics = "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EventLink//EN",
        *vevents,
        "END:VCALENDAR",
    ])
    return Response(content=ics, media_type="text/calendar")


@app.post("/password/forgot")
def password_forgot(
    payload: schemas.PasswordResetRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    _enforce_rate_limit("password_forgot", request=request, identifier=payload.email.lower(), limit=5, window_seconds=300)
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
        send_email_async(background_tasks, db, user.email, subject, body, body_html, context={"user_id": user.id, "lang": lang})
    return {"status": "ok"}


@app.post("/password/reset")
def password_reset(payload: schemas.PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
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
