"""
Domain exception hierarchy.

Every error raised by domain/service code should be one of these (or
a subclass added later), never a bare Exception. This is what lets
the API layer translate failures into structured JSON responses
without ever leaking internals (stack traces, driver errors, etc.)
back to a client.
"""

from typing import Any


class SimulacaError(Exception):
    """
    Base class for all domain errors in the Simulaca brain.

    Attributes:
        message: Human-readable description of what went wrong, safe
            to return to a client.
        error_code: Stable, machine-readable identifier for this error
            type (e.g. "entity_not_found"), safe to expose to clients.
        details: Optional structured context (e.g. which field
            failed), safe to expose to clients. Never put raw
            internals (stack traces, SQL, etc.) here.
        http_status: HTTP status code the API layer should map this
            error to.
    """

    error_code: str = "internal_error"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EntityNotFoundError(SimulacaError):
    """Raised when a requested entity does not exist."""

    error_code = "entity_not_found"
    http_status = 404

    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(
            f"{entity_type} '{entity_id}' was not found.",
            details={"entity_type": entity_type, "entity_id": str(entity_id)},
        )


class DomainValidationError(SimulacaError):
    """
    Raised when data is structurally valid but violates a domain rule
    (e.g. an agent's need value outside its allowed range).

    Distinct from pydantic.ValidationError, which covers structural
    and type validation at the schema boundary rather than domain
    rules.
    """

    error_code = "domain_validation_error"
    http_status = 422


class ConflictError(SimulacaError):
    """Raised when an operation conflicts with current state (e.g. duplicate creation)."""

    error_code = "conflict"
    http_status = 409


class RepositoryError(SimulacaError):
    """Raised when a persistence-layer operation fails unexpectedly."""

    error_code = "repository_error"
    http_status = 500