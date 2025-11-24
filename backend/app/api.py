from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auth, models, schemas
from .config import settings
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Event Link API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _attach_tags(db: Session, event: models.Event, tag_names: List[str]):
    clean_names = {name.strip().lower() for name in tag_names if name.strip()}
    if not clean_names:
        event.tags = []
        return
    tags = []
    for name in clean_names:
        existing = db.query(models.Tag).filter(func.lower(models.Tag.name) == name).first()
        if not existing:
            existing = models.Tag(name=name)
            db.add(existing)
            db.flush()
        tags.append(existing)
    event.tags = tags


def _event_summary(db: Session, event: models.Event) -> schemas.EventSummary:
    registrations_count = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event.id)
        .count()
    )
    return schemas.EventSummary(
        id=event.id,
        title=event.title,
        category=event.category,
        event_date=event.event_date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        max_seats=event.max_seats,
        registrations_count=registrations_count,
    )


def send_registration_email(background_tasks: BackgroundTasks, user: models.User, event: models.Event):
    # Placeholder email sender; in a real system this would enqueue a message to an email service
    def _log_email():
        print(
            f"Sending email to {user.email}: Confirmare înscriere pentru {event.title} pe {event.event_date} la {event.location}"
        )

    background_tasks.add_task(_log_email)


@app.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user.confirm_password is not None and user.password != user.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        password_hash=hashed_password,
        role=user.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth.create_access_token(
        data={"sub": str(new_user.id), "role": new_user.role.value},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer", "user": new_user}


@app.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_credentials.email).first()
    if not user or not auth.verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = auth.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@app.get("/")
def read_root():
    return {"message": "Hello from Event Link API!"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/events", response_model=List[schemas.EventSummary])
def get_events(
    search: Optional[str] = None,
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Event).filter(models.Event.event_date >= func.now())

    if search:
        query = query.filter(func.lower(models.Event.title).contains(search.lower()))
    if category:
        query = query.filter(func.lower(models.Event.category) == category.lower())
    if start_date:
        query = query.filter(models.Event.event_date >= start_date)
    if end_date:
        query = query.filter(models.Event.event_date <= end_date)

    events = query.order_by(models.Event.event_date.asc()).all()
    return [_event_summary(db, e) for e in events]


@app.get("/api/events/{event_id}", response_model=schemas.EventDetail)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    detail = _event_summary(db, event).dict()
    detail.update(
        {
            "description": event.description,
            "owner_id": event.owner_id,
            "tags": event.tags,
        }
    )
    return detail


@app.post("/api/events", response_model=schemas.EventDetail)
def create_event(
    event: schemas.EventCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.organizator:
        raise HTTPException(status_code=403, detail="Only organizers can create events")

    if event.event_date.date() < datetime.utcnow().date():
        raise HTTPException(status_code=400, detail="Event date cannot be in the past")

    new_event = models.Event(
        title=event.title,
        description=event.description,
        category=event.category,
        event_date=event.event_date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        max_seats=event.max_seats,
        owner_id=current_user.id,
    )
    _attach_tags(db, new_event, event.tags)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return get_event(new_event.id, db)


@app.put("/api/events/{event_id}", response_model=schemas.EventDetail)
def update_event(
    event_id: int,
    event_update: schemas.EventUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this event")

    for field, value in event_update.dict(exclude_unset=True).items():
        if field == "tags" and value is not None:
            _attach_tags(db, event, value)
        else:
            setattr(event, field, value)

    db.commit()
    db.refresh(event)
    return get_event(event.id, db)


@app.delete("/api/events/{event_id}")
def delete_event(
    event_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to delete this event")

    db.delete(event)
    db.commit()
    return {"message": "Event deleted"}


@app.get("/api/organizer/events", response_model=List[schemas.EventSummary])
def get_organizer_events(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.organizator:
        raise HTTPException(status_code=403, detail="Only organizers can view their events")
    events = (
        db.query(models.Event)
        .filter(models.Event.owner_id == current_user.id)
        .order_by(models.Event.event_date.asc())
        .all()
    )
    return [_event_summary(db, e) for e in events]


@app.get("/api/events/{event_id}/participants")
def get_participants(
    event_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    registrations = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id)
        .all()
    )
    return {
        "count": len(registrations),
        "max_seats": event.max_seats,
        "participants": [
            {"id": reg.user.id, "email": reg.user.email}
            for reg in registrations
        ],
    }


@app.post("/api/events/{event_id}/register", response_model=schemas.Registration)
def register_for_event(
    event_id: int,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can register")
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    current_count = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id)
        .count()
    )
    if event.max_seats and current_count >= event.max_seats:
        raise HTTPException(status_code=409, detail="Event is full")

    existing = (
        db.query(models.Registration)
        .filter(models.Registration.event_id == event_id, models.Registration.user_id == current_user.id)
        .first()
    )
    if existing:
        return existing

    registration = models.Registration(user_id=current_user.id, event_id=event_id)
    db.add(registration)
    db.commit()
    db.refresh(registration)
    send_registration_email(background_tasks, current_user, event)
    return registration


@app.get("/api/my-registrations", response_model=List[schemas.EventSummary])
def my_registrations(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    registrations = (
        db.query(models.Event)
        .join(models.Registration, models.Event.id == models.Registration.event_id)
        .filter(models.Registration.user_id == current_user.id)
        .order_by(models.Event.event_date.asc())
        .all()
    )
    return [_event_summary(db, e) for e in registrations]


@app.get("/api/recommended", response_model=List[schemas.EventSummary])
def recommended(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.student:
        return []

    # Collect tags from registered events
    registered_event_ids = [r.event_id for r in current_user.registrations]
    if registered_event_ids:
        tag_ids = (
            db.query(models.event_tags.c.tag_id)
            .filter(models.event_tags.c.event_id.in_(registered_event_ids))
            .distinct()
        ).subquery()
        events = (
            db.query(models.Event)
            .join(models.event_tags, models.Event.id == models.event_tags.c.event_id)
            .filter(models.event_tags.c.tag_id.in_(tag_ids))
            .filter(models.Event.id.notin_(registered_event_ids))
            .filter(models.Event.event_date >= func.now())
            .all()
        )
    else:
        # fallback: most popular upcoming
        events = (
            db.query(models.Event)
            .filter(models.Event.event_date >= func.now())
            .order_by(models.Event.event_date.asc())
            .limit(5)
            .all()
        )
    # remove duplicates
    seen = set()
    unique_events = []
    for e in events:
        if e.id not in seen:
            seen.add(e.id)
            unique_events.append(e)
    return [_event_summary(db, e) for e in unique_events]

