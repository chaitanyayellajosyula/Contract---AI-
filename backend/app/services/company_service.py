from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyCreate, CompanyUpdate


class CompanyService:
    """Service layer containing business logic for company persistence."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = CompanyRepository(db)

    def create_company(self, payload: CompanyCreate) -> Company:
        """Create a new company record from validated input."""
        company = Company(**payload.model_dump())
        return self.repository.create_company(company)

    def get_company(self, company_id: int) -> Company | None:
        """Return a single company by identifier, if present."""
        return self.repository.get_company(company_id)

    def list_companies(self, name: str | None = None, industry: str | None = None, location: str | None = None) -> list[Company]:
        """Return companies matching the optional filters."""
        query = self.repository.db.query(Company)

        if name is not None:
            query = query.filter(Company.name.ilike(f"%{name}%"))
        if industry is not None:
            query = query.filter(Company.industry.ilike(f"%{industry}%"))
        if location is not None:
            query = query.filter(Company.location.ilike(f"%{location}%"))

        return query.order_by(Company.created_at.desc()).all()

    def update_company(self, company_id: int, payload: CompanyUpdate) -> Company | None:
        """Apply a partial update to an existing company record."""
        return self.repository.update_company(company_id, payload.model_dump(exclude_unset=True))

    def delete_company(self, company_id: int) -> bool:
        """Delete a company record by identifier."""
        return self.repository.delete_company(company_id)
