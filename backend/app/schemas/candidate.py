from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CandidateCreate(BaseModel):
    """Schema for creating a new candidate record."""

    owner_user_id: int
    company_id: int
    first_name: Annotated[str, Field(min_length=1, max_length=255)]
    last_name: Annotated[str, Field(min_length=1, max_length=255)]
    email: Annotated[str, Field(min_length=1, max_length=255)]
    phone: str | None = None
    linkedin_url: str | None = None
    current_location: str | None = None
    preferred_location: str | None = None
    visa_status: str | None = None
    total_experience: str | None = None
    us_experience: str | None = None
    current_rate: str | None = None
    expected_rate: str | None = None
    availability_status: str | None = None
    resume_filename: str | None = None


class CandidateUpdate(BaseModel):
    """Schema for patching an existing candidate record."""

    owner_user_id: int | None = None
    company_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    current_location: str | None = None
    preferred_location: str | None = None
    visa_status: str | None = None
    total_experience: str | None = None
    us_experience: str | None = None
    current_rate: str | None = None
    expected_rate: str | None = None
    availability_status: str | None = None
    resume_filename: str | None = None


class CandidateResponse(BaseModel):
    """Schema returned for candidate-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    company_id: int
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    current_location: str | None = None
    preferred_location: str | None = None
    visa_status: str | None = None
    total_experience: str | None = None
    us_experience: str | None = None
    current_rate: str | None = None
    expected_rate: str | None = None
    availability_status: str | None = None
    resume_filename: str | None = None
    created_at: datetime
    updated_at: datetime
