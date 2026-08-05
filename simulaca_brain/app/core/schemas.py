"""
Shared Pydantic schema base classes.

Every request/response model in the project should build on
SimulacaBaseModel (directly or via TimestampedSchema) so behavior like
whitespace-stripping and strict-extra-field rejection is consistent
everywhere, instead of being repeated -- or forgotten -- per model.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimulacaBaseModel(BaseModel):
    """Base class for all Simulaca Pydantic schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )


class TimestampedSchema(SimulacaBaseModel):
    """Base schema for entities that track creation/update times."""

    created_at: datetime
    updated_at: datetime | None = None


class ErrorResponse(SimulacaBaseModel):
    """
    The single structured error shape returned by every endpoint in
    the API. Never contains raw exception internals -- only a stable
    error_code, a human-readable message, and optional client-safe
    details.
    """

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)