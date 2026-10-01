from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorResponse, VendorUpdate
from app.schemas.vendor_intelligence import (
    IntelligenceContact,
    IntelligenceJobPage,
    VendorIntelligenceProfile,
    VendorSearchPage,
)
from app.services.vendor_service import VendorService
from app.services.vendor_intelligence_service import VendorIntelligenceService

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Vendor:
    """Create a vendor belonging to the authenticated user's company."""
    service = VendorService(db)
    return service.create_vendor(current_user, payload)


@router.get("", response_model=list[VendorResponse])
def list_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Vendor]:
    """List vendors in the authenticated user's company."""
    service = VendorService(db)
    return service.list_vendors(current_user)


@router.get("/intelligence", response_model=VendorSearchPage)
def search_vendor_intelligence(
    q: str | None = None,
    company: str | None = None,
    website: str | None = None,
    location: str | None = None,
    engagement_type: str | None = None,
    source: str | None = None,
    has_jobs: bool | None = None,
    active_within_days: int | None = Query(default=None, ge=1, le=365),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorSearchPage:
    return VendorIntelligenceService(db).search_vendors(
        current_user,
        q,
        page,
        page_size,
        company=company,
        website=website,
        location=location,
        engagement_type=engagement_type,
        source=source,
        has_jobs=has_jobs,
        active_within_days=active_within_days,
    )


@router.get("/{vendor_id}/intelligence", response_model=VendorIntelligenceProfile)
def get_vendor_intelligence(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorIntelligenceProfile:
    profile = VendorIntelligenceService(db).vendor_profile(current_user, vendor_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return profile


@router.get("/{vendor_id}/jobs", response_model=IntelligenceJobPage)
def get_vendor_jobs(
    vendor_id: int,
    source: str | None = None,
    engagement_type: str | None = None,
    location: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IntelligenceJobPage:
    jobs = VendorIntelligenceService(db).vendor_jobs(
        current_user,
        vendor_id,
        page,
        page_size,
        source=source,
        engagement_type=engagement_type,
        location=location,
    )
    if jobs is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return jobs


@router.get("/{vendor_id}/contacts", response_model=list[IntelligenceContact])
def get_vendor_intelligence_contacts(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IntelligenceContact]:
    contacts = VendorIntelligenceService(db).vendor_contacts(current_user, vendor_id)
    if contacts is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return contacts


@router.get("/{vendor_id}", response_model=VendorResponse)
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Vendor:
    """Get a specific vendor with company authorization."""
    service = VendorService(db)
    vendor = service.get_vendor(vendor_id, current_user)
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return vendor


@router.patch("/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: int,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Vendor:
    """Update a vendor with company authorization."""
    service = VendorService(db)
    vendor = service.update_vendor(vendor_id, current_user, payload)
    if vendor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a vendor with company authorization."""
    service = VendorService(db)
    deleted = service.delete_vendor(vendor_id, current_user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
