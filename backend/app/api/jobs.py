from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobIngestionSummary, JobResponse, JobUpdate
from app.services.job_service import JobService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize_job(job: Job) -> JobResponse:
    response = JobResponse.model_validate(job)
    response.company = job.company.name if job.company is not None else None
    return response


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> Job:
    """Create a new job record."""
    service = JobService(db)
    return service.create_job(payload)


@router.post("/ingest/{source}", response_model=JobIngestionSummary)
def ingest_jobs(
    source: str,
    board: str = Query(default="stripe"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobIngestionSummary:
    """Fetch one public source and ingest normalized jobs without duplicates."""
    del current_user

    try:
        summary = IngestionService(db).ingest(source=source, identifier=board)
        return JobIngestionSummary(**summary)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[JobResponse])
def list_jobs(
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    remote_type: str | None = None,
    status: str | None = None,
    source: str | None = None,
    viewed: bool | None = None,
    bookmarked: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobResponse]:
    """List jobs with optional filters and pagination."""
    service = JobService(db)

    jobs, _total = service.list_jobs(
        title=title,
        company=company,
        location=location,
        employment_type=employment_type,
        remote_type=remote_type,
        status=status,
        source=source,
        viewed=viewed,
        bookmarked=bookmarked,
        page=page,
        page_size=page_size,
    )

    return [_serialize_job(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    """Return a single job by identifier."""
    service = JobService(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _serialize_job(job)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)) -> JobResponse:
    """Apply a partial update to an existing job."""
    service = JobService(db)
    job = service.update_job(job_id, payload)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _serialize_job(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete an existing job."""
    service = JobService(db)
    deleted = service.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
