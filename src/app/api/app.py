"""FastAPI app factory and app singleton for normalization API."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.controllers import MainController
from app.api.router import create_router


def create_app() -> FastAPI:
    """Create FastAPI app wired to local controller implementation."""
    api = MainController()

    app = FastAPI(title="Normalization API", version="0.1.0")
    app.include_router(create_router(api))
    return app


app = create_app()
