from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator
from .models import UserRole


ThemePreference = Literal["system", "light", "dark"]
StudyLevel = Literal["bachelor", "master", "phd", "medicine"]


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
        if not any(ch.isalpha() for ch in v) or not any(ch.isdigit() for ch in v):
            raise ValueError("Password must include letters and numbers")
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
    theme_preference: ThemePreference = "system"

    model_config = ConfigDict(from_attributes=True)

class ThemePreferenceUpdate(BaseModel):
    theme_preference: ThemePreference


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
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

    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: str = Field(..., min_length=2, max_length=100)
    start_time: datetime
    end_time: Optional[datetime] = None
    city: str = Field(..., min_length=2, max_length=100)
    location: str = Field(..., min_length=2, max_length=255)
    max_seats: int
    cover_url: Optional[HttpUrl] = None
    tags: List[str] = Field(default_factory=list)
    status: Optional[str] = Field(default="published", pattern="^(published|draft)$")
    publish_at: Optional[datetime] = None


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    location: Optional[str] = None
    max_seats: Optional[int] = None
    cover_url: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(default=None, pattern="^(published|draft)$")
    publish_at: Optional[datetime] = None


class EventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    city: Optional[str]
    location: Optional[str]
    max_seats: Optional[int]
    cover_url: Optional[str]
    owner_id: int
    owner_name: Optional[str]
    tags: List[TagResponse]
    seats_taken: int
    recommendation_reason: Optional[str] = None
    status: Optional[str] = None
    publish_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EventDetailResponse(EventResponse):
    is_registered: bool = False
    is_owner: bool = False
    available_seats: Optional[int] = None
    is_favorite: bool = False


class PublicEventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    city: Optional[str]
    location: Optional[str]
    max_seats: Optional[int]
    cover_url: Optional[str]
    organizer_name: Optional[str]
    tags: List[TagResponse]
    seats_taken: int


class PublicEventDetailResponse(PublicEventResponse):
    available_seats: Optional[int] = None


class PaginatedPublicEvents(BaseModel):
    items: List[PublicEventResponse]
    total: int
    page: int
    page_size: int


class ParticipantResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    registration_time: datetime
    attended: bool


class ParticipantListResponse(BaseModel):
    event_id: int
    title: str
    cover_url: Optional[str]
    seats_taken: int
    max_seats: Optional[int]
    city: Optional[str] = None
    participants: list[ParticipantResponse]
    total: int
    page: int
    page_size: int


class OrganizerProfileBase(BaseModel):
    org_name: Optional[str] = Field(None, max_length=255)
    org_description: Optional[str] = None
    org_logo_url: Optional[HttpUrl] = None
    org_website: Optional[str] = Field(None, max_length=255)


class OrganizerProfileResponse(OrganizerProfileBase):
    user_id: int
    email: EmailStr
    full_name: Optional[str] = None
    events: List[EventResponse] = []


class OrganizerProfileUpdate(OrganizerProfileBase):
    pass


class FavoriteListResponse(BaseModel):
    items: List[EventResponse]


class PaginatedEvents(BaseModel):
    items: List[EventResponse]
    total: int
    page: int
    page_size: int


class TagResponse(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TagListResponse(BaseModel):
    items: List[TagResponse]


class UniversityCatalogItem(BaseModel):
    name: str
    city: Optional[str] = None
    faculties: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)


class UniversityCatalogResponse(BaseModel):
    items: List[UniversityCatalogItem]


class StudentProfileResponse(BaseModel):
    user_id: int
    email: EmailStr
    full_name: Optional[str] = None
    city: Optional[str] = None
    university: Optional[str] = None
    faculty: Optional[str] = None
    study_level: Optional[StudyLevel] = None
    study_year: Optional[int] = None
    interest_tags: List[TagResponse] = []


class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    university: Optional[str] = Field(default=None, max_length=255)
    faculty: Optional[str] = Field(default=None, max_length=255)
    study_level: Optional[StudyLevel] = None
    study_year: Optional[int] = Field(default=None, ge=1, le=10)
    interest_tag_ids: Optional[List[int]] = None


class AdminUserUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None
    org_name: Optional[str] = None
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    is_active: bool
    registrations_count: int = 0
    attended_count: int = 0
    events_created_count: int = 0


class PaginatedAdminUsers(BaseModel):
    items: List[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminEventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    city: Optional[str] = None
    location: Optional[str] = None
    max_seats: Optional[int] = None
    cover_url: Optional[str] = None
    owner_id: int
    owner_email: EmailStr
    owner_name: Optional[str] = None
    tags: List[TagResponse] = []
    seats_taken: int = 0
    status: Optional[str] = None
    publish_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class PaginatedAdminEvents(BaseModel):
    items: List[AdminEventResponse]
    total: int
    page: int
    page_size: int


class RegistrationDayStat(BaseModel):
    date: str
    registrations: int


class TagPopularityStat(BaseModel):
    name: str
    registrations: int
    events: int


class AdminStatsResponse(BaseModel):
    total_users: int
    total_events: int
    total_registrations: int
    registrations_by_day: List[RegistrationDayStat]
    top_tags: List[TagPopularityStat]


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        pwd = info.data.get("new_password") if hasattr(info, "data") else None
        if pwd and v != pwd:
            raise ValueError("Parolele nu se potrivesc")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=255)
