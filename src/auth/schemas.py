from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    display_name: str = Field(..., min_length=2, max_length=100, description="Display name")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")
    language_preference: str = Field(default="en", description="Preferred language: en or ja")
    timezone: str = Field(default="Asia/Kolkata", description="IANA timezone")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    display_name: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    user_presence: str
    last_seen: Optional[datetime]
    status: str
    registration_date: Optional[str]
    timezone: str
    language_preference: str
    avatar_url: Optional[str]


class TokenData(BaseModel):
    user_id: str
    email: str
