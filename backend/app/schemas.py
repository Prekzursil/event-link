from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from .models import UserRole

class UserBase(BaseModel):
    email: EmailStr
    role: UserRole

class UserCreate(UserBase):
    password: str
    confirm_password: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[UserRole] = None


class TagBase(BaseModel):
    name: str


class Tag(TagBase):
    id: int

    class Config:
        from_attributes = True


class EventBase(BaseModel):
    title: str
    description: str
    category: str
    event_date: datetime
    start_time: datetime
    end_time: Optional[datetime]
    location: str
    max_seats: int = Field(gt=0)
    tags: List[str] = []


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    category: Optional[str]
    event_date: Optional[datetime]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    location: Optional[str]
    max_seats: Optional[int] = Field(default=None, gt=0)
    tags: Optional[List[str]]


class EventSummary(BaseModel):
    id: int
    title: str
    category: Optional[str]
    event_date: datetime
    start_time: datetime
    end_time: Optional[datetime]
    location: Optional[str]
    max_seats: Optional[int]
    registrations_count: int

    class Config:
        from_attributes = True


class EventDetail(EventSummary):
    description: Optional[str]
    owner_id: int
    tags: List[Tag] = []


class Registration(BaseModel):
    id: int
    event_id: int
    user_id: int
    registration_time: datetime

    class Config:
        from_attributes = True
