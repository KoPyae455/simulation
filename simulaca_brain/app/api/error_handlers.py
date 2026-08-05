"""
Global FastAPI exception handlers.

Registered once in the app factory (see app.main.create_app) so every
route in the system returns the same ErrorResponse shape on failure --
whether the failure is a domain error, a routing error, a request
validation error, or something unexpected. This is the one place
internal exceptions get translated into client-safe JSON.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import SimulacaError
from app.core.schemas import ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the given FastAPI app."""

    @app.exception_handler(SimulacaError)
    async def handle_domain_error(request: Request, exc: SimulacaError) -> JSONResponse:
        """Translate any domain error into a structured JSON response."""
        logger.info(
            "Domain error while handling request",
            extra={"path": request.url.path, "error_code": exc.error_code},
        )
        body = ErrorResponse(error_code=exc.error_code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.http_status, content=body.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Normalize routing-level errors (e.g. 404 on an unmatched path) into the same shape."""
        body = ErrorResponse(error_code="http_error", message=str(exc.detail), details={})
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Replace FastAPI's default validation payload with the project's ErrorResponse shape."""
        body = ErrorResponse(
            error_code="request_validation_error",
            message="The request was invalid.",
            details={"errors": jsonable_encoder(exc.errors())},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all: log the real exception server-side, never expose internals to the client."""
        logger.exception(
            "Unhandled exception while processing request",
            extra={"path": request.url.path},
        )
        body = ErrorResponse(
            error_code="internal_error",
            message="An unexpected error occurred. Please try again later.",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=body.model_dump(mode="json"),
        )