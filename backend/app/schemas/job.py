from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    """Schema for creating a new job record."""

    title: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience: str | None = None
    salary: str | None = None
    remote_type: str | None = None
    status: str | None = None
    source: str | None = None
    source_job_id: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool = False
    bookmarked: bool = False
    recruiter_id: int | None = None


class JobUpdate(BaseModel):
    """Schema for patching an existing job record."""

    title: str | None = None
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience: str | None = None
    salary: str | None = None
    remote_type: str | None = None
    status: str | None = None
    source: str | None = None
    source_job_id: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool | None = None
    bookmarked: bool | None = None
    recruiter_id: int | None = None


class JobResponse(BaseModel):
    """Schema returned for job-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience: str | None = None
    salary: str | None = None
    remote_type: str | None = None
    status: str | None = None
    source: str | None = None
    source_job_id: str | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool
    bookmarked: bool
    created_at: datetime
    updated_at: datetime
    recruiter_id: int | None = None
