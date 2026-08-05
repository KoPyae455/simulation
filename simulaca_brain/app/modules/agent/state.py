"""Domain state owned and updated by individual agents."""

from enum import Enum

from pydantic import AliasChoices, Field

from app.core.schemas import SimulacaBaseModel


class NeedType(str, Enum):
    """Identifiers for the needs managed by an agent's internal state."""

    HUNGER = "hunger"
    THIRST = "thirst"
    FATIGUE = "fatigue"
    SAFETY = "safety"
    COMFORT = "comfort"
    SOCIAL = "social"


class AgentNeeds(SimulacaBaseModel):
    """Mutable need levels on a 0--100 scale, where higher values are more urgent."""

    hunger: int = Field(default=0, ge=0, le=100)
    thirst: int = Field(default=0, ge=0, le=100)
    fatigue: int = Field(
        default=0,
        ge=0,
        le=100,
        validation_alias=AliasChoices("fatigue", "rest"),
    )
    safety: int = Field(default=0, ge=0, le=100)
    comfort: int = Field(default=0, ge=0, le=100)
    social: int = Field(default=0, ge=0, le=100)

    def get(self, need: NeedType) -> int:
        """Return the current urgency level for ``need``."""
        return getattr(self, need.value)

    def set(self, need: NeedType, value: int) -> int:
        """Set ``need`` to ``value`` and return its clamped resulting level."""
        clamped_value = self._clamp(value)
        setattr(self, need.value, clamped_value)
        return clamped_value

    def increase(self, need: NeedType, amount: int) -> int:
        """Increase ``need`` by ``amount`` and return its clamped resulting level."""
        return self.set(need, self.get(need) + amount)

    def decrease(self, need: NeedType, amount: int) -> int:
        """Decrease ``need`` by ``amount`` and return its clamped resulting level."""
        return self.set(need, self.get(need) - amount)

    def is_critical(self, need: NeedType, threshold: int = 80) -> bool:
        """Return whether ``need`` is at or above a clamped urgency threshold."""
        return self.get(need) >= self._clamp(threshold)

    def highest_priority(self) -> NeedType | None:
        """Return the most urgent need, or ``None`` when every need is zero."""
        highest = max(NeedType, key=self.get)
        return highest if self.get(highest) > 0 else None

    @staticmethod
    def _clamp(value: int) -> int:
        """Constrain a numeric need level to the supported range."""
        return max(0, min(100, value))
