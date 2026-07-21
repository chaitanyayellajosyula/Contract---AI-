from fastapi import APIRouter

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


@router.get("")
def list_recruiters() -> list[dict[str, str]]:
    return []
