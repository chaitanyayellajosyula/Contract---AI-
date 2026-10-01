from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.dependencies import get_db
from app.models.user import User, UserRole
from app.services.source_health_service import SourceHealthService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/source-health")
def get_source_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.role != UserRole.LEGACY_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return SourceHealthService(db).summarize()