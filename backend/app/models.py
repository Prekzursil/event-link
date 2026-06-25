"""SQLAlchemy models for the event-link backend."""

# SQLAlchemy ORM classes are column declarations — no public methods needed.
# pylint: disable=too-few-public-methods

import enum
from datetime import datetime
from typing import Any, Optional
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
    Float,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import Base

USER_ID_FK = "users.id"
EVENT_ID_FK = "events.id"
TAG_ID_FK = "tags.id"
CASCADE_DELETE_ORPHAN = "all, delete-orphan"


class UserRole(str, enum.Enum):
    """Supported application roles."""

    # Enum members use lowercase to match the values serialized on the wire /
    # stored in the database; changing them would force a schema migration.
    # pylint: disable=invalid-name
    student = "student"
    organizator = "organizator"
    admin = "admin"


class User(Base):
    """Application user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    org_name: Mapped[Optional[str]] = mapped_column(String(255))
    org_description: Mapped[Optional[str]] = mapped_column(Text)
    org_logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    org_website: Mapped[Optional[str]] = mapped_column(String(255))
    theme_preference: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="system", default="system"
    )
    language_preference: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="system", default="system"
    )
    city: Mapped[Optional[str]] = mapped_column(String(100))
    university: Mapped[Optional[str]] = mapped_column(String(255))
    faculty: Mapped[Optional[str]] = mapped_column(String(255))
    study_level: Mapped[Optional[str]] = mapped_column(String(20))
    study_year: Mapped[Optional[int]] = mapped_column(Integer)
    email_digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    email_filling_fast_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    events = relationship(
        "Event", back_populates="owner", foreign_keys="Event.owner_id"
    )
    registrations = relationship(
        "Registration",
        back_populates="user",
        cascade=CASCADE_DELETE_ORPHAN,
        foreign_keys="Registration.user_id",
    )
    favorites = relationship(
        "FavoriteEvent", back_populates="user", cascade=CASCADE_DELETE_ORPHAN
    )
    interest_tags = relationship("Tag", secondary="user_interest_tags")


class Tag(Base):
    """Canonical event tag."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    events = relationship("Event", secondary="event_tags", back_populates="tags")


class Event(Base):
    """Event created by an organizer."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    start_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    location: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    max_seats: Mapped[Optional[int]] = mapped_column(Integer)
    cover_url: Mapped[Optional[str]] = mapped_column(String(500))
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="published"
    )
    publish_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    moderation_score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0", default=0.0
    )
    moderation_flags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    moderation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="clean", default="clean"
    )
    moderation_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    moderation_reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=True
    )

    owner = relationship("User", back_populates="events", foreign_keys=[owner_id])
    registrations = relationship(
        "Registration", back_populates="event", cascade=CASCADE_DELETE_ORPHAN
    )
    tags = relationship("Tag", secondary="event_tags", back_populates="events")
    favorites = relationship(
        "FavoriteEvent", back_populates="event", cascade=CASCADE_DELETE_ORPHAN
    )
    deleted_by = relationship("User", foreign_keys=[deleted_by_user_id])
    moderation_reviewed_by = relationship(
        "User", foreign_keys=[moderation_reviewed_by_user_id]
    )


class Registration(Base):
    """Student registration for an event."""

    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_registration"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False
    )
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(EVENT_ID_FK), nullable=False
    )
    registration_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=True
    )
    attended: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    deleted_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=True
    )

    user = relationship("User", back_populates="registrations", foreign_keys=[user_id])
    event = relationship("Event", back_populates="registrations")
    deleted_by = relationship("User", foreign_keys=[deleted_by_user_id])


class FavoriteEvent(Base):
    """User bookmark of an event."""

    __tablename__ = "favorite_events"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_favorite_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False
    )
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(EVENT_ID_FK), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="favorites")
    event = relationship("Event", back_populates="favorites")


class PasswordResetToken(Base):
    """Single-use password reset token."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    used: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User")


class BackgroundJob(Base):
    """Persisted background task queue item."""

    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("job_type", "dedupe_key", name="uq_background_job_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dedupe_key: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True
    )
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True, server_default="queued"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3"
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    locked_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class NotificationDelivery(Base):
    """Recorded outbound notification delivery."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notification_delivery_dedupe_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False, index=True
    )
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(EVENT_ID_FK), nullable=True, index=True
    )
    sent_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    meta: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    event = relationship("Event", foreign_keys=[event_id])


class AuditLog(Base):
    """Audit trail entry for administrative actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    meta: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])


class UserRecommendation(Base):
    """Stored recommendation scored for a user-event pair."""

    __tablename__ = "user_recommendations"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_user_recommendation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False, index=True
    )
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(EVENT_ID_FK), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    event = relationship("Event", foreign_keys=[event_id])


class RecommenderModel(Base):
    """Metadata and weights for a trained recommender model."""

    __tablename__ = "recommender_models"
    __table_args__ = (
        UniqueConstraint("model_version", name="uq_recommender_models_model_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    feature_names: Mapped[Any] = mapped_column(JSON, nullable=False)
    weights: Mapped[Any] = mapped_column(JSON, nullable=False)
    meta: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class EventInteraction(Base):
    """Behavioral interaction recorded against an event."""

    __tablename__ = "event_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=True, index=True
    )
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey(EVENT_ID_FK), nullable=True, index=True
    )
    interaction_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    meta: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    event = relationship("Event", foreign_keys=[event_id])


class UserImplicitInterestTag(Base):
    """Derived tag affinity for a user."""

    __tablename__ = "user_implicit_interest_tags"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_id", name="uq_user_implicit_interest_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(TAG_ID_FK), nullable=False, index=True
    )
    score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0", default=1.0
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])
    tag = relationship("Tag", foreign_keys=[tag_id])


class UserImplicitInterestCategory(Base):
    """Derived category affinity for a user."""

    __tablename__ = "user_implicit_interest_categories"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", name="uq_user_implicit_interest_category"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0", default=1.0
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])


class UserImplicitInterestCity(Base):
    """Derived city affinity for a user."""

    __tablename__ = "user_implicit_interest_cities"
    __table_args__ = (
        UniqueConstraint("user_id", "city", name="uq_user_implicit_interest_city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(USER_ID_FK), nullable=False, index=True
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0", default=1.0
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])


event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", Integer, ForeignKey(EVENT_ID_FK), primary_key=True),
    Column("tag_id", Integer, ForeignKey(TAG_ID_FK), primary_key=True),
)


# User interest tags - tags that students are interested in for recommendations
user_interest_tags = Table(
    "user_interest_tags",
    Base.metadata,
    Column("user_id", Integer, ForeignKey(USER_ID_FK), primary_key=True),
    Column("tag_id", Integer, ForeignKey(TAG_ID_FK), primary_key=True),
)


# User hidden tags - tags that students want to hide from feeds/recommendations
user_hidden_tags = Table(
    "user_hidden_tags",
    Base.metadata,
    Column("user_id", Integer, ForeignKey(USER_ID_FK), primary_key=True),
    Column("tag_id", Integer, ForeignKey(TAG_ID_FK), primary_key=True),
)


# User blocked organizers that students want to mute from recommendations.
user_blocked_organizers = Table(
    "user_blocked_organizers",
    Base.metadata,
    Column("user_id", Integer, ForeignKey(USER_ID_FK), primary_key=True),
    Column("organizer_id", Integer, ForeignKey(USER_ID_FK), primary_key=True),
)
