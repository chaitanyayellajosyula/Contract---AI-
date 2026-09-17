from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, get_optional_current_user
from app.core.dependencies import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobIngestionSummary, JobResponse, JobUpdate, JobUserStatusUpdate
from app.services.job_service import JobService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _serialize_job(job: Job, user_status=None) -> JobResponse:
    response = JobResponse.model_validate(job)
    response.company = job.company.name if job.company is not None else job.source_company
    if user_status is not None:
        response.viewed = user_status.viewed
        response.saved = user_status.saved
        response.hidden = user_status.hidden
        response.bookmarked = user_status.saved
    else:
        response.saved = job.bookmarked
        response.hidden = False
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
    response: Response,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    employment_type: str | None = None,
    remote_type: str | None = None,
    status: str | None = None,
    source: str | None = None,
    engagement: str | None = None,
    freshness: str | None = Query(default=None, pattern="^(today|last_3_days|last_7_days|older)$"),
    viewed: bool | None = None,
    saved: bool | None = None,
    hidden: bool | None = None,
    bookmarked: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> list[JobResponse]:
    """List jobs with optional filters and pagination."""
    service = JobService(db)

    jobs, total = service.list_jobs(
        title=title,
        company=company,
        location=location,
        employment_type=employment_type,
        remote_type=remote_type,
        status=status,
        source=source,
        engagement=engagement,
        freshness=freshness,
        viewed=viewed,
        saved=saved,
        hidden=hidden,
        bookmarked=bookmarked,
        user=current_user,
        page=page,
        page_size=page_size,
    )

    statuses = service.get_user_statuses(current_user.id, [job.id for job in jobs]) if current_user else {}
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    return [_serialize_job(job, statuses.get(job.id)) for job in jobs]


@router.patch("/{job_id}/status", response_model=JobResponse)
def update_job_status(
    job_id: int,
    payload: JobUserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Update the authenticated user's workflow state for one job."""
    service = JobService(db)
    status_record = service.set_user_status(current_user.id, job_id, payload.model_dump(exclude_unset=True))
    if status_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    job = service.get_job(job_id)
    return _serialize_job(job, status_record)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> JobResponse:
    """Return a single job by identifier."""
    service = JobService(db)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    statuses = JobService(db).get_user_statuses(current_user.id, [job.id]) if current_user else {}
    return _serialize_job(job, statuses.get(job.id))


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
