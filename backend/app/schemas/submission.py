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
    status: SubmissionStatusValue
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