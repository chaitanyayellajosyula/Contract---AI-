from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> Job:
    """Create a new job record."""
    service = JobService(db)
    return service.create_job(payload)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    remote_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[Job]:
    """List jobs with optional filters."""
    service = JobService(db)
    return service.list_jobs(
        title=title,
        company=company,
        location=location,
        employment_type=employment_type,
        remote_type=remote_type,
        status=status,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    """Return a single job by identifier."""
    service = JobService(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)) -> Job:
    """Apply a partial update to an existing job."""
    service = JobService(db)
    job = service.update_job(job_id, payload)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete an existing job."""
    service = JobService(db)
    deleted = service.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
