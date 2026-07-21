from fastapi import APIRouter

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
def list_vendors() -> list[dict[str, str]]:
    return []
