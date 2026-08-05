"""
Shared type aliases used across the Simulaca domain.

Defined once here so every future module (agent, memory, cognition,
world) refers to the same underlying types instead of each inventing
its own -- this is what keeps cross-module wiring painless as the
system grows.
"""

from uuid import UUID

EntityId = UUID
"""Unique identifier for any persisted domain entity (agent, memory record, event, ...)."""