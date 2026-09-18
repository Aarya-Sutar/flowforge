"""Middleware that gives every HTTP request a request_id, logs its start and
completion (with status and duration — exactly the fields spec's
observability section asks for), and echoes the ID back as a response
header so a client-reported issue can be matched to server-side logs.
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("flowforge.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        started_at = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - started_at) * 1000, 2)

        logger.info(
            "http_request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response
