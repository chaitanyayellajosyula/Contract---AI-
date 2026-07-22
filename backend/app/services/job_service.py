from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job
from app.models.recruiter import Recruiter
from app.models.vendor import Vendor
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobCreate, JobUpdate


class JobService:
    """Service layer containing business logic for job persistence."""

    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        self.repository = JobRepository(db)

    def create_job(self, payload: JobCreate) -> Job:
        """Create a new job record from validated input."""
        job = Job(**payload.model_dump())
        return self.repository.create(job)

    def get_job(self, job_id: int) -> Job | None:
        """Return a single job by identifier, if present."""
        return self.repository.get(job_id)

    def list_jobs(self, title: str | None = None, company: str | None = None, location: str | None = None, employment_type: str | None = None, remote_type: str | None = None, status: str | None = None) -> list[Job]:
        """Return jobs matching the optional filters."""
        query = self.repository.db.query(Job)

        if title is not None:
            query = query.filter(Job.title.ilike(f"%{title}%"))
        if company is not None:
            query = (
                query.join(Job.recruiter)
                .join(Recruiter.vendor)
                .join(Vendor.company)
                .filter(Company.name.ilike(f"%{company}%"))
            )
        if location is not None:
            query = query.filter(Job.location.ilike(f"%{location}%"))
        if employment_type is not None:
            query = query.filter(Job.employment_type == employment_type)
        if remote_type is not None:
            query = query.filter(Job.remote_type == remote_type)
        if status is not None:
            query = query.filter(Job.status == status)

        return query.order_by(Job.created_at.desc()).all()

    def update_job(self, job_id: int, payload: JobUpdate) -> Job | None:
        """Apply a partial update to an existing job record."""
        return self.repository.update(job_id, payload.model_dump(exclude_unset=True))

    def delete_job(self, job_id: int) -> bool:
        """Delete a job record by identifier."""
        return self.repository.delete(job_id)
