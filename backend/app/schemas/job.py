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
    source_url: str | None = None
    apply_url: str | None = None
    source_company: str | None = None
    source_updated_at: datetime | None = None
    source_metadata: dict | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool = False
    bookmarked: bool = False
    company_id: int | None = None
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
    source_url: str | None = None
    apply_url: str | None = None
    source_company: str | None = None
    source_updated_at: datetime | None = None
    source_metadata: dict | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool | None = None
    bookmarked: bool | None = None
    company_id: int | None = None
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
    source_url: str | None = None
    apply_url: str | None = None
    source_company: str | None = None
    source_updated_at: datetime | None = None
    source_metadata: dict | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    viewed: bool
    bookmarked: bool
    saved: bool = False
    hidden: bool = False
    company_id: int | None = None
    company: str | None = None
    created_at: datetime
    updated_at: datetime
    recruiter_id: int | None = None


class JobIngestionSummary(BaseModel):
    """Response contract for single-source job ingestion."""

    source: str
    source_identifier: str
    run_id: int
    started_at: datetime
    completed_at: datetime
    status: str
    fetched: int
    created: int
    updated: int
    skipped_duplicates: int
    rejected: int
    message: str | None = None


class JobUserStatusUpdate(BaseModel):
    """User-owned workflow state for one job."""

    viewed: bool | None = None
    saved: bool | None = None
    hidden: bool | None = None
