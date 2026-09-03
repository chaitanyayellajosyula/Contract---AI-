from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.submission import Submission


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

    def list_for_owner(self, owner_user_id: int) -> list[Submission]:
        return self.db.query(Submission).join(Submission.candidate).filter(Candidate.owner_user_id == owner_user_id).order_by(Submission.created_at.desc()).all()

    def list_for_company(self, company_id: int) -> list[Submission]:
        return self.db.query(Submission).filter(Submission.company_id == company_id).order_by(Submission.created_at.desc()).all()

    def update(self, submission: Submission, updates: dict[str, Any]) -> Submission:
        for field, value in updates.items():
            setattr(submission, field, value)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def delete(self, submission: Submission) -> None:
        self.db.delete(submission)
        self.db.commit()