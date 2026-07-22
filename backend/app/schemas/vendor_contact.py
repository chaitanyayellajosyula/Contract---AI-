from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class VendorContactCreate(BaseModel):
    """Schema for creating a new vendor contact."""

    vendor_id: int
    full_name: Annotated[str, Field(min_length=1, max_length=255)]
    email: Annotated[str, Field(min_length=1, max_length=255)]
    phone: str | None = None
    linkedin_url: str | None = None
    designation: str | None = None
    is_active: bool = True


class VendorContactUpdate(BaseModel):
    """Schema for patching an existing vendor contact."""

    vendor_id: int | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    designation: str | None = None
    is_active: bool | None = None


class VendorContactResponse(BaseModel):
    """Schema returned for vendor contact-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    full_name: str
    email: str
    phone: str | None = None
    linkedin_url: str | None = None
    designation: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
