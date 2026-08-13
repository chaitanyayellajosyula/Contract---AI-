from typing import Any

from sqlalchemy.orm import Session

from app.models.vendor import Vendor


class VendorRepository:
    """Repository for vendor persistence and lookup operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        self.db = db

    def create_vendor(self, vendor: Vendor) -> Vendor:
        """Create and persist a new vendor."""
        self.db.add(vendor)
        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def get_vendor(self, vendor_id: int) -> Vendor | None:
        """Return a vendor by identifier, if present."""
        return self.db.get(Vendor, vendor_id)

    def get_vendor_for_company(self, vendor_id: int, company_id: int) -> Vendor | None:
        """Return a vendor only if it belongs to the specified company."""
        return self.db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.company_id == company_id).first()

    def list_vendors(self) -> list[Vendor]:
        """Return all vendors ordered by creation time."""
        return self.db.query(Vendor).order_by(Vendor.created_at.desc()).all()

    def list_vendors_for_company(self, company_id: int) -> list[Vendor]:
        """Return all vendors belonging to the specified company."""
        return self.db.query(Vendor).filter(Vendor.company_id == company_id).order_by(Vendor.created_at.desc()).all()

    def update_vendor(self, vendor_id: int, updates: dict[str, Any]) -> Vendor | None:
        """Apply partial updates to an existing vendor."""
        vendor = self.get_vendor(vendor_id)
        if vendor is None:
            return None

        for field, value in updates.items():
            if hasattr(vendor, field):
                setattr(vendor, field, value)

        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def update_vendor_for_company(self, vendor_id: int, company_id: int, updates: dict[str, Any]) -> Vendor | None:
        """Apply partial updates only to vendors belonging to the specified company."""
        vendor = self.get_vendor_for_company(vendor_id, company_id)
        if vendor is None:
            return None

        for field, value in updates.items():
            if hasattr(vendor, field):
                setattr(vendor, field, value)

        self.db.commit()
        self.db.refresh(vendor)
        return vendor

    def delete_vendor(self, vendor_id: int) -> bool:
        """Delete a vendor by identifier."""
        vendor = self.get_vendor(vendor_id)
        if vendor is None:
            return False

        self.db.delete(vendor)
        self.db.commit()
        return True

    def delete_vendor_for_company(self, vendor_id: int, company_id: int) -> bool:
        """Delete a vendor only if it belongs to the specified company."""
        vendor = self.get_vendor_for_company(vendor_id, company_id)
        if vendor is None:
            return False

        self.db.delete(vendor)
        self.db.commit()
        return True

    def get_by_name(self, name: str) -> Vendor | None:
        """Return a vendor matching the provided name."""
        return self.db.query(Vendor).filter(Vendor.name == name).first()
