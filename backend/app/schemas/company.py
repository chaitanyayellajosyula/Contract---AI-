from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    """Schema for creating a new company record."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    website: str | None = None
    industry: str | None = None
    location: str | None = None


class CompanyUpdate(BaseModel):
    """Schema for patching an existing company record."""

    name: str | None = None
    website: str | None = None
    industry: str | None = None
    location: str | None = None


class CompanyResponse(BaseModel):
    """Schema returned for company-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website: str | None = None
    industry: str | None = None
    location: str | None = None
    created_at: datetime
    updated_at: datetime
