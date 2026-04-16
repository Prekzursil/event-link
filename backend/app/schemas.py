"""Pydantic schemas for API requests and responses."""

from datetime import date, datetime
from typing import Any, List, Optional, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
)
from .models import UserRole

ThemePreference = Literal["system", "light", "dark"]
LanguagePreference = Literal["system", "ro", "en"]
StudyLevel = Literal["bachelor", "master", "phd", "medicine"]


class UserBase(BaseModel):
    """Shared user identity fields."""

    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None


class UserCreate(BaseModel):
    """Payload for creating a basic user account."""

    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Enforce the application's minimum password requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(ch.isalpha() for ch in v) or not any(ch.isdigit() for ch in v):
            raise ValueError("Password must include letters and numbers")
        return v


class StudentRegister(UserCreate):
    """Payload for registering a student account."""

    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        """Confirm the repeated password matches the original value."""
        password = info.data.get("password") if hasattr(info, "data") else None
        if password and v != password:
            raise ValueError("Passwords do not match")
        return v


class UserLogin(BaseModel):
    """Credentials used for user login."""

    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Serialized user returned by API endpoints."""

    id: int
    theme_preference: ThemePreference = "system"
    language_preference: LanguagePreference = "system"

    model_config = ConfigDict(from_attributes=True)


class ThemePreferenceUpdate(BaseModel):
    """Theme preference update payload."""

    theme_preference: ThemePreference


class LanguagePreferenceUpdate(BaseModel):
    """Language preference update payload."""

    language_preference: LanguagePreference


class Token(BaseModel):
    """Authentication tokens returned after login or refresh."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    role: UserRole
    user_id: int


class TokenData(BaseModel):
    """JWT payload fields extracted from a token."""

    email: Optional[str] = None
    role: Optional[UserRole] = None
    user_id: Optional[int] = None


