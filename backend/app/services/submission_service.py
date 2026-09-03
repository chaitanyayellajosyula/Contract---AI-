from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.submission import SubmissionCreate, SubmissionStatusUpdate
from app.services.candidate_service import CandidateService


class SubmissionService:
    """Submission workflow and company/ownership authorization."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = SubmissionRepository(db)

    def create(self, current_user: User, payload: SubmissionCreate) -> Submission:
        self._require_company(current_user)
        candidate = CandidateService(self.db).get_candidate_for_user(payload.candidate_id, current_user)
        job = self.db.get(Job, payload.job_id)
        job_company_id = self._job_company_id(job)
        if candidate is None or job_company_id is None or job_company_id != current_user.company_id or candidate.company_id != current_user.company_id:
            raise self._not_found()
        if self.repository.get_for_candidate_and_job(candidate.id, job.id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Candidate is already submitted to this job")
        return self.repository.create(Submission(candidate_id=candidate.id, job_id=job.id, company_id=current_user.company_id, submitted_by_user_id=current_user.id, status=SubmissionStatus.SUBMITTED.value, notes=payload.notes))

    def list_for_user(self, current_user: User) -> list[Submission]:
        if current_user.role == UserRole.RECRUITER.value:
            return self.repository.list_for_owner(current_user.id)
        if current_user.role == UserRole.COMPANY_ADMIN.value and current_user.company_id is not None:
            return self.repository.list_for_company(current_user.company_id)
        return []

    def get_for_user(self, submission_id: int, current_user: User) -> Submission | None:
        submission = self.repository.get(submission_id)
        return submission if submission is not None and self._can_access(current_user, submission) else None

    def update_for_user(self, submission_id: int, current_user: User, payload: SubmissionStatusUpdate) -> Submission | None:
        submission = self.get_for_user(submission_id, current_user)
        return None if submission is None else self.repository.update(submission, payload.model_dump(exclude_unset=True))

    def delete_for_user(self, submission_id: int, current_user: User) -> bool:
        submission = self.get_for_user(submission_id, current_user)
        if submission is None:
            return False
        self.repository.delete(submission)
        return True

    def _can_access(self, user: User, submission: Submission) -> bool:
        if user.role == UserRole.RECRUITER.value:
            return submission.candidate.owner_user_id == user.id
        return user.role == UserRole.COMPANY_ADMIN.value and submission.company_id == user.company_id

    @staticmethod
    def _job_company_id(job: Job | None) -> int | None:
        if job is None:
            return None
        if job.company_id is not None:
            return job.company_id
        if job.recruiter is not None and job.recruiter.vendor is not None:
            return job.recruiter.vendor.company_id
        return None

    @staticmethod
    def _require_company(user: User) -> None:
        if user.company_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must be assigned to a company")

    @staticmethod
    def _not_found() -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission resource not found")