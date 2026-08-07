"""Cognition and planning errors."""

from typing import Any

from app.core.exceptions import DomainValidationError, SimulacaError


class LLMPlanningError(SimulacaError):
    """Raised when the LLM planner cannot produce a valid plan."""

    error_code = "llm_planning_error"
    http_status = 502


class InvalidPlanError(DomainValidationError):
    """Raised when a plan fails structural or registry validation."""

    error_code = "invalid_plan"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)
