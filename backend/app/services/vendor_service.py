from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.repositories.vendor_repository import VendorRepository
from app.schemas.vendor import VendorCreate, VendorUpdate


class VendorService:
    """Service layer containing business logic for vendor persistence and authorization."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = VendorRepository(db)

    def create_vendor(self, current_user: User, payload: VendorCreate) -> Vendor:
        """Create a new vendor.
        
        Security:
        - vendor.company_id is set to current_user.company_id
        - Client cannot override company_id
        """
        if current_user.company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be assigned to a company to create vendors"
            )

        vendor = Vendor(
            **payload.model_dump(),
            company_id=current_user.company_id
        )
        return self.repository.create_vendor(vendor)

    def get_vendor(self, vendor_id: int, current_user: User) -> Vendor | None:
        """Get a vendor with company authorization."""
        vendor = self.repository.get_vendor(vendor_id)
        if vendor is None or vendor.company_id != current_user.company_id:
            return None

        return vendor

    def list_vendors(self, current_user: User) -> list[Vendor]:
        """List vendors for the authenticated user's company."""
        if current_user.company_id is None:
            return []

        return self.repository.list_vendors_for_company(current_user.company_id)

    def update_vendor(self, vendor_id: int, current_user: User, payload: VendorUpdate) -> Vendor | None:
        """Update a vendor with company authorization.
        
        Security:
        - company_id cannot be modified (automatically stripped)
        """
        vendor = self.repository.get_vendor(vendor_id)
        if vendor is None or vendor.company_id != current_user.company_id:
            return None

        # Remove company_id from updates (protected field)
        updates = payload.model_dump(exclude_unset=True, exclude={"company_id"})
        return self.repository.update_vendor(vendor_id, updates)

    def delete_vendor(self, vendor_id: int, current_user: User) -> bool:
        """Delete a vendor with company authorization."""
        vendor = self.repository.get_vendor(vendor_id)
        if vendor is None or vendor.company_id != current_user.company_id:
            return False

        return self.repository.delete_vendor(vendor_id)
