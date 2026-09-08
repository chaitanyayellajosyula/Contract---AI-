from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.submission import Submission, SubmissionStatusHistory


class SubmissionRepository:
    """Persistence operations for candidate submissions."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, submission: Submission) -> Submission:
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def get(self, submission_id: int) -> Submission | None:
        return self.db.get(Submission, submission_id)

    def get_for_candidate_and_job(self, candidate_id: int, job_id: int) -> Submission | None:
        return self.db.query(Submission).filter(Submission.candidate_id == candidate_id, Submission.job_id == job_id).first()

    def list_for_owner(self, owner_user_id: int, status: str | None = None, job_id: int | None = None, candidate_id: int | None = None) -> list[Submission]:
        query = self.db.query(Submission).join(Submission.candidate).filter(Candidate.owner_user_id == owner_user_id)
        return self._apply_filters(query, status, job_id, candidate_id).order_by(Submission.created_at.desc()).all()

    def list_for_company(self, company_id: int, status: str | None = None, job_id: int | None = None, candidate_id: int | None = None) -> list[Submission]:
        query = self.db.query(Submission).filter(Submission.company_id == company_id)
        return self._apply_filters(query, status, job_id, candidate_id).order_by(Submission.created_at.desc()).all()

    def list_history(self, submission_id: int) -> list[SubmissionStatusHistory]:
        return self.db.query(SubmissionStatusHistory).filter(SubmissionStatusHistory.submission_id == submission_id).order_by(SubmissionStatusHistory.created_at.asc()).all()

    def update(self, submission: Submission, updates: dict[str, Any], history: SubmissionStatusHistory | None = None) -> Submission:
        for field, value in updates.items():
            setattr(submission, field, value)
        if history is not None:
            self.db.add(history)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def delete(self, submission: Submission) -> None:
        self.db.delete(submission)
        self.db.commit()

    @staticmethod
    def _apply_filters(query: Any, status: str | None, job_id: int | None, candidate_id: int | None) -> Any:
        if status is not None:
            query = query.filter(Submission.status == status)
        if job_id is not None:
            query = query.filter(Submission.job_id == job_id)
        if candidate_id is not None:
            query = query.filter(Submission.candidate_id == candidate_id)
        return query