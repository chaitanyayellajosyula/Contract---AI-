from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionHistoryResponse, SubmissionResponse, SubmissionStatusUpdate
from app.services.submission_service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(payload: SubmissionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Submission:
    return SubmissionService(db).create(current_user, payload)


@router.get("", response_model=list[SubmissionResponse])
def list_submissions(
    status_filter: SubmissionStatus | None = Query(default=None, alias="status"),
    job_id: int | None = Query(default=None, gt=0),
    candidate_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Submission]:
    return SubmissionService(db).list_for_user(current_user, status_filter.value if status_filter else None, job_id, candidate_id)


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Submission:
    submission = SubmissionService(db).get_for_user(submission_id, current_user)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.patch("/{submission_id}", response_model=SubmissionResponse)
def update_submission(submission_id: int, payload: SubmissionStatusUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Submission:
    submission = SubmissionService(db).update_for_user(submission_id, current_user, payload)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


@router.get("/{submission_id}/history", response_model=list[SubmissionHistoryResponse])
def get_submission_history(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list:
    history = SubmissionService(db).history_for_user(submission_id, current_user)
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return history


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Response:
    if not SubmissionService(db).delete_for_user(submission_id, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)