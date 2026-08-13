from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.candidate import Candidate
from app.models.user import User
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Create a candidate and assign ownership to the authenticated recruiter."""
    service = CandidateService(db)
    return service.create_candidate(current_user.id, payload)


@router.get("", response_model=list[CandidateResponse])
def list_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Candidate]:
    """List only the authenticated recruiter's own candidates."""
    service = CandidateService(db)
    return service.list_candidates_for_owner(current_user.id)


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Candidate:
    """Return a candidate only when it belongs to the authenticated recruiter."""
    service = CandidateService(db)
    candidate = service.get_candidate_for_owner(candidate_id, current_user.id)
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
    """Update a candidate only when it belongs to the authenticated recruiter."""
    service = CandidateService(db)
    candidate = service.update_candidate_for_owner(candidate_id, current_user.id, payload)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a candidate only when it belongs to the authenticated recruiter."""
    service = CandidateService(db)
    deleted = service.delete_candidate_for_owner(candidate_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
