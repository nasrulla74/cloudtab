"""Global exception handlers for the FastAPI application."""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI application."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return a clean 422 with structured validation errors."""
        errors = []
        for err in exc.errors():
            field = " -> ".join(str(loc) for loc in err.get("loc", []))
            errors.append({
                "field": field,
                "message": err.get("msg", "Validation error"),
                "type": err.get("type", "unknown"),
            })
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            errors,
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "errors": errors,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """Handle database integrity constraint violations (unique, FK, etc.)."""
        error_msg = str(exc.orig) if exc.orig else str(exc)

        # Detect common constraint violations
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            detail = "A record with this value already exists"
            status_code = 409
        elif "foreign key" in error_msg.lower():
            detail = "Referenced record does not exist or cannot be removed"
            status_code = 409
        else:
            detail = "Database constraint violation"
            status_code = 409

        logger.warning(
            "IntegrityError on %s %s: %s",
            request.method,
            request.url.path,
            error_msg,
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": detail},
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(
        request: Request, exc: OperationalError
    ) -> JSONResponse:
        """Handle database connection/operational errors."""
        logger.error(
            "Database operational error on %s %s: %s",
            request.method,
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily unavailable"},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions — log full traceback, return 500."""
        logger.error(
            "Unhandled exception on %s %s: %s\n%s",
            request.method,
            request.url.path,
            str(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