class TagResponse(BaseModel):
    """Serialized tag."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class EventBase(BaseModel):
    """Shared event payload fields."""

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
    """Payload for creating an event."""


class EventUpdate(BaseModel):
    """Payload for updating an existing event."""

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
    """Serialized event for authenticated endpoints."""

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
    owner_name: Optional[str] = None
    tags: List[TagResponse]
    seats_taken: int
    recommendation_reason: Optional[str] = None
    status: Optional[str] = None
    publish_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EventDetailResponse(EventResponse):
    """Detailed event payload for authenticated viewers."""

    is_registered: bool = False
    is_owner: bool = False
    available_seats: Optional[int] = None
    is_favorite: bool = False


class PublicEventResponse(BaseModel):
    """Serialized event for public listings."""

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
    organizer_name: Optional[str] = None
    tags: List[TagResponse]
    seats_taken: int


class PublicEventDetailResponse(PublicEventResponse):
    """Detailed event payload for public viewers."""

    available_seats: Optional[int] = None


class PaginatedPublicEvents(BaseModel):
    """Paginated public event listing."""

    items: List[PublicEventResponse]
    total: int
    page: int
    page_size: int


class ParticipantResponse(BaseModel):
    """Serialized participant entry for organizer views."""

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    registration_time: datetime
    attended: bool


class ParticipantListResponse(BaseModel):
    """Paginated participant list for a single event."""

    event_id: int
    title: str
    cover_url: Optional[str] = None
    seats_taken: int
    max_seats: Optional[int] = None
    city: Optional[str] = None
    participants: list[ParticipantResponse]
    total: int
    page: int
    page_size: int


class OrganizerProfileBase(BaseModel):
    """Shared organizer profile fields."""

    org_name: Optional[str] = Field(None, max_length=255)
    org_description: Optional[str] = None
    org_logo_url: Optional[HttpUrl] = None
    org_website: Optional[str] = Field(None, max_length=255)


class OrganizerProfileResponse(OrganizerProfileBase):
    """Organizer profile returned by the API."""

    user_id: int
    email: EmailStr
    full_name: Optional[str] = None
    events: List[EventResponse] = Field(default_factory=list)


class OrganizerProfileUpdate(OrganizerProfileBase):
    """Payload for updating organizer profile details."""


class FavoriteListResponse(BaseModel):
    """List of favorited events."""

    items: List[EventResponse]


class EventListQuery(BaseModel):
    """Query parameters for organizer and admin event listings."""

    search: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    tags: List[str] = Field(default_factory=list)
    tags_csv: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    include_past: bool = False
    sort: Optional[str] = None
    page: int = 1
    page_size: int = 10


class PaginatedEvents(BaseModel):
    """Paginated event listing for authenticated endpoints."""

    items: List[EventResponse]
    total: int
    page: int
    page_size: int


class TagListResponse(BaseModel):
    """List of tags."""

    items: List[TagResponse]


class UniversityCatalogItem(BaseModel):
    """University catalog entry returned by the API."""

    name: str
    city: Optional[str] = None
    faculties: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)


class UniversityCatalogResponse(BaseModel):
    """Full university catalog response."""

    items: List[UniversityCatalogItem]


class StudentProfileResponse(BaseModel):
    """Student profile returned by the API."""

    user_id: int
    email: EmailStr
    full_name: Optional[str] = None
    city: Optional[str] = None
    university: Optional[str] = None
    faculty: Optional[str] = None
    study_level: Optional[StudyLevel] = None
    study_year: Optional[int] = None
    interest_tags: List[TagResponse] = Field(default_factory=list)


class StudentProfileUpdate(BaseModel):
    """Payload for updating student profile details."""

    full_name: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    university: Optional[str] = Field(default=None, max_length=255)
    faculty: Optional[str] = Field(default=None, max_length=255)
    study_level: Optional[StudyLevel] = None
    study_year: Optional[int] = Field(default=None, ge=1, le=10)
    interest_tag_ids: Optional[List[int]] = None


class OrganizerSummaryResponse(BaseModel):
    """Compact organizer identity used in personalization settings."""

    id: int
    email: EmailStr
    full_name: Optional[str] = None
    org_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PersonalizationSettingsResponse(BaseModel):
    """User-specific personalization settings."""

    hidden_tags: List[TagResponse] = Field(default_factory=list)
    blocked_organizers: List[OrganizerSummaryResponse] = Field(default_factory=list)


class NotificationPreferencesResponse(BaseModel):
    """Current notification preference settings."""

    email_digest_enabled: bool
    email_filling_fast_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    """Payload for updating notification preferences."""

    email_digest_enabled: Optional[bool] = None
    email_filling_fast_enabled: Optional[bool] = None


class AdminUserUpdate(BaseModel):
    """Administrative update payload for a user."""

    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    """Administrative view of a user."""

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
    """Paginated admin user listing."""

    items: List[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminEventResponse(BaseModel):
    """Administrative view of an event."""

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
    tags: List[TagResponse] = Field(default_factory=list)
    seats_taken: int = 0
    status: Optional[str] = None
    publish_at: Optional[datetime] = None
    moderation_score: float = 0.0
    moderation_status: Optional[str] = None
    moderation_flags: Optional[list[str]] = None
    moderation_reviewed_at: Optional[datetime] = None
    moderation_reviewed_by_user_id: Optional[int] = None
    deleted_at: Optional[datetime] = None


class PaginatedAdminEvents(BaseModel):
    """Paginated admin event listing."""

    items: List[AdminEventResponse]
    total: int
    page: int
    page_size: int


class AdminEventListQuery(BaseModel):
    """Query parameters for admin event listings."""

    search: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    include_deleted: bool = False
    flagged_only: bool = False
    page: int = 1
    page_size: int = 20


class RegistrationDayStat(BaseModel):
    """Registration volume for a single day."""

    date: str
    registrations: int


class TagPopularityStat(BaseModel):
    """Popularity metrics for a single tag."""

    name: str
    registrations: int
    events: int


class AdminStatsResponse(BaseModel):
    """Administrative statistics summary."""

    total_users: int
    total_events: int
    total_registrations: int
    registrations_by_day: List[RegistrationDayStat]
    top_tags: List[TagPopularityStat]


class PersonalizationMetricsDay(BaseModel):
    """Daily personalization performance metrics."""

    date: str
    impressions: int
    clicks: int
    registrations: int
    ctr: float
    registration_conversion: float


class PersonalizationMetricsTotals(BaseModel):
    """Aggregate personalization performance metrics."""

    impressions: int
    clicks: int
    registrations: int
    ctr: float
    registration_conversion: float


class PersonalizationMetricsResponse(BaseModel):
    """Time-series and totals for personalization metrics."""

    items: List[PersonalizationMetricsDay]
    totals: PersonalizationMetricsTotals


class AdminPersonalizationStatusResponse(BaseModel):
    """Administrative status of personalization subsystems."""

    task_queue_enabled: bool
    recommendations_realtime_refresh_enabled: bool
    recommendations_online_learning_enabled: bool
    active_model_version: Optional[str] = None
    active_model_created_at: Optional[datetime] = None


class EnqueuedJobResponse(BaseModel):
    """Metadata for a newly queued background job."""

    job_id: int
    job_type: str
    status: str


class AdminRetrainRecommendationsRequest(BaseModel):
    """Payload for retraining the recommendations model."""

    top_n: Optional[int] = Field(default=50, ge=1, le=200)
    epochs: Optional[int] = Field(default=None, ge=1, le=50)
    lr: Optional[float] = Field(default=None, gt=0)
    l2: Optional[float] = Field(default=None, ge=0)
    seed: Optional[int] = None
    model_version: Optional[str] = Field(default=None, max_length=100)
    timeout_seconds: Optional[int] = Field(default=None, ge=30, le=60 * 60)


class AdminEvaluateGuardrailsRequest(BaseModel):
    """Payload for evaluating personalization guardrails."""

    days: Optional[int] = Field(default=None, ge=1, le=365)
    min_impressions: Optional[int] = Field(default=None, ge=1, le=1000000)
    ctr_drop_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    conversion_drop_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    click_to_register_window_hours: Optional[int] = Field(
        default=None, ge=1, le=24 * 30
    )


class AdminActivatePersonalizationModelRequest(BaseModel):
    """Payload for activating a trained personalization model."""

    model_version: str = Field(..., min_length=1, max_length=100)
    recompute: bool = True
    top_n: int = Field(default=50, ge=1, le=200)


class AdminActivatePersonalizationModelResponse(BaseModel):
    """Result of activating a personalization model."""

    active_model_version: str
    recompute_job: Optional[EnqueuedJobResponse] = None


class AdminWeeklyDigestRequest(BaseModel):
    """Payload for sending weekly digests."""

    top_n: Optional[int] = Field(default=8, ge=1, le=20)


class AdminFillingFastRequest(BaseModel):
    """Payload for sending filling-fast notifications."""

    threshold_abs: Optional[int] = Field(default=5, ge=1, le=100)
    threshold_ratio: Optional[float] = Field(default=0.2, ge=0, le=1)
    max_per_user: Optional[int] = Field(default=3, ge=1, le=20)


class PasswordResetRequest(BaseModel):
    """Payload for initiating a password reset."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Payload for completing a password reset."""

    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info):
        """Confirm the repeated password matches the new password."""
        pwd = info.data.get("new_password") if hasattr(info, "data") else None
        if pwd and v != pwd:
            raise ValueError("Parolele nu se potrivesc")
        return v


