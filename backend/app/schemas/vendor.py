from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VendorCreate(BaseModel):
    """Schema for creating a new vendor."""

    name: str
    email: str | None = None
    phone: str | None = None


class VendorUpdate(BaseModel):
    """Schema for patching an existing vendor.
    
    Note: company_id cannot be modified. Vendors are bound to their company.
    """

    name: str | None = None
    email: str | None = None
    phone: str | None = None


class VendorResponse(BaseModel):
    """Schema returned for vendor-related responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    company_id: int | None = None
    created_at: datetime
    updated_at: datetime
