from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.api.routes import router
from app.config import get_settings
from app.db import init_db
from app.exceptions import AppError
from app.observability import RequestLoggingMiddleware, configure_logging, logger

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


def _request_id(request: Request) -> str:
    """Read the request ID prepared by middleware for an error response."""
    return getattr(request.state, "request_id", "-")


def _error_response(request: Request, *, code: str, message: str, status_code: int) -> JSONResponse:
    """Create a unified safe error payload and preserve the request correlation ID."""
    response = JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "request_id": _request_id(request)},
    )
    response.headers["X-Request-ID"] = _request_id(request)
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Return expected business errors without leaking implementation details."""
    return _error_response(request, code=exc.code, message=exc.message, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map request validation failures to the public error contract."""
    return _error_response(request, code="validation_error", message="Request validation failed.", status_code=422)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map framework HTTP errors such as 404 and 405 to the public error contract."""
    messages = {404: "Resource not found.", 405: "Method not allowed."}
    return _error_response(
        request,
        code="http_error",
        message=messages.get(exc.status_code, "Request could not be completed."),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures internally and return a non-sensitive 500 response."""
    logger.error(
        "Unhandled application error",
        exc_info=settings.debug,
        extra={
            "request_id": _request_id(request),
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        },
    )
    return _error_response(request, code="internal_error", message="Internal server error.", status_code=500)


@app.on_event("startup")
def on_startup() -> None:
    """Create local storage after database migrations have been applied."""
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    init_db()


@app.get("/health")
def health() -> dict:
    """Return a minimal health response for local and container checks."""
    return {"status": "ok", "mock_mode": settings.mock_mode}


app.include_router(router)
