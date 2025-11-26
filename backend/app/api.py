from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
import time
import re
import logging
import asyncio
import os
import secrets
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .config import settings
from .database import engine, get_db, SessionLocal
from .email_service import send_registration_email, send_registration_email as send_email
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


app = FastAPI(title="Event Link API", version="1.0.0")

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _validate_cover_url(url: str) -> None:
    pattern = re.compile(r"^https?://")
    if url and not pattern.match(url):
        raise HTTPException(status_code=400, detail="Cover URL trebuie să fie un link http/https valid.")


@app.on_event("startup")
def _on_startup():
    _check_configuration()
    if getattr(settings, "auto_run_migrations", False):
        _run_migrations()
    elif settings.auto_create_tables:
        models.Base.metadata.create_all(bind=engine)
    try:
        asyncio.get_event_loop().create_task(_cleanup_loop())
    except RuntimeError:
        # Fallback for sync contexts
        import threading
        threading.Thread(target=lambda: asyncio.run(_cleanup_loop()), daemon=True).start()


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
            .filter((models.PasswordResetToken.used == True) | (models.PasswordResetToken.expires_at < now))
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
    cleaned = {name.strip().lower() for name in tag_names if name and name.strip()}
    tags: list[models.Tag] = []
    for name in cleaned:
        tag = db.query(models.Tag).filter(func.lower(models.Tag.name) == name.lower()).first()
        if not tag:
            tag = models.Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    event.tags = tags


def _events_with_counts_query(db: Session, base_query=None):
    if base_query is None:
        base_query = db.query(models.Event)
    seats_subquery = (
        db.query(
            models.Registration.event_id,
            func.count(models.Registration.id).label("seats_taken"),
        )
        .group_by(models.Registration.event_id)
        .subquery()
    )
    query = (
        base_query.outerjoin(seats_subquery, models.Event.id == seats_subquery.c.event_id)
        .add_columns(func.coalesce(seats_subquery.c.seats_taken, 0).label("seats_taken"))
    )
    return query, seats_subquery


def _serialize_event(event: models.Event, seats_taken: int) -> schemas.EventResponse:
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
        location=event.location,
        max_seats=event.max_seats,
        owner_id=event.owner_id,
        owner_name=owner_name,
        tags=event.tags,
        seats_taken=int(seats_taken or 0),
        cover_url=event.cover_url,
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


@app.post("/organizer/upgrade")
def upgrade_to_organizer(
    request: schemas.OrganizerUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.role == models.UserRole.organizator:
        return {"status": "already_organizer"}
    if not settings.organizer_invite_code or request.invite_code != settings.organizer_invite_code:
        raise HTTPException(status_code=403, detail="Cod invalid sau lipsă.")
    current_user.role = models.UserRole.organizator
    db.add(current_user)
    db.commit()
    return {"status": "upgraded"}


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


@app.get("/api/events", response_model=schemas.PaginatedEvents)
def get_events(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    include_past: bool = False,
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
    query = db.query(models.Event)
    if not include_past:
        query = query.filter(models.Event.start_time >= now)
    if search:
        query = query.filter(func.lower(models.Event.title).like(f"%{search.lower()}%"))
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.filter(models.Event.start_time <= end_dt)
    total = query.count()
    query = query.order_by(models.Event.start_time)
    query, seats_subquery = _events_with_counts_query(db, query)
    query = query.offset((page - 1) * page_size).limit(page_size)
    events = query.all()
    items = [_serialize_event(event, seats) for event, seats in events]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/api/events/{event_id}", response_model=schemas.EventDetailResponse)
def get_event(event_id: int, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_optional_user)):
    query, seats_subquery = _events_with_counts_query(db, db.query(models.Event).filter(models.Event.id == event_id))
    result = query.first()
    if not result:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    event, seats_taken = result
    is_registered = False
    if current_user:
        is_registered = (
            db.query(models.Registration)
            .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
            .first()
            is not None
        )
    available_seats = event.max_seats - seats_taken if event.max_seats is not None else None
    owner_name = event.owner.full_name or event.owner.email if event.owner else None
    return schemas.EventDetailResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        category=event.category,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        owner_id=event.owner_id,
        owner_name=owner_name,
        tags=event.tags,
        seats_taken=seats_taken or 0,
        is_registered=is_registered,
        is_owner=current_user.id == event.owner_id if current_user else False,
        available_seats=available_seats,
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
        location=event.location,
        max_seats=event.max_seats,
        cover_url=event.cover_url,
        owner_id=current_user.id,
    )
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
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if db_event.owner_id != current_user.id:
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

    db.commit()
    db.refresh(db_event)
    log_event("event_updated", event_id=db_event.id, owner_id=current_user.id)
    seats_count = (
        db.query(func.count(models.Registration.id))
        .filter(models.Registration.event_id == db_event.id)
        .scalar()
    ) or 0
    return _serialize_event(db_event, seats_count)


