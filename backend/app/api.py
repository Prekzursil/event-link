from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
import time

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .config import settings
from .database import engine, get_db
from .email_service import send_registration_email
from .logging_utils import configure_logging, RequestIdMiddleware, log_event, log_warning

configure_logging()

app = FastAPI(title="Event Link API", version="1.0.0")

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup():
    if settings.auto_create_tables:
        models.Base.metadata.create_all(bind=engine)


def _ensure_future_date(start_time: datetime) -> None:
    start_time = _normalize_dt(start_time)
    if start_time and start_time < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data evenimentului nu poate fi în trecut.")


def _normalize_dt(value: Optional[datetime]) -> Optional[datetime]:
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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
    _enforce_rate_limit(request, "register")
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
    access_token = auth.create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email, "role": new_user.role.value},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer", "role": new_user.role, "user_id": new_user.id}


@app.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    _enforce_rate_limit(request, "login")
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    if not user or not auth.verify_password(user_credentials.password, user.password_hash):
        log_warning("login_failed", email=user_credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorectă",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth.create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}, expires_delta=access_token_expires
    )
    log_event("login_success", user_id=user.id, email=user.email, role=user.role.value)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "user_id": user.id}


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


def _enforce_rate_limit(request: Request, action: str, limit: int = 20, window_seconds: int = 60) -> None:
    now = time.time()
    key = f"{action}:{request.client.host if request.client else 'unknown'}"
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
    if event.cover_url and len(event.cover_url) > 500:
        raise HTTPException(status_code=400, detail="Cover URL prea lung.")

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
        if update.cover_url and len(update.cover_url) > 500:
            raise HTTPException(status_code=400, detail="Cover URL prea lung.")
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

    subject = f"Confirmare înscriere: {event.title}"
    body = (
        f"Bună {current_user.full_name or current_user.email},\n\n"
        f"Te-ai înscris la evenimentul '{event.title}'.\n"
        f"Data și ora de start: {event.start_time}.\n"
        f"Locația: {event.location}.\n\n"
        "Ne vedem acolo!"
    )
    send_registration_email(
        background_tasks,
        current_user.email,
        subject,
        body,
        context={"user_id": current_user.id, "event_id": event.id},
    )
    return {"status": "registered"}


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
