from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from .models import UserRole


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class StudentRegister(UserCreate):
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        password = info.data.get("password") if hasattr(info, "data") else None
        if password and v != password:
            raise ValueError("Passwords do not match")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True


class OrganizerUpgradeRequest(BaseModel):
    invite_code: str


class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole
    user_id: int


class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None
    user_id: Optional[int] = None


class TagResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    start_time: datetime
    end_time: Optional[datetime] = None
    location: str
    max_seats: int
    cover_url: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    max_seats: Optional[int] = None
    cover_url: Optional[str] = None
    tags: Optional[List[str]] = None


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    location: Optional[str]
    max_seats: Optional[int]
    cover_url: Optional[str]
    owner_id: int
    owner_name: Optional[str]
    tags: List[TagResponse]
    seats_taken: int

    class Config:
        from_attributes = True


class EventDetailResponse(EventResponse):
    is_registered: bool = False
    is_owner: bool = False
    available_seats: Optional[int] = None


class ParticipantResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    registration_time: datetime
    attended: bool


class ParticipantListResponse(BaseModel):
    event_id: int
    title: str
    seats_taken: int
    max_seats: Optional[int]
    participants: list[ParticipantResponse]


class PaginatedEvents(BaseModel):
    items: List[EventResponse]
    total: int
    page: int
    page_size: int