@app.delete("/api/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_organizer)):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if db_event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să ștergeți acest eveniment.")

    db.delete(db_event)
    db.commit()
    log_event("event_deleted", event_id=db_event.id, owner_id=current_user.id)
    return


@app.get("/api/organizer/events", response_model=List[schemas.EventResponse])
def organizer_events(
    db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_organizer)
):
    base_query = db.query(models.Event).filter(models.Event.owner_id == current_user.id).order_by(models.Event.start_time)
    query, seats_subquery = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


@app.get("/api/organizer/events/{event_id}/participants", response_model=schemas.ParticipantListResponse)
def event_participants(
    event_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_organizer)
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să accesați acest eveniment.")

    participants = (
        db.query(models.User, models.Registration.registration_time, models.Registration.attended)
        .join(models.Registration, models.User.id == models.Registration.user_id)
        .filter(models.Registration.event_id == event_id)
        .order_by(models.Registration.registration_time)
        .all()
    )
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
    seats_taken = len(participants)
    return schemas.ParticipantListResponse(
        event_id=event.id,
        title=event.title,
        cover_url=event.cover_url,
        seats_taken=seats_taken,
        max_seats=event.max_seats,
        participants=participant_list,
    )


@app.put("/api/organizer/events/{event_id}/participants/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_participant_attendance(
    event_id: int,
    user_id: int,
    attended: bool,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_organizer),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu aveți dreptul să modificați acest eveniment.")

    registration = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == user_id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Participarea nu a fost găsită.")

    registration.attended = attended
    db.add(registration)
    db.commit()
    log_event("attendance_updated", event_id=registration.event_id, user_id=user_id, owner_id=current_user.id, attended=attended)
    return


