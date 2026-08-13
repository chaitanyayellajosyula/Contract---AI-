from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.repositories.candidate_repository import CandidateRepository
from app.schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateService:
    """Service layer for candidate persistence."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = CandidateRepository(db)

    def create_candidate(self, payload: CandidateCreate) -> Candidate:
        """Create a new candidate record from validated input."""
        candidate = Candidate(**payload.model_dump())
        return self.repository.create_candidate(candidate)

    def get_candidate(self, candidate_id: int) -> Candidate | None:
        """Return a single candidate by identifier, if present."""
        return self.repository.get_candidate(candidate_id)

    def list_candidates(self) -> list[Candidate]:
        """Return all candidates."""
        return self.repository.list_candidates()

    def update_candidate(self, candidate_id: int, payload: CandidateUpdate) -> Candidate | None:
        """Apply a partial update to an existing candidate record."""
        return self.repository.update_candidate(candidate_id, payload.model_dump(exclude_unset=True))

    def delete_candidate(self, candidate_id: int) -> bool:
        """Delete a candidate record by identifier."""
        return self.repository.delete_candidate(candidate_id)
