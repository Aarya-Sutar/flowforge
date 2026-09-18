"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, dashboard, health, requests, rules, tasks
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.request_logging import RequestLoggingMiddleware

configure_logging()
logger = logging.getLogger("flowforge.app")

app = FastAPI(
    title="FlowForge API",
    description="Intelligent business process automation platform",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Centralized exception handling (spec §13): FastAPI's own handlers
    already cover HTTPException and request-validation errors with clean,
    specific responses — this only ever fires for genuinely unexpected bugs.
    The full exception (with traceback) is logged server-side, tagged with
    the same request_id RequestLoggingMiddleware assigned, so it can be
    correlated with the rest of that request's log lines. The client only
    ever sees a generic message — never a stack trace, a file path, or any
    other implementation detail that could help an attacker or just
    confuse a legitimate caller.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled_exception",
        extra={"request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(rules.router)
app.include_router(tasks.router)
app.include_router(dashboard.router)
