from datetime import datetime
from typing import Annotated

from email_validator import validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    """Schema for creating a new user account."""

    full_name: Annotated[str, Field(min_length=1, max_length=255)]
    email: str
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value: str) -> str:
        """Accept standard emails and the development bootstrap local-domain address."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Email is required")
        if "@" not in normalized or normalized.count("@") != 1:
            raise ValueError("Email must contain a single @")

        local_part, domain = normalized.split("@", 1)
        if not local_part or not domain:
            raise ValueError("Email must contain local and domain parts")

        if domain.lower().endswith(".local"):
            return normalized

        try:
            result = validate_email(normalized, check_deliverability=False)
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ValueError("Invalid email address") from exc

        return result.normalized


class UserLogin(BaseModel):
    """Schema for authenticating an existing user."""

    email: str
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def validate_email_field(cls, value: str) -> str:
        """Accept standard emails and the development bootstrap local-domain address."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Email is required")
        if "@" not in normalized or normalized.count("@") != 1:
            raise ValueError("Email must contain a single @")

        local_part, domain = normalized.split("@", 1)
        if not local_part or not domain:
            raise ValueError("Email must contain local and domain parts")

        if domain.lower().endswith(".local"):
            return normalized

        try:
            result = validate_email(normalized, check_deliverability=False)
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ValueError("Invalid email address") from exc

        return result.normalized


class UserResponse(BaseModel):
    """Schema returned for user-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None
    email: str
    company_id: int | None = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Schema for authentication tokens."""

    access_token: str
    token_type: str = "bearer"
