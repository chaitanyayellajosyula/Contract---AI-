from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.repositories.candidate_repository import CandidateRepository
from app.schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateService:
    """Service layer for candidate persistence and ownership enforcement."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = CandidateRepository(db)

    def create_candidate(self, owner_user_id: int, payload: CandidateCreate) -> Candidate:
        """Create a new candidate record owned by the authenticated recruiter."""
        candidate = Candidate(owner_user_id=owner_user_id, **payload.model_dump())
        return self.repository.create_candidate(candidate)

    def get_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> Candidate | None:
        """Return a candidate only if it belongs to the authenticated recruiter."""
        return self.repository.get_candidate_for_owner(candidate_id, owner_user_id)

    def list_candidates_for_owner(self, owner_user_id: int) -> list[Candidate]:
        """Return all candidates owned by the authenticated recruiter."""
        return self.repository.list_candidates_for_owner(owner_user_id)

    def update_candidate_for_owner(self, candidate_id: int, owner_user_id: int, payload: CandidateUpdate) -> Candidate | None:
        """Apply a partial update only to the authenticated recruiter's candidate."""
        return self.repository.update_candidate_for_owner(candidate_id, owner_user_id, payload.model_dump(exclude_unset=True, exclude={"owner_user_id"}))

    def delete_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> bool:
        """Delete a candidate only when it belongs to the authenticated recruiter."""
        return self.repository.delete_candidate_for_owner(candidate_id, owner_user_id)
