"""Prompt construction for the LLM cognitive planner."""

import json

from app.modules.cognition.action_registry import ActionRegistry
from app.modules.cognition.decision_context import DecisionContext

SYSTEM_PROMPT = """You are an NPC cognitive planner for a life simulation.

Your role:
- Examine the supplied decision context
- Consider agent needs, memories, and the current world
- Select only valid actions from the available action list
- Produce a minimal valid action plan as JSON

Rules:
- Do NOT invent unavailable resources, locations, entities, or actions
- Do NOT execute anything directly
- Do NOT include hidden chain-of-thought; keep reasoning_summary concise
- Return ONLY valid JSON matching the required schema
- Prefer the shortest plan that satisfies the current goal

Required JSON schema:
{
  "goal": "<current goal>",
  "reasoning_summary": "<one or two sentences>",
  "steps": [
    {
      "action": "<registered action>",
      "target": "<location or entity name or null>",
      "parameters": {}
    }
  ]
}
"""


class PromptBuilder:
    """Render bounded decision context into an LLM prompt."""

    def build_system_prompt(self) -> str:
        """Return the stable system prompt for NPC planning."""
        return SYSTEM_PROMPT

    def build_user_prompt(self, context: DecisionContext) -> str:
        """Serialize ``context`` into a structured planning prompt."""
        payload = {
            "agent": {
                "id": str(context.agent_id),
                "name": context.agent_name,
                "needs": context.needs.model_dump(mode="json"),
                "personality": context.personality,
            },
            "simulation": {
                "tick": context.tick,
                "datetime": context.simulation_datetime.isoformat(),
            },
            "goal": context.current_goal,
            "location": context.current_location.model_dump(mode="json") if context.current_location else None,
            "nearby_locations": [location.model_dump(mode="json") for location in context.nearby_locations],
            "nearby_entities": [entity.model_dump(mode="json") for entity in context.nearby_entities],
            "world_facts": context.world_facts,
            "relevant_memories": [
                {
                    "content": memory.content,
                    "description": memory.description,
                    "location": memory.location,
                    "event_type": memory.event_type,
                }
                for memory in context.relevant_memories
            ],
            "available_actions": context.available_actions or list(ActionRegistry.list_actions()),
            "action_constraints": context.action_constraints,
        }
        return json.dumps(payload, indent=2)
