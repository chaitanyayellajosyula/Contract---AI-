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

    def get_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> Candidate | None:
        """Return a candidate that belongs to the specified recruiter."""
        return self.db.query(Candidate).filter(Candidate.id == candidate_id, Candidate.owner_user_id == owner_user_id).first()

    def list_candidates(self) -> list[Candidate]:
        """Return all candidates ordered by creation time."""
        return self.db.query(Candidate).order_by(Candidate.created_at.desc()).all()

    def list_candidates_for_owner(self, owner_user_id: int) -> list[Candidate]:
        """Return all candidates owned by the specified recruiter."""
        return self.db.query(Candidate).filter(Candidate.owner_user_id == owner_user_id).order_by(Candidate.created_at.desc()).all()

    def get_candidate_for_company(self, candidate_id: int, company_id: int) -> Candidate | None:
        """Return a candidate that belongs to the specified company (for company admin access)."""
        return self.db.query(Candidate).filter(Candidate.id == candidate_id, Candidate.company_id == company_id).first()

    def list_candidates_for_company(self, company_id: int) -> list[Candidate]:
        """Return all candidates belonging to the specified company (for company admin access)."""
        return self.db.query(Candidate).filter(Candidate.company_id == company_id).order_by(Candidate.created_at.desc()).all()

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

    def update_candidate_for_owner(self, candidate_id: int, owner_user_id: int, updates: dict[str, Any]) -> Candidate | None:
        """Apply partial updates only to candidates owned by the specified recruiter."""
        candidate = self.get_candidate_for_owner(candidate_id, owner_user_id)
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

    def delete_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> bool:
        """Delete a candidate only when it belongs to the specified recruiter."""
        candidate = self.get_candidate_for_owner(candidate_id, owner_user_id)
        if candidate is None:
            return False

        self.db.delete(candidate)
        self.db.commit()
        return True

    def update_candidate_for_company(self, candidate_id: int, company_id: int, updates: dict[str, Any]) -> Candidate | None:
        """Apply partial updates only to candidates belonging to the specified company (for company admin access)."""
        candidate = self.get_candidate_for_company(candidate_id, company_id)
        if candidate is None:
            return None

        for field, value in updates.items():
            if hasattr(candidate, field):
                setattr(candidate, field, value)

        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def delete_candidate_for_company(self, candidate_id: int, company_id: int) -> bool:
        """Delete a candidate only when it belongs to the specified company (for company admin access)."""
        candidate = self.get_candidate_for_company(candidate_id, company_id)
        if candidate is None:
            return False

        self.db.delete(candidate)
        self.db.commit()
        return True