@app.post("/api/events/{event_id}/register", status_code=status.HTTP_201_CREATED)
def register_for_event(
    event_id: int,
    background_tasks: BackgroundTasks,
    request: Request | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    now = datetime.now(timezone.utc)
    start_time = _normalize_dt(event.start_time)
    if start_time and start_time < now:
        raise HTTPException(status_code=400, detail="Evenimentul a început deja.")

    seats_taken = (
        db.query(func.count(models.Registration.id)).filter(models.Registration.event_id == event_id).scalar() or 0
    )
    if event.max_seats is not None and seats_taken >= event.max_seats:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evenimentul este plin.")

    existing = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ești deja înscris la eveniment.")

    registration = models.Registration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    db.commit()
    log_event("event_registered", event_id=event.id, user_id=current_user.id)

    lang = (request.headers.get("accept-language") if request else None) or "ro"
    subject, body_text, body_html = render_registration_email(event, current_user, lang=lang)
    send_registration_email(
        background_tasks,
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
    request: Request | None = None,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    _enforce_rate_limit("resend_registration", request=request, identifier=current_user.email.lower(), limit=3, window_seconds=600)
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    registration = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=400, detail="Nu ești înscris la acest eveniment.")

    lang = (request.headers.get("accept-language") or "ro")
    subject, body_text, body_html = render_registration_email(event, current_user, lang=lang)
    send_registration_email(
        background_tasks,
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
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evenimentul nu există")
    now = datetime.now(timezone.utc)
    start_time = _normalize_dt(event.start_time)
    if start_time and start_time < now:
        raise HTTPException(status_code=400, detail="Nu te poți dezabona după ce evenimentul a început.")

    registration = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=400, detail="Nu ești înscris la acest eveniment.")

    db.delete(registration)
    db.commit()
    log_event("event_unregistered", event_id=event.id, user_id=current_user.id)
    return


@app.get("/api/me/events", response_model=List[schemas.EventResponse])
def my_events(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    current_user = auth.require_student(current_user)
    base_query = (
        db.query(models.Event)
        .join(models.Registration, models.Event.id == models.Registration.event_id)
        .filter(models.Registration.user_id == current_user.id)
        .order_by(models.Event.start_time)
    )
    query, seats_subquery = _events_with_counts_query(db, base_query)
    events = query.all()
    return [_serialize_event(event, seats) for event, seats in events]


@app.get("/api/recommendations", response_model=List[schemas.EventResponse])
def recommended_events(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_student),
):
    now = datetime.now(timezone.utc)
    registered_event_ids = [
        e.event_id
        for e in db.query(models.Registration.event_id)
        .filter(models.Registration.user_id == current_user.id)
        .all()
    ]
    tag_names = [
        t[0]
        for t in (
            db.query(models.Tag.name)
            .join(models.event_tags, models.Tag.id == models.event_tags.c.tag_id)
            .join(models.Event, models.Event.id == models.event_tags.c.event_id)
            .join(models.Registration, models.Registration.event_id == models.Event.id)
            .filter(models.Registration.user_id == current_user.id)
            .all()
        )
    ]

    events: List[tuple[models.Event, int]] = []
    if tag_names:
        base_query = (
            db.query(models.Event)
            .join(models.Event.tags)
            .filter(func.lower(models.Tag.name).in_([name.lower() for name in tag_names]))
            .filter(models.Event.start_time >= now)
        )
        if registered_event_ids:
            base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
        base_query = base_query.distinct().order_by(models.Event.start_time)
        query, seats_subquery = _events_with_counts_query(db, base_query)
        events = query.limit(10).all()

    if not events:
        base_query = db.query(models.Event).filter(models.Event.start_time >= now)
        if registered_event_ids:
            base_query = base_query.filter(~models.Event.id.in_(registered_event_ids))
        query, seats_subquery = _events_with_counts_query(db, base_query)
        events = query.order_by(func.coalesce(seats_subquery.c.seats_taken, 0).desc(), models.Event.start_time).limit(10).all()

    filtered = []
    for event, seats in events:
        if event.max_seats is not None and seats >= event.max_seats:
            continue
        filtered.append(_serialize_event(event, seats))
    return filtered[:10]

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/events/{event_id}/ics")
def event_ics(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
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
        .filter(models.Registration.user_id == current_user.id)
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
    request: Request | None = None,
    db: Session = Depends(get_db),
):
    _enforce_rate_limit("password_forgot", request=request, identifier=payload.email.lower(), limit=5, window_seconds=300)
    user = db.query(models.User).filter(func.lower(models.User.email) == payload.email.lower()).first()
    if user:
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id, models.PasswordResetToken.used == False
        ).update({"used": True})
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset = models.PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at, used=False)
        db.add(reset)
        db.commit()
        frontend_hint = settings.allowed_origins[0] if settings.allowed_origins else ""
        link = f"{frontend_hint}/reset-password?token={token}" if frontend_hint else token
        lang = (request.headers.get("accept-language") if request else None) or "ro"
        subject, body, body_html = render_password_reset_email(user, link, lang=lang)
        send_email(background_tasks, user.email, subject, body, body_html, context={"user_id": user.id, "lang": lang})
    return {"status": "ok"}


@app.post("/password/reset")
def password_reset(payload: schemas.PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    _enforce_rate_limit("password_reset", request=request, limit=10, window_seconds=300)
    token_row = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token == payload.token, models.PasswordResetToken.used == False)
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
