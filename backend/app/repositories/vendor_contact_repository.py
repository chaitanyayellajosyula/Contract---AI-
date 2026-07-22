from typing import Any

from sqlalchemy.orm import Session

from app.models.vendor_contact import VendorContact


class VendorContactRepository:
    """Repository for vendor contact persistence and lookup operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        self.db = db

    def create_contact(self, contact: VendorContact) -> VendorContact:
        """Create and persist a new vendor contact."""
        self.db.add(contact)
        self.db.commit()
        self.db.refresh(contact)
        return contact

    def get_contact(self, contact_id: int) -> VendorContact | None:
        """Return a vendor contact by identifier, if present."""
        return self.db.get(VendorContact, contact_id)

    def list_contacts(self) -> list[VendorContact]:
        """Return all vendor contacts ordered by creation time."""
        return self.db.query(VendorContact).order_by(VendorContact.created_at.desc()).all()

    def update_contact(self, contact_id: int, updates: dict[str, Any]) -> VendorContact | None:
        """Apply partial updates to an existing vendor contact."""
        contact = self.get_contact(contact_id)
        if contact is None:
            return None

        for field, value in updates.items():
            if hasattr(contact, field):
                setattr(contact, field, value)

        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete_contact(self, contact_id: int) -> bool:
        """Delete a vendor contact by identifier."""
        contact = self.get_contact(contact_id)
        if contact is None:
            return False

        self.db.delete(contact)
        self.db.commit()
        return True

    def get_by_email(self, email: str) -> VendorContact | None:
        """Return a vendor contact matching the provided email address."""
        return self.db.query(VendorContact).filter(VendorContact.email == email).first()
