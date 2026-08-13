from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.user import User, UserRole
from app.repositories.candidate_repository import CandidateRepository
from app.schemas.candidate import CandidateCreate, CandidateUpdate


class CandidateService:
    """Service layer for candidate persistence and ownership enforcement.
    
    This service enforces authorization rules:
    - RECRUITER: can only access/modify their own candidates
    - COMPANY_ADMIN: can access/modify all candidates in their company
    - Different company: returns None (triggers 404)
    """

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = CandidateRepository(db)

    def create_candidate(self, current_user: User, payload: CandidateCreate) -> Candidate:
        """Create a new candidate record.
        
        Security:
        - owner_user_id is always set to current_user.id
        - company_id is always derived from current_user.company_id
        - Client cannot override these fields
        - Raises 400 if user has no company assignment
        """
        if current_user.company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must be assigned to a company to create candidates"
            )

        candidate = Candidate(
            owner_user_id=current_user.id,
            company_id=current_user.company_id,
            **payload.model_dump()
        )
        return self.repository.create_candidate(candidate)

    def get_candidate_for_user(self, candidate_id: int, current_user: User) -> Candidate | None:
        """Get a candidate with role-based authorization.
        
        - RECRUITER: only their own candidates
        - COMPANY_ADMIN: any candidate in their company
        - Different company: returns None (triggers 404)
        """
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            return None

        if self._user_can_access_candidate(current_user, candidate):
            return candidate

        return None

    def list_candidates_for_user(self, current_user: User) -> list[Candidate]:
        """List candidates with role-based authorization.
        
        - RECRUITER: only their own candidates
        - COMPANY_ADMIN: all candidates in their company
        """
        if self._is_recruiter(current_user):
            return self.repository.list_candidates_for_owner(current_user.id)
        elif self._is_company_admin(current_user):
            if current_user.company_id is None:
                return []
            return self.repository.list_candidates_for_company(current_user.company_id)
        return []

    def update_candidate_for_user(self, candidate_id: int, current_user: User, payload: CandidateUpdate) -> Candidate | None:
        """Update a candidate with role-based authorization and field protection.
        
        - RECRUITER: only their own candidates
        - COMPANY_ADMIN: any candidate in their company
        - owner_user_id and company_id are never modified (stripped from updates)
        """
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            return None

        if not self._user_can_access_candidate(current_user, candidate):
            return None

        # Remove security fields that should never be modified
        updates = payload.model_dump(exclude_unset=True, exclude={"owner_user_id", "company_id"})

        if self._is_recruiter(current_user):
            return self.repository.update_candidate_for_owner(candidate_id, current_user.id, updates)
        elif self._is_company_admin(current_user):
            return self.repository.update_candidate_for_company(candidate_id, current_user.company_id, updates)

        return None

    def delete_candidate_for_user(self, candidate_id: int, current_user: User) -> bool:
        """Delete a candidate with role-based authorization.
        
        - RECRUITER: only their own candidates
        - COMPANY_ADMIN: any candidate in their company
        """
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            return False

        if not self._user_can_access_candidate(current_user, candidate):
            return False

        if self._is_recruiter(current_user):
            return self.repository.delete_candidate_for_owner(candidate_id, current_user.id)
        elif self._is_company_admin(current_user):
            return self.repository.delete_candidate_for_company(candidate_id, current_user.company_id)

        return False

    # Helper methods for authorization logic

    def _is_recruiter(self, user: User) -> bool:
        """Check if user has RECRUITER role."""
        return user.role == UserRole.RECRUITER.value

    def _is_company_admin(self, user: User) -> bool:
        """Check if user has COMPANY_ADMIN role."""
        return user.role == UserRole.COMPANY_ADMIN.value

    def _user_can_access_candidate(self, user: User, candidate: Candidate) -> bool:
        """Determine if user has access to candidate based on role and ownership/company.
        
        Returns True if:
        - User is recruiter and owns the candidate
        - User is company admin and candidate belongs to their company
        
        Returns False otherwise (different company, insufficient role).
        """
        if self._is_recruiter(user):
            # Recruiters can only access their own candidates
            return candidate.owner_user_id == user.id

        if self._is_company_admin(user):
            # Company admins can access candidates in their company
            return candidate.company_id == user.company_id

        # Any other role: no access
        return False

    # Legacy recruiter-only methods for backward compatibility

    def get_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> Candidate | None:
        """Return a candidate only if it belongs to the authenticated recruiter.
        
        DEPRECATED: Use get_candidate_for_user() instead.
        Kept for backward compatibility with existing tests.
        """
        return self.repository.get_candidate_for_owner(candidate_id, owner_user_id)

    def list_candidates_for_owner(self, owner_user_id: int) -> list[Candidate]:
        """Return all candidates owned by the authenticated recruiter.
        
        DEPRECATED: Use list_candidates_for_user() instead.
        Kept for backward compatibility with existing tests.
        """
        return self.repository.list_candidates_for_owner(owner_user_id)

    def update_candidate_for_owner(self, candidate_id: int, owner_user_id: int, payload: CandidateUpdate) -> Candidate | None:
        """Apply a partial update only to the authenticated recruiter's candidate.
        
        DEPRECATED: Use update_candidate_for_user() instead.
        Kept for backward compatibility with existing tests.
        """
        return self.repository.update_candidate_for_owner(candidate_id, owner_user_id, payload.model_dump(exclude_unset=True, exclude={"owner_user_id", "company_id"}))

    def delete_candidate_for_owner(self, candidate_id: int, owner_user_id: int) -> bool:
        """Delete a candidate only when it belongs to the authenticated recruiter.
        
        DEPRECATED: Use delete_candidate_for_user() instead.
        Kept for backward compatibility with existing tests.
        """
        return self.repository.delete_candidate_for_owner(candidate_id, owner_user_id)
