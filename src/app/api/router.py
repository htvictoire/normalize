"""HTTP route registration for the normalization API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.models import (
    ConfirmRequest,
    NormalizeRequest,
    SuggestRequest,
)
from app.api.paths import resolve_data_file
from app.models.instance import InstanceModel

if TYPE_CHECKING:
    from app.bootstrap import MainOrchestrator


def create_router(api: MainOrchestrator) -> APIRouter:
    """Create API router with health/suggest/confirm/profile/normalize routes."""
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/normalize/suggest", response_model=InstanceModel)
    def suggest_endpoint(payload: SuggestRequest) -> InstanceModel:
        try:
            data_file = resolve_data_file(payload.file)
            instance = api.suggest(
                file_path=data_file,
                source_file_name=payload.name,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return instance

    @router.put("/normalize/instances/{instance_id}/confirm", response_model=InstanceModel)
    def confirm_endpoint(instance_id: UUID, payload: ConfirmRequest) -> InstanceModel:
        try:
            instance = api.confirm(instance_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return instance

    @router.get("/normalize/instances/{instance_id}", response_model=InstanceModel)
    def get_instance_endpoint(instance_id: UUID) -> InstanceModel:
        instance = api.get_instance(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail=f"instance not found: {instance_id}")
        return instance

    @router.post("/normalize/instances/{instance_id}/profile", response_model=InstanceModel)
    def profile_endpoint(instance_id: UUID) -> InstanceModel:
        try:
            instance = api.profile(instance_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return instance

    @router.post("/normalize/instances/{instance_id}/normalize", response_model=InstanceModel)
    def normalize_endpoint(
        instance_id: UUID,
        payload: NormalizeRequest,
    ) -> InstanceModel:
        try:
            instance = api.normalize(
                instance_id,
                output_dir=payload.output_dir,
                mode=payload.mode,
                rules_version=payload.rules_version,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return instance

    return router
