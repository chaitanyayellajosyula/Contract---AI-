from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


PositiveId = Annotated[int, Field(gt=0)]
OutreachStatusValue = Literal["DRAFT", "READY", "SENT", "CANCELLED"]
OutreachTemplateType = Literal["candidate_submission", "vendor_relationship", "follow_up"]


class OutreachEntities(BaseModel):
    candidate_id: PositiveId | None = None
    job_id: PositiveId | None = None
    vendor_id: PositiveId | None = None
    contact_id: PositiveId | None = None


class OutreachDraftPreviewRequest(OutreachEntities):
    template_type: OutreachTemplateType


class OutreachDraftPreview(BaseModel):
    template_type: OutreachTemplateType
    subject: str
    body: str
    recipient_email: str | None
    evidence: list[str]


class OutreachDraftCreate(OutreachEntities):
    subject: Annotated[str, Field(min_length=1, max_length=500)]
    body: Annotated[str, Field(min_length=1)]
    notes: str | None = None


class OutreachUpdate(BaseModel):
    subject: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    body: Annotated[str, Field(min_length=1)] | None = None
    notes: str | None = None
    status: Literal["DRAFT", "READY"] | None = None


class OutreachResponse(BaseModel):
    id: int
    candidate_id: int | None
    candidate_name: str | None
    job_id: int | None
    job_title: str | None
    vendor_id: int | None
    vendor_name: str | None
    contact_id: int | None
    contact_name: str | None
    recipient_email: str | None
    subject: str
    body: str
    status: OutreachStatusValue
    notes: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None


class OutreachPage(BaseModel):
    items: list[OutreachResponse]
    total: int
    page: int
    page_size: int