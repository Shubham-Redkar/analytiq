"""AnalytIQ Schemas - Authentication and user response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request contract."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(description="User's unique email address.")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password (minimum 8 characters).",
    )
    display_name: str = Field(
        min_length=1,
        max_length=100,
        description="Display name for the user profile.",
    )


class LoginRequest(BaseModel):
    """User login request contract."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(description="User email address.")
    password: str = Field(min_length=1, description="Account password.")


class UserResponse(BaseModel):
    """Sanitized user response representation (never exposes password hashes)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime


class MessageResponse(BaseModel):
    """Generic status/message response contract."""

    message: str
    status: str = "ok"
