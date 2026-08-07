"""Deterministic goal generation from agent needs."""

from app.modules.agent.state import AgentNeeds


class GoalGenerator:
    """Select the highest-priority goal from current agent needs."""

    _THRESHOLD = 80

    def generate(self, needs: AgentNeeds) -> str:
        """Return the single deterministic goal that best matches need priorities."""
        if needs.thirst > self._THRESHOLD:
            return "drink"
        if needs.hunger > self._THRESHOLD:
            return "eat"
        if needs.fatigue > self._THRESHOLD:
            return "sleep"
        return "idle"

    def reason_for(self, goal: str, needs: AgentNeeds) -> str:
        """Return a short explanation for why ``goal`` was selected."""
        if goal == "drink":
            return f"Thirst exceeded threshold at {needs.thirst}/100."
        if goal == "eat":
            return f"Hunger exceeded threshold at {needs.hunger}/100."
        if goal == "sleep":
            return f"Fatigue exceeded threshold at {needs.fatigue}/100."
        return "No critical need exceeded the threshold."
