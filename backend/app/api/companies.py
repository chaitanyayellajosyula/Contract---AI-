from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)) -> Company:
    """Create a new company record."""
    service = CompanyService(db)
    return service.create_company(payload)


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    name: str | None = None,
    industry: str | None = None,
    location: str | None = None,
    db: Session = Depends(get_db),
) -> list[Company]:
    """List companies with optional filters."""
    service = CompanyService(db)
    return service.list_companies(name=name, industry=industry, location=location)


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)) -> Company:
    """Return a single company by identifier."""
    service = CompanyService(db)
    company = service.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)) -> Company:
    """Apply a partial update to an existing company."""
    service = CompanyService(db)
    company = service.update_company(company_id, payload)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete an existing company."""
    service = CompanyService(db)
    deleted = service.delete_company(company_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
