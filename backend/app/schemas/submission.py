from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.submission import SubmissionStatus


SubmissionStatusValue = Literal[tuple(status.value for status in SubmissionStatus)]


class SubmissionCreate(BaseModel):
    candidate_id: Annotated[int, Field(gt=0)]
    job_id: Annotated[int, Field(gt=0)]
    notes: str | None = None


class SubmissionStatusUpdate(BaseModel):
    status: SubmissionStatusValue | None = None
    notes: str | None = None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    job_id: int
    company_id: int
    submitted_by_user_id: int
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    candidate: "CandidateSummary"
    job: "JobSummary"
    company: "CompanySummary"


class CandidateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    location: str | None = None


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class SubmissionHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    from_status: str | None = None
    to_status: str
    changed_by_user_id: int
    notes: str | None = None
    created_at: datetime