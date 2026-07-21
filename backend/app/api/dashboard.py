from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard_summary() -> dict[str, object]:
    return {
        "message": "Dashboard ready",
        "stats": {
            "opportunities": 0,
            "vendors": 0,
            "recruiters": 0,
        },
    }
