from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User
from app.models.vendor_contact import VendorContact
from app.schemas.vendor_contact import VendorContactCreate, VendorContactResponse, VendorContactUpdate
from app.services.vendor_contact_service import VendorContactService

router = APIRouter(prefix="/vendor-contacts", tags=["vendor-contacts"])


@router.post("/{vendor_id}", response_model=VendorContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    vendor_id: int,
    payload: VendorContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorContact:
    """Create a vendor contact for the specified vendor (must belong to user's company)."""
    service = VendorContactService(db)
    try:
        return service.create_contact(vendor_id, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[VendorContactResponse])
def list_contacts(
    vendor_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VendorContact]:
    """List vendor contacts in the authenticated user's company.
    
    Optionally filter by vendor_id (vendor must belong to user's company).
    """
    service = VendorContactService(db)
    return service.list_contacts(current_user, vendor_id=vendor_id)


@router.get("/{contact_id}", response_model=VendorContactResponse)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorContact:
    """Get a vendor contact with company authorization."""
    service = VendorContactService(db)
    contact = service.get_contact(contact_id, current_user)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return contact


@router.patch("/{contact_id}", response_model=VendorContactResponse)
def update_contact(
    contact_id: int,
    payload: VendorContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VendorContact:
    """Update a vendor contact with company authorization."""
    service = VendorContactService(db)
    try:
        contact = service.update_contact(contact_id, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a vendor contact with company authorization."""
    service = VendorContactService(db)
    deleted = service.delete_contact(contact_id, current_user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
