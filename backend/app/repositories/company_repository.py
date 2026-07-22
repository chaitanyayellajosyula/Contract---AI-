from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company


class CompanyRepository:
    """Repository for company persistence and lookup operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        self.db = db

    def create_company(self, company: Company) -> Company:
        """Create and persist a new company record."""
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def get_company(self, company_id: int) -> Company | None:
        """Return a company by identifier, if present."""
        return self.db.get(Company, company_id)

    def list_companies(self) -> list[Company]:
        """Return all companies ordered by creation time."""
        return self.db.query(Company).order_by(Company.created_at.desc()).all()

    def update_company(self, company_id: int, updates: dict[str, Any]) -> Company | None:
        """Apply partial updates to an existing company record."""
        company = self.get_company(company_id)
        if company is None:
            return None

        for field, value in updates.items():
            if hasattr(company, field):
                setattr(company, field, value)

        self.db.commit()
        self.db.refresh(company)
        return company

    def delete_company(self, company_id: int) -> bool:
        """Delete a company record by identifier."""
        company = self.get_company(company_id)
        if company is None:
            return False

        self.db.delete(company)
        self.db.commit()
        return True

    def get_by_name(self, name: str) -> Company | None:
        """Return a company matching the provided name."""
        return self.db.query(Company).filter(Company.name == name).first()