class RefreshRequest(BaseModel):
    """Payload for refreshing an access token."""

    refresh_token: str


class AccountDeleteRequest(BaseModel):
    """Payload for confirming account deletion."""

    password: str = Field(..., min_length=1, max_length=255)


class OrganizerBulkStatusUpdate(BaseModel):
    """Bulk event status update payload for organizers."""

    event_ids: List[int] = Field(..., min_length=1)
    status: Literal["draft", "published"]


class OrganizerBulkTagsUpdate(BaseModel):
    """Bulk tag update payload for organizers."""

    event_ids: List[int] = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)


class OrganizerEmailParticipantsRequest(BaseModel):
    """Payload for emailing participants of an event."""

    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=10000)


class OrganizerEmailParticipantsResponse(BaseModel):
    """Summary of an organizer participant email send."""

    recipients: int


class EventDuplicateCandidate(BaseModel):
    """Potential duplicate event surfaced by suggestion tooling."""

    id: int
    title: str
    start_time: datetime
    city: Optional[str] = None
    similarity: float


class EventSuggestRequest(BaseModel):
    """Payload for event suggestion and duplicate detection."""

    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None


class EventSuggestResponse(BaseModel):
    """Suggested metadata and duplicate candidates for an event."""

    suggested_category: Optional[str] = None
    suggested_city: Optional[str] = None
    suggested_tags: List[str] = []
    duplicates: List[EventDuplicateCandidate] = []
    moderation_score: float = 0.0
    moderation_flags: List[str] = []
    moderation_status: str = "clean"


InteractionType = Literal[
    "impression",
    "click",
    "view",
    "dwell",
    "share",
    "search",
    "filter",
    "favorite",
    "register",
    "unregister",
]


class InteractionEventIn(BaseModel):
    """Single client-side interaction event payload."""

    interaction_type: InteractionType
    event_id: Optional[int] = None
    occurred_at: Optional[datetime] = None
    meta: Optional[dict[str, Any]] = None


class InteractionBatchIn(BaseModel):
    """Batch of client-side interaction events."""

    events: List[InteractionEventIn] = Field(..., min_length=1, max_length=100)
