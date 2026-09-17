"""Health check endpoint used by Docker healthchecks and load balancers."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check(response: Response, db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database_status = "up"
    except Exception:
        database_status = "down"

    if database_status != "up":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if database_status == "up" else "degraded",
        "database": database_status,
    }
