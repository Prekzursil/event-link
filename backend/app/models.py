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

    events = relationship("Event", back_populates="owner")
    registrations = relationship("Registration", back_populates="user")


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
    event_date = Column(TIMESTAMP(timezone=True), nullable=False)
    location = Column(String(255))
    max_seats = Column(Integer)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="events")
    registrations = relationship("Registration", back_populates="event")
    tags = relationship("Tag", secondary="event_tags", back_populates="events")


class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    registration_time = Column(TIMESTAMP(timezone=True), server_default="CURRENT_TIMESTAMP")

    user = relationship("User", back_populates="registrations")
    event = relationship("Event", back_populates="registrations")


event_tags = Table(
    "event_tags",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)
