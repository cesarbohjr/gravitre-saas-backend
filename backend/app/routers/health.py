"""BE-00: Health check. No auth required."""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """GET /health — returns 200 without auth."""
    return {"status": "ok"}
