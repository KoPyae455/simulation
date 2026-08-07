"""Registry of actions the simulation allows planners to propose."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    """Metadata describing one executable simulation action."""

    name: str
    description: str
    requires_target: bool = False


class ActionRegistry:
    """Catalog of valid actions planners may select from."""

    _ACTIONS: dict[str, ActionDefinition] = {
        "move": ActionDefinition(
            name="move",
            description="Move to a connected location.",
            requires_target=True,
        ),
        "eat": ActionDefinition(
            name="eat",
            description="Eat food at the current or target location.",
            requires_target=True,
        ),
        "drink": ActionDefinition(
            name="drink",
            description="Drink water at the current or target location.",
            requires_target=True,
        ),
        "sleep": ActionDefinition(
            name="sleep",
            description="Rest to recover fatigue.",
            requires_target=False,
        ),
        "idle": ActionDefinition(
            name="idle",
            description="Wait without changing location.",
            requires_target=False,
        ),
    }

    @classmethod
    def list_actions(cls) -> tuple[str, ...]:
        """Return all registered action names in stable order."""
        return tuple(cls._ACTIONS.keys())

    @classmethod
    def get(cls, action: str) -> ActionDefinition | None:
        """Return the definition for ``action`` when it is registered."""
        return cls._ACTIONS.get(action)

    @classmethod
    def is_valid(cls, action: str) -> bool:
        """Return whether ``action`` is a registered simulation action."""
        return action in cls._ACTIONS
