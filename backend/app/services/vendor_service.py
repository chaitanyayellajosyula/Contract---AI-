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

    def _has_company_scope_access(self, current_user: User) -> bool:
        """Allow only recruiter and company admin roles to manage company-scoped vendors."""
        return (
            current_user.company_id is not None
            and current_user.role in {UserRole.RECRUITER.value, UserRole.COMPANY_ADMIN.value}
        )

    def create_vendor(self, current_user: User, payload: VendorCreate) -> Vendor:
        """Create a new vendor.
        
        Security:
        - vendor.company_id is set to current_user.company_id
        - Client cannot override company_id
        - Only recruiter/company admin can create within a company scope
        """
        if not self._has_company_scope_access(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage vendors"
            )

        vendor = Vendor(
            **payload.model_dump(),
            company_id=current_user.company_id
        )
        return self.repository.create_vendor(vendor)

    def get_vendor(self, vendor_id: int, current_user: User) -> Vendor | None:
        """Get a vendor with company authorization."""
        if not self._has_company_scope_access(current_user):
            return None

        return self.repository.get_vendor_for_company(vendor_id, current_user.company_id)

    def list_vendors(self, current_user: User) -> list[Vendor]:
        """List vendors for the authenticated user's company."""
        if not self._has_company_scope_access(current_user):
            return []

        return self.repository.list_vendors_for_company(current_user.company_id)

    def update_vendor(self, vendor_id: int, current_user: User, payload: VendorUpdate) -> Vendor | None:
        """Update a vendor with company authorization.
        
        Security:
        - company_id cannot be modified (automatically stripped)
        """
        if not self._has_company_scope_access(current_user):
            return None

        updates = payload.model_dump(exclude_unset=True, exclude={"company_id"})
        return self.repository.update_vendor_for_company(vendor_id, current_user.company_id, updates)

    def delete_vendor(self, vendor_id: int, current_user: User) -> bool:
        """Delete a vendor with company authorization."""
        if not self._has_company_scope_access(current_user):
            return False

        return self.repository.delete_vendor_for_company(vendor_id, current_user.company_id)
