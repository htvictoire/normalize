"""Shared pydantic base model for app and API contracts."""

from pydantic import BaseModel, ConfigDict


class MainModel(BaseModel):
    """Strict shared base model with no extra fields."""

    model_config = ConfigDict(extra="forbid")
