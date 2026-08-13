from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate import Candidate


class CandidateRepository:
    """Repository for candidate persistence and lookup operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        self.db = db

    def create_candidate(self, candidate: Candidate) -> Candidate:
        """Create and persist a new candidate record."""
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def get_candidate(self, candidate_id: int) -> Candidate | None:
        """Return a candidate by identifier, if present."""
        return self.db.get(Candidate, candidate_id)

    def list_candidates(self) -> list[Candidate]:
        """Return all candidates ordered by creation time."""
        return self.db.query(Candidate).order_by(Candidate.created_at.desc()).all()

    def update_candidate(self, candidate_id: int, updates: dict[str, Any]) -> Candidate | None:
        """Apply partial updates to an existing candidate record."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return None

        for field, value in updates.items():
            if hasattr(candidate, field):
                setattr(candidate, field, value)

        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def delete_candidate(self, candidate_id: int) -> bool:
        """Delete a candidate record by identifier."""
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            return False

        self.db.delete(candidate)
        self.db.commit()
        return True
