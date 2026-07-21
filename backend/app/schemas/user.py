from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a new user account."""

    full_name: Annotated[str, Field(min_length=1, max_length=255)]
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserLogin(BaseModel):
    """Schema for authenticating an existing user."""

    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]


class UserResponse(BaseModel):
    """Schema returned for user-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Schema for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
