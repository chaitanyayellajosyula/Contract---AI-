from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.repositories.vendor_contact_repository import VendorContactRepository
from app.repositories.vendor_repository import VendorRepository
from app.schemas.vendor_contact import VendorContactCreate, VendorContactUpdate


class VendorContactService:
    """Service layer containing business logic for vendor contact persistence and authorization."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = VendorContactRepository(db)
        self.vendor_repository = VendorRepository(db)

    def _has_company_scope_access(self, current_user: User) -> bool:
        """Allow only recruiter and company admin roles to manage company-scoped contacts."""
        return (
            current_user.company_id is not None
            and current_user.role in {UserRole.RECRUITER.value, UserRole.COMPANY_ADMIN.value}
        )

    def create_contact(self, vendor_id: int, current_user: User, payload: VendorContactCreate) -> VendorContact:
        """Create a new vendor contact.
        
        Security:
        - Vendor must belong to authenticated user's company
        - Returns 404 if vendor doesn't exist or belongs to different company
        """
        if not self._has_company_scope_access(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage vendor contacts"
            )

        vendor = self.vendor_repository.get_vendor_for_company(vendor_id, current_user.company_id)
        if vendor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vendor not found"
            )

        if self.repository.get_by_email(payload.email) is not None:
            raise ValueError("Vendor contact with this email already exists")

        contact = VendorContact(vendor_id=vendor_id, **payload.model_dump())
        return self.repository.create_contact(contact)

    def get_contact(self, contact_id: int, current_user: User) -> VendorContact | None:
        """Get a vendor contact with company authorization."""
        if not self._has_company_scope_access(current_user):
            return None

        return self.repository.get_contact_for_company(contact_id, current_user.company_id)

    def list_contacts(self, current_user: User, vendor_id: int | None = None) -> list[VendorContact]:
        """List vendor contacts for the authenticated user's company."""
        if not self._has_company_scope_access(current_user):
            return []

        if vendor_id is not None:
            vendor = self.vendor_repository.get_vendor_for_company(vendor_id, current_user.company_id)
            if vendor is None:
                return []
            return (
                self.db.query(VendorContact)
                .join(Vendor)
                .filter(Vendor.company_id == current_user.company_id, VendorContact.vendor_id == vendor_id)
                .order_by(VendorContact.created_at.desc())
                .all()
            )

        return self.repository.list_contacts_for_company(current_user.company_id)

    def update_contact(self, contact_id: int, current_user: User, payload: VendorContactUpdate) -> VendorContact | None:
        """Update a vendor contact with company authorization.
        
        Security:
        - vendor_id cannot be modified (automatically stripped)
        """
        if not self._has_company_scope_access(current_user):
            return None

        contact = self.repository.get_contact_for_company(contact_id, current_user.company_id)
        if contact is None:
            return None

        if payload.email is not None:
            existing = self.repository.get_by_email(payload.email)
            if existing is not None and existing.id != contact_id:
                raise ValueError("Vendor contact with this email already exists")

        updates = payload.model_dump(exclude_unset=True, exclude={"vendor_id"})
        return self.repository.update_contact_for_company(contact_id, current_user.company_id, updates)

    def delete_contact(self, contact_id: int, current_user: User) -> bool:
        """Delete a vendor contact with company authorization."""
        if not self._has_company_scope_access(current_user):
            return False

        return self.repository.delete_contact_for_company(contact_id, current_user.company_id)

