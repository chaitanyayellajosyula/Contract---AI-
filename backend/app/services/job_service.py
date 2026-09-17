from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job
from app.models.job_user_status import JobUserStatus
from app.models.user import User
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

    def list_jobs(
        self,
        title: str | None = None,
        company: str | None = None,
        location: str | None = None,
        employment_type: str | None = None,
        remote_type: str | None = None,
        status: str | None = None,
        source: str | None = None,
        engagement: str | None = None,
        freshness: str | None = None,
        viewed: bool | None = None,
        saved: bool | None = None,
        hidden: bool | None = None,
        bookmarked: bool | None = None,
        user: User | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Job], int]:
        """Return paginated jobs matching the optional filters."""
        query = self.repository.db.query(Job)
        if user is not None:
            query = query.outerjoin(
                JobUserStatus,
                and_(JobUserStatus.job_id == Job.id, JobUserStatus.user_id == user.id),
            )

        if title is not None:
            query = query.filter(Job.title.ilike(f"%{title}%"))

        if company is not None:
            query = (
                query.outerjoin(Job.recruiter)
                .outerjoin(Recruiter.vendor)
                .outerjoin(Vendor.company)
                .filter(
                    or_(
                        Company.name.ilike(f"%{company}%"),
                        Job.company.has(Company.name.ilike(f"%{company}%")),
                        Job.source_company.ilike(f"%{company}%"),
                    )
                )
            )

        if location is not None:
            query = query.filter(Job.location.ilike(f"%{location}%"))

        if employment_type is not None or engagement is not None:
            engagement_filter = engagement or employment_type
            query = query.filter(Job.employment_type == engagement_filter)

        if remote_type is not None:
            query = query.filter(Job.remote_type == remote_type)

        if status is not None:
            query = query.filter(Job.status == status)

        if source is not None:
            query = query.filter(Job.source == source)

        if freshness is not None:
            freshness_field = func.coalesce(Job.posted_at, Job.created_at)
            now = datetime.utcnow()
            if freshness == "today":
                query = query.filter(freshness_field >= now.replace(hour=0, minute=0, second=0, microsecond=0))
            elif freshness == "last_3_days":
                query = query.filter(freshness_field >= now - timedelta(days=3))
            elif freshness == "last_7_days":
                query = query.filter(freshness_field >= now - timedelta(days=7))
            elif freshness == "older":
                query = query.filter(freshness_field < now - timedelta(days=7))

        if user is not None:
            status_viewed = func.coalesce(JobUserStatus.viewed, False)
            status_saved = func.coalesce(JobUserStatus.saved, False)
            status_hidden = func.coalesce(JobUserStatus.hidden, False)
            if viewed is not None:
                query = query.filter(status_viewed == viewed)
            if saved is not None or bookmarked is not None:
                query = query.filter(status_saved == (saved if saved is not None else bookmarked))
            if hidden is not None:
                query = query.filter(status_hidden == hidden)
        elif viewed is not None or saved is not None or hidden is not None:
            query = query.filter(False)
        if bookmarked is not None and user is None:
            query = query.filter(Job.bookmarked == bookmarked)

        total = query.count()

        offset = (page - 1) * page_size

        jobs = (
            query
            .order_by(func.coalesce(Job.posted_at, Job.created_at).desc(), Job.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        return jobs, total

    def get_user_statuses(self, user_id: int, job_ids: list[int]) -> dict[int, JobUserStatus]:
        if not job_ids:
            return {}
        statuses = self.db.query(JobUserStatus).filter(
            JobUserStatus.user_id == user_id,
            JobUserStatus.job_id.in_(job_ids),
        ).all()
        return {status.job_id: status for status in statuses}

    def set_user_status(self, user_id: int, job_id: int, updates: dict[str, bool | None]) -> JobUserStatus | None:
        if self.repository.get(job_id) is None:
            return None
        status = self.db.query(JobUserStatus).filter(
            JobUserStatus.user_id == user_id,
            JobUserStatus.job_id == job_id,
        ).first()
        if status is None:
            status = JobUserStatus(user_id=user_id, job_id=job_id)
            self.db.add(status)
        for field, value in updates.items():
            if value is not None:
                setattr(status, field, value)
        self.db.commit()
        self.db.refresh(status)
        return status

    def update_job(self, job_id: int, payload: JobUpdate) -> Job | None:
        """Apply a partial update to an existing job record."""
        return self.repository.update(job_id, payload.model_dump(exclude_unset=True))

    def ingest_jobs(self, source: str, normalized_jobs: list[dict[str, Any]]) -> dict[str, int | str]:
        """Persist a batch, updating changed jobs by source + source_job_id."""
        created = 0
        updated = 0
        skipped_duplicates = 0
        rejected = 0

        for item in normalized_jobs:
            if item is None:
                rejected += 1
                continue

            source_job_id = str(item.get("source_job_id")) if item.get("source_job_id") is not None else None
            if item.get("title") is None or not str(item["title"]).strip():
                rejected += 1
                continue
            if source_job_id is None:
                rejected += 1
                continue

            existing = self.repository.get_by_source_and_source_job_id(source, source_job_id)
            if existing is not None:
                updates = {
                    field: value
                    for field, value in item.items()
                    if field not in {"source", "source_job_id", "viewed", "bookmarked"}
                    and getattr(existing, field, None) != value
                }
                if updates:
                    self.repository.update(existing.id, updates)
                    updated += 1
                else:
                    skipped_duplicates += 1
                continue

            job = Job(**item)
            self.repository.create(job)
            created += 1

        return {
            "source": source,
            "fetched": len(normalized_jobs),
            "created": created,
            "updated": updated,
            "skipped_duplicates": skipped_duplicates,
            "rejected": rejected,
        }

    def delete_job(self, job_id: int) -> bool:
        """Delete a job record by identifier."""
        return self.repository.delete(job_id)
