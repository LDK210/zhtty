from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("hirepilot")


class StructuredLogFormatter(logging.Formatter):
    """Serialize allowlisted operational fields as one JSON log event."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a JSON event without request bodies, headers, or personal data."""
        event: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
            "method": getattr(record, "method", None),
            "path": getattr(record, "path", None),
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "job_id": getattr(record, "job_id", None),
            "resume_id": getattr(record, "resume_id", None),
            "stage": getattr(record, "stage", None),
        }
        return json.dumps(event, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the dedicated application logger exactly once."""
    logger.setLevel(level.upper())
    logger.propagate = False
    if any(getattr(handler, "_hirepilot_handler", False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler._hirepilot_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(StructuredLogFormatter())
    logger.addHandler(handler)


def new_request_id(value: str | None) -> str:
    """Return a bounded client request ID or a new server-generated UUID."""
    if value and len(value) <= 128 and all(character.isalnum() or character in "-_" for character in value):
        return value
    return uuid4().hex


def log_task_event(level: int, message: str, *, job_id: int, resume_id: int | None, stage: str) -> None:
    """Write a safe background-task event with job and resume correlation IDs."""
    logger.log(
        level,
        message,
        extra={"job_id": job_id, "resume_id": resume_id, "stage": stage},
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and write one structured event for every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware with the downstream ASGI application."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Execute the request while recording safe request metadata and duration."""
        request_id = new_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.error(
                "Request failed before a response was generated",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            request_id_context.reset(token)
