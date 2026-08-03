"""HTTP route registration for the normalization API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from shared.models.instance import InstanceModel

from app.api.models import ConfirmRequest, CreateConfirmedRequest, SuggestRequest
from app.bootstrap import MainOrchestrator

router = APIRouter()


def _orchestrator(request: Request) -> MainOrchestrator:
    return request.app.state.orchestrator  # type: ignore[no-any-return]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/normalize/suggest", response_model=InstanceModel)
def suggest_endpoint(request: Request, payload: SuggestRequest) -> InstanceModel:
    return _orchestrator(request).suggest(payload)


@router.post("/normalize/layout", response_model=InstanceModel)
def layout_endpoint(request: Request, payload: SuggestRequest) -> InstanceModel:
    return _orchestrator(request).resolve_layout(payload)


@router.post("/normalize/instances/{instance_id}/type", response_model=InstanceModel)
def type_endpoint(request: Request, instance_id: UUID) -> InstanceModel:
    return _orchestrator(request).type_columns(instance_id)


@router.post("/normalize/instances", response_model=InstanceModel)
def create_confirmed_endpoint(request: Request, payload: CreateConfirmedRequest) -> InstanceModel:
    return _orchestrator(request).create_confirmed(payload, payload.confirmed_config)


@router.get("/normalize/instances/{instance_id}", response_model=InstanceModel)
def get_instance_endpoint(request: Request, instance_id: UUID) -> InstanceModel:
    instance = _orchestrator(request).get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"instance not found: {instance_id}")
    return instance


@router.put("/normalize/instances/{instance_id}/confirm", response_model=InstanceModel)
def confirm_endpoint(request: Request, instance_id: UUID, payload: ConfirmRequest) -> InstanceModel:
    return _orchestrator(request).confirm(
        instance_id, payload.confirmed_config, payload.source_file
    )


@router.post("/normalize/instances/{instance_id}/profile", response_model=InstanceModel)
def profile_endpoint(request: Request, instance_id: UUID) -> InstanceModel:
    return _orchestrator(request).profile(instance_id)


@router.post("/normalize/instances/{instance_id}/normalize", response_model=InstanceModel)
def normalize_endpoint(request: Request, instance_id: UUID) -> InstanceModel:
    return _orchestrator(request).normalize(instance_id)
