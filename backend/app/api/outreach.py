from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User
from app.schemas.outreach import (
    OutreachDraftCreate,
    OutreachDraftPreview,
    OutreachDraftPreviewRequest,
    OutreachPage,
    OutreachResponse,
    OutreachStatusValue,
    OutreachUpdate,
)
from app.services.outreach_service import OutreachService

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.post("/draft-preview", response_model=OutreachDraftPreview)
def preview_outreach_draft(
    payload: OutreachDraftPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachDraftPreview:
    return OutreachService(db).preview(current_user, payload)


@router.post("/drafts", response_model=OutreachResponse, status_code=status.HTTP_201_CREATED)
def create_outreach_draft(
    payload: OutreachDraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachResponse:
    return OutreachService(db).create_draft(current_user, payload)


@router.get("", response_model=OutreachPage)
def list_outreach(
    candidate_id: int | None = Query(default=None, gt=0),
    job_id: int | None = Query(default=None, gt=0),
    vendor_id: int | None = Query(default=None, gt=0),
    contact_id: int | None = Query(default=None, gt=0),
    status_filter: OutreachStatusValue | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachPage:
    return OutreachService(db).list_for_user(
        current_user,
        candidate_id=candidate_id,
        job_id=job_id,
        vendor_id=vendor_id,
        contact_id=contact_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get("/{outreach_id}", response_model=OutreachResponse)
def get_outreach(
    outreach_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachResponse:
    outreach = OutreachService(db).get_for_user(outreach_id, current_user)
    if outreach is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach not found")
    return OutreachService._response(outreach)


@router.patch("/{outreach_id}", response_model=OutreachResponse)
def update_outreach(
    outreach_id: int,
    payload: OutreachUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachResponse:
    outreach = OutreachService(db).update_for_user(outreach_id, current_user, payload)
    if outreach is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach not found")
    return outreach


@router.post("/{outreach_id}/mark-sent", response_model=OutreachResponse)
def mark_outreach_sent(
    outreach_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachResponse:
    outreach = OutreachService(db).mark_sent(outreach_id, current_user)
    if outreach is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach not found")
    return outreach


@router.post("/{outreach_id}/cancel", response_model=OutreachResponse)
def cancel_outreach(
    outreach_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OutreachResponse:
    outreach = OutreachService(db).cancel(outreach_id, current_user)
    if outreach is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach not found")
    return outreach