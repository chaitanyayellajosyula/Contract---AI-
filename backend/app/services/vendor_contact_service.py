from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.repositories.vendor_contact_repository import VendorContactRepository
from app.schemas.vendor_contact import VendorContactCreate, VendorContactUpdate


class VendorContactService:
    """Service layer containing business logic for vendor contact persistence and authorization."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = VendorContactRepository(db)

    def create_contact(self, vendor_id: int, current_user: User, payload: VendorContactCreate) -> VendorContact:
        """Create a new vendor contact.
        
        Security:
        - Vendor must belong to authenticated user's company
        - Returns 404 if vendor doesn't exist or belongs to different company
        """
        # Verify vendor exists and belongs to user's company
        vendor = self.db.get(Vendor, vendor_id)
        if vendor is None or vendor.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )

        # Check for duplicate email
        if self.repository.get_by_email(payload.email) is not None:
            raise ValueError("Vendor contact with this email already exists")

        contact = VendorContact(vendor_id=vendor_id, **payload.model_dump())
        return self.repository.create_contact(contact)

    def get_contact(self, contact_id: int, current_user: User) -> VendorContact | None:
        """Get a vendor contact with company authorization."""
        contact = self.repository.get_contact(contact_id)
        if contact is None:
            return None

        # Check if contact's vendor belongs to user's company
        if contact.vendor.company_id != current_user.company_id:
            return None

        return contact

    def list_contacts(self, current_user: User, vendor_id: int | None = None) -> list[VendorContact]:
        """List vendor contacts for the authenticated user's company."""
        query = self.db.query(VendorContact).join(Vendor).filter(Vendor.company_id == current_user.company_id)

        if vendor_id is not None:
            # Verify vendor belongs to user's company
            vendor = self.db.get(Vendor, vendor_id)
            if vendor is None or vendor.company_id != current_user.company_id:
                return []
            query = query.filter(VendorContact.vendor_id == vendor_id)

        return query.order_by(VendorContact.created_at.desc()).all()

    def update_contact(self, contact_id: int, current_user: User, payload: VendorContactUpdate) -> VendorContact | None:
        """Update a vendor contact with company authorization.
        
        Security:
        - vendor_id cannot be modified (automatically stripped)
        """
        contact = self.repository.get_contact(contact_id)
        if contact is None or contact.vendor.company_id != current_user.company_id:
            return None

        if payload.email is not None:
            existing = self.repository.get_by_email(payload.email)
            if existing is not None and existing.id != contact_id:
                raise ValueError("Vendor contact with this email already exists")

        # Remove vendor_id from updates (protected field)
        updates = payload.model_dump(exclude_unset=True, exclude={"vendor_id"})
        return self.repository.update_contact(contact_id, updates)

    def delete_contact(self, contact_id: int, current_user: User) -> bool:
        """Delete a vendor contact with company authorization."""
        contact = self.repository.get_contact(contact_id)
        if contact is None or contact.vendor.company_id != current_user.company_id:
            return False

        return self.repository.delete_contact(contact_id)
