from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.vendor_contact import VendorContact
from app.schemas.vendor_contact import VendorContactCreate, VendorContactResponse, VendorContactUpdate
from app.services.vendor_contact_service import VendorContactService

router = APIRouter(prefix="/vendor-contacts", tags=["vendor-contacts"])


@router.post("", response_model=VendorContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(payload: VendorContactCreate, db: Session = Depends(get_db)) -> VendorContact:
    """Create a new vendor contact."""
    service = VendorContactService(db)
    try:
        return service.create_contact(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[VendorContactResponse])
def list_contacts(
    vendor_id: int | None = None,
    full_name: str | None = None,
    email: str | None = None,
    designation: str | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
) -> list[VendorContact]:
    """List vendor contacts with optional filters."""
    service = VendorContactService(db)
    return service.list_contacts(
        vendor_id=vendor_id,
        full_name=full_name,
        email=email,
        designation=designation,
        is_active=is_active,
    )


@router.get("/{contact_id}", response_model=VendorContactResponse)
def get_contact(contact_id: int, db: Session = Depends(get_db)) -> VendorContact:
    """Return a single vendor contact by identifier."""
    service = VendorContactService(db)
    contact = service.get_contact(contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return contact


@router.patch("/{contact_id}", response_model=VendorContactResponse)
def update_contact(contact_id: int, payload: VendorContactUpdate, db: Session = Depends(get_db)) -> VendorContact:
    """Apply a partial update to an existing vendor contact."""
    service = VendorContactService(db)
    try:
        contact = service.update_contact(contact_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete an existing vendor contact."""
    service = VendorContactService(db)
    deleted = service.delete_contact(contact_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor contact not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
