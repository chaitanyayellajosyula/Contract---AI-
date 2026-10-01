from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User
from app.schemas.matching import MatchResponse
from app.services.matching_service import MatchingService

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post("/candidates/{candidate_id}/jobs/{job_id}", response_model=MatchResponse)
def match_candidate_to_job(
    candidate_id: int,
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchResponse:
    return MatchingService(db).match_for_user(candidate_id, job_id, current_user)