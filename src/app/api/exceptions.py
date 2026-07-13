"""Global exception handlers for the normalization API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.errors import (
    InstanceNotFoundError,
    InvalidRequestError,
    InvalidStateError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Map deliberate domain errors to HTTP status.

    Only domain errors are mapped. An unhandled exception is a bug and must surface as
    500 rather than be dressed as a client error.
    """

    @app.exception_handler(InstanceNotFoundError)
    def not_found_handler(_request: Request, exc: InstanceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidStateError)
    def conflict_handler(_request: Request, exc: InvalidStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequestError)
    def bad_request_handler(_request: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
