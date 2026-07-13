"""FastAPI app factory and app singleton for the normalization API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exceptions import register_exception_handlers
from app.api.router import router
from app.bootstrap import MainOrchestrator


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.orchestrator = MainOrchestrator()
    yield


def create_app() -> FastAPI:
    """Create FastAPI app wired to the normalization router."""
    app = FastAPI(title="Normalization API", version="0.1.0", lifespan=_lifespan)
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
