from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.candidate import Candidate
from app.models.user import User
from app.schemas.candidate import CandidateCreate, CandidateHotlistItem, CandidateHotlistPage, CandidateResponse, CandidateUpdate
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Create a candidate and assign ownership/company based on authenticated user.
    
    Security:
    - Ownership is set to current user (cannot be overridden)
    - Company is set to current user's company (cannot be overridden)
    - Returns 400 if user is not assigned to a company
    """
    service = CandidateService(db)
    return service.create_candidate(current_user, payload)


@router.get("", response_model=list[CandidateResponse])
def list_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Candidate]:
    """List candidates with role-based access control.
    
    RECRUITER: sees only their own candidates
    COMPANY_ADMIN: sees all candidates in their company
    """
    service = CandidateService(db)
    return service.list_candidates_for_user(current_user)


@router.get("/hotlist", response_model=CandidateHotlistPage)
def search_candidate_hotlist(
    q: str | None = None,
    location: str | None = None,
    experience: str | None = None,
    visa_status: str | None = None,
    availability_status: str | None = None,
    rate: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CandidateHotlistPage:
    candidates, total = CandidateService(db).search_candidates_for_user(
        current_user,
        query=q,
        location=location,
        experience=experience,
        visa_status=visa_status,
        availability_status=availability_status,
        rate=rate,
        page=page,
        page_size=page_size,
    )
    supported_fields = (
        "current_location",
        "preferred_location",
        "visa_status",
        "total_experience",
        "us_experience",
        "current_rate",
        "expected_rate",
        "availability_status",
        "resume_filename",
    )
    items = [
        CandidateHotlistItem(
            candidate=candidate,
            data_availability={
                **{
                    field: "stored" if getattr(candidate, field) else "not_recorded"
                    for field in supported_fields
                },
                "skills": "unavailable",
                "title": "unavailable",
                "education": "unavailable",
                "certifications": "unavailable",
                "resume_content": "unavailable",
            },
        )
        for candidate in candidates
    ]
    return CandidateHotlistPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Get a specific candidate with role-based access control.
    
    Returns 404 if:
    - Candidate does not exist
    - User lacks permission (recruiter: not owner, company admin: different company)
    
    Note: 404 is used instead of 403 to avoid revealing candidate existence
    across company boundaries.
    """
    service = CandidateService(db)
    candidate = service.get_candidate_for_user(candidate_id, current_user)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Update a candidate with role-based access control.
    
    Security:
    - owner_user_id and company_id cannot be modified (automatically stripped)
    - RECRUITER: can only update own candidates
    - COMPANY_ADMIN: can update any candidate in their company
    - Returns 404 if candidate doesn't exist or user lacks permission
    """
    service = CandidateService(db)
    candidate = service.update_candidate_for_user(candidate_id, current_user, payload)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a candidate with role-based access control.
    
    RECRUITER: can only delete own candidates
    COMPANY_ADMIN: can delete any candidate in their company
    Returns 404 if candidate doesn't exist or user lacks permission
    """
    service = CandidateService(db)
    deleted = service.delete_candidate_for_user(candidate_id, current_user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
