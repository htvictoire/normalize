"""HTTP route registration for the normalization API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.models import ConfirmRequest, SuggestRequest
from app.bootstrap import MainOrchestrator
from shared.models.instance import InstanceModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/normalize/suggest", response_model=InstanceModel)
def suggest_endpoint(payload: SuggestRequest) -> InstanceModel:
    return MainOrchestrator().suggest(payload, source_checksum=payload.source_checksum)


@router.get("/normalize/instances/{instance_id}", response_model=InstanceModel)
def get_instance_endpoint(instance_id: UUID) -> InstanceModel:
    instance = MainOrchestrator().get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"instance not found: {instance_id}")
    return instance


@router.put("/normalize/instances/{instance_id}/confirm", response_model=InstanceModel)
def confirm_endpoint(instance_id: UUID, payload: ConfirmRequest) -> InstanceModel:
    return MainOrchestrator().confirm(instance_id, payload)


@router.post("/normalize/instances/{instance_id}/profile", response_model=InstanceModel)
def profile_endpoint(instance_id: UUID) -> InstanceModel:
    return MainOrchestrator().profile(instance_id)


@router.post("/normalize/instances/{instance_id}/normalize", response_model=InstanceModel)
def normalize_endpoint(instance_id: UUID) -> InstanceModel:
    return MainOrchestrator().normalize(instance_id)
