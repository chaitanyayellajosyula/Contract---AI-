from sqlalchemy.orm import Session

from app.models.vendor_contact import VendorContact
from app.repositories.vendor_contact_repository import VendorContactRepository
from app.schemas.vendor_contact import VendorContactCreate, VendorContactUpdate


class VendorContactService:
    """Service layer containing business logic for vendor contact persistence."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = VendorContactRepository(db)

    def create_contact(self, payload: VendorContactCreate) -> VendorContact:
        """Create a new vendor contact from validated input."""
        if self.repository.get_by_email(payload.email) is not None:
            raise ValueError("Vendor contact with this email already exists")

        contact = VendorContact(**payload.model_dump())
        return self.repository.create_contact(contact)

    def get_contact(self, contact_id: int) -> VendorContact | None:
        """Return a single vendor contact by identifier, if present."""
        return self.repository.get_contact(contact_id)

    def list_contacts(self, vendor_id: int | None = None, full_name: str | None = None, email: str | None = None, designation: str | None = None, is_active: bool | None = None) -> list[VendorContact]:
        """Return vendor contacts matching the optional filters."""
        query = self.repository.db.query(VendorContact)

        if vendor_id is not None:
            query = query.filter(VendorContact.vendor_id == vendor_id)
        if full_name is not None:
            query = query.filter(VendorContact.full_name.ilike(f"%{full_name}%"))
        if email is not None:
            query = query.filter(VendorContact.email.ilike(f"%{email}%"))
        if designation is not None:
            query = query.filter(VendorContact.designation.ilike(f"%{designation}%"))
        if is_active is not None:
            query = query.filter(VendorContact.is_active == is_active)

        return query.order_by(VendorContact.created_at.desc()).all()

    def update_contact(self, contact_id: int, payload: VendorContactUpdate) -> VendorContact | None:
        """Apply a partial update to an existing vendor contact."""
        if payload.email is not None:
            existing = self.repository.get_by_email(payload.email)
            if existing is not None and existing.id != contact_id:
                raise ValueError("Vendor contact with this email already exists")

        return self.repository.update_contact(contact_id, payload.model_dump(exclude_unset=True))

    def delete_contact(self, contact_id: int) -> bool:
        """Delete a vendor contact by identifier."""
        return self.repository.delete_contact(contact_id)
