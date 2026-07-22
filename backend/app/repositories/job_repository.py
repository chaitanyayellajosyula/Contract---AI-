from typing import Any

from sqlalchemy.orm import Session

from app.models.job import Job


class JobRepository:
    """Repository for persisting and querying job records."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session."""
        self.db = db

    def create(self, job: Job) -> Job:
        """Create and persist a new job record."""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: int) -> Job | None:
        """Return a job by identifier, if present."""
        return self.db.get(Job, job_id)

    def get_all(self) -> list[Job]:
        """Return all persisted jobs."""
        return self.db.query(Job).order_by(Job.created_at.desc()).all()

    def update(self, job_id: int, updates: dict[str, Any]) -> Job | None:
        """Apply partial updates to an existing job record."""
        job = self.get(job_id)
        if job is None:
            return None

        for field, value in updates.items():
            if hasattr(job, field):
                setattr(job, field, value)

        self.db.commit()
        self.db.refresh(job)
        return job

    def delete(self, job_id: int) -> bool:
        """Delete a job record by identifier."""
        job = self.get(job_id)
        if job is None:
            return False

        self.db.delete(job)
        self.db.commit()
        return True
