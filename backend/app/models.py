import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    TIMESTAMP,
    ForeignKey,
    Enum,
    Table,
    UniqueConstraint,
    func,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship
from .database import Base


class UserRole(str, enum.Enum):
    student = "student"
    organizator = "organizator"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    full_name = Column(String(255))
    org_name = Column(String(255))
    org_description = Column(Text)
    org_logo_url = Column(String(500))
    org_website = Column(String(255))

    events = relationship("Event", back_populates="owner", foreign_keys="Event.owner_id")
    registrations = relationship(
        "Registration",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Registration.user_id",
    )
    favorites = relationship("FavoriteEvent", back_populates="user", cascade="all, delete-orphan")
    interest_tags = relationship("Tag", secondary="user_interest_tags")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    events = relationship("Event", secondary="event_tags", back_populates="tags")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    start_time = Column(TIMESTAMP(timezone=True), nullable=False)
    end_time = Column(TIMESTAMP(timezone=True), nullable=True)
    location = Column(String(255))
    max_seats = Column(Integer)
    cover_url = Column(String(500))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(String(20), nullable=False, server_default="published")
    publish_at = Column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    owner = relationship("User", back_populates="events", foreign_keys=[owner_id])
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary="event_tags", back_populates="events")
    favorites = relationship("FavoriteEvent", back_populates="event", cascade="all, delete-orphan")
    deleted_by = relationship("User", foreign_keys=[deleted_by_user_id])


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_registration"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    registration_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    attended = Column(Boolean, server_default="false", nullable=False)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="registrations", foreign_keys=[user_id])
    event = relationship("Event", back_populates="registrations")
    deleted_by = relationship("User", foreign_keys=[deleted_by_user_id])


class FavoriteEvent(Base):
    __tablename__ = "favorite_events"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_favorite_event"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="favorites")
    event = relationship("Event", back_populates="favorites")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used = Column(Boolean, server_default="false", nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, index=True, server_default="queued")
    attempts = Column(Integer, nullable=False, server_default="0")
    max_attempts = Column(Integer, nullable=False, server_default="3")
    run_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False, index=True)
    locked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    locked_by = Column(String(100), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    meta = Column(JSON, nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])


event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


# User interest tags - tags that students are interested in for recommendations
user_interest_tags = Table(
    "user_interest_tags",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)
