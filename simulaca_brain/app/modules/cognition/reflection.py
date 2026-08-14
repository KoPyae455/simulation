"""Episode reflection and semantic knowledge extraction for V0.8."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, ValidationError

from app.core.llm.base import LLMProvider
from app.core.schemas import SimulacaBaseModel
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.action_plan import ActionPlan


class EpisodeAction(SimulacaBaseModel):
    """One executed or planned action inside an episode."""

    action: str
    target: str | None = None


class EpisodeRecord(SimulacaBaseModel):
    """Structured input consumed by the reflection engine."""

    episode_id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    agent_name: str
    start_tick: int
    end_tick: int
    started_at: datetime
    ended_at: datetime
    goal: str
    planner: str
    initial_needs: AgentNeeds
    final_needs: AgentNeeds
    actions: list[EpisodeAction] = Field(default_factory=list)
    summary: str = ""
    success: bool


class KnowledgeFact(SimulacaBaseModel):
    """Reusable semantic relation extracted from one episode."""

    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    object: str = Field(min_length=1)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class ReflectionStructuredOutput(SimulacaBaseModel):
    """Validated reflection payload (LLM-generated or heuristic fallback)."""

    summary: str = Field(min_length=1)
    success: bool
    knowledge: list[KnowledgeFact] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)


class ReflectionResult(SimulacaBaseModel):
    """Result returned to the simulation after one reflection call."""

    output: ReflectionStructuredOutput
    source: str
    error: str | None = None


class ReflectionEngine:
    """Convert completed episodes into structured knowledge."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    def reflect(self, episode: EpisodeRecord) -> ReflectionResult:
        """Reflect on a completed episode using LLM output with safe fallback."""
        if self._provider is None:
            return ReflectionResult(output=self._heuristic_reflection(episode), source="heuristic")

        prompt = self._build_reflection_prompt(episode)
        try:
            raw = self._provider.generate(prompt, system_prompt=self._system_prompt())
            parsed = self._parse_output(raw)
            if not parsed.knowledge:
                parsed = self._merge_with_heuristics(parsed, episode)
            return ReflectionResult(output=parsed, source="llm")
        except Exception as exc:
            fallback = self._heuristic_reflection(episode)
            return ReflectionResult(output=fallback, source="heuristic", error=str(exc))

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a simulation reflection module. "
            "Extract concise, reusable knowledge from one completed agent episode. "
            "Return only JSON with schema: "
            "{summary: string, success: boolean, knowledge: [{subject,predicate,object,confidence}], lessons: [string]}."
        )

    @staticmethod
    def _build_reflection_prompt(episode: EpisodeRecord) -> str:
        payload = {
            "episode_id": str(episode.episode_id),
            "agent_name": episode.agent_name,
            "goal": episode.goal,
            "planner": episode.planner,
            "start_tick": episode.start_tick,
            "end_tick": episode.end_tick,
            "initial_needs": episode.initial_needs.model_dump(mode="json"),
            "final_needs": episode.final_needs.model_dump(mode="json"),
            "actions": [action.model_dump(mode="json") for action in episode.actions],
            "summary": episode.summary,
            "success": episode.success,
            "requirements": [
                "Do not output chain-of-thought.",
                "Prefer environment/action/outcome facts useful for future planning.",
                "Set confidence in [0,1].",
            ],
        }
        return json.dumps(payload, indent=2)

    @staticmethod
    def _parse_output(raw_response: str) -> ReflectionStructuredOutput:
        payload_text = raw_response.strip()
        if payload_text.startswith("```"):
            payload_text = payload_text.removeprefix("```json").removeprefix("```").strip()
            if payload_text.endswith("```"):
                payload_text = payload_text[:-3].strip()

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Reflection response was not valid JSON.") from exc

        try:
            return ReflectionStructuredOutput.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("Reflection response did not match schema.") from exc

    def _heuristic_reflection(self, episode: EpisodeRecord) -> ReflectionStructuredOutput:
        knowledge = self._heuristic_knowledge(episode)
        delta = self._goal_delta(episode)
        summary = (
            f"{episode.agent_name} pursued goal '{episode.goal}' from tick {episode.start_tick} "
            f"to {episode.end_tick} and {'succeeded' if episode.success else 'did not succeed'}"
        )
        if delta is not None:
            summary = f"{summary}. Need delta for {episode.goal}: {delta}."
        lessons: list[str] = []
        if knowledge:
            lessons.append(
                "A reusable strategy was observed for this goal."
            )
        elif episode.success:
            lessons.append("The action sequence succeeded and can be retried in similar context.")
        else:
            lessons.append("The episode failed; prefer alternative targets or actions next time.")

        return ReflectionStructuredOutput(
            summary=summary,
            success=episode.success,
            knowledge=knowledge,
            lessons=lessons,
        )

    def _merge_with_heuristics(
        self,
        structured: ReflectionStructuredOutput,
        episode: EpisodeRecord,
    ) -> ReflectionStructuredOutput:
        if structured.knowledge:
            return structured
        heuristic = self._heuristic_knowledge(episode)
        if not heuristic:
            return structured
        return ReflectionStructuredOutput(
            summary=structured.summary,
            success=structured.success,
            knowledge=heuristic,
            lessons=structured.lessons,
        )

    @staticmethod
    def _goal_delta(episode: EpisodeRecord) -> int | None:
        if episode.goal == "drink":
            return episode.initial_needs.thirst - episode.final_needs.thirst
        if episode.goal == "eat":
            return episode.initial_needs.hunger - episode.final_needs.hunger
        if episode.goal == "sleep":
            return episode.initial_needs.fatigue - episode.final_needs.fatigue
        return None

    def _heuristic_knowledge(self, episode: EpisodeRecord) -> list[KnowledgeFact]:
        target = self._primary_target(episode)
        if target is None:
            return []
        if episode.goal == "drink" and episode.success:
            return [KnowledgeFact(subject=target, predicate="provides", object="drinkable water", confidence=0.68)]
        if episode.goal == "eat" and episode.success:
            return [KnowledgeFact(subject=target, predicate="provides", object="edible food", confidence=0.66)]
        if episode.goal == "sleep" and episode.success:
            return [KnowledgeFact(subject=target, predicate="supports", object="rest recovery", confidence=0.62)]
        return []

    @staticmethod
    def _primary_target(episode: EpisodeRecord) -> str | None:
        for action in episode.actions:
            if action.target:
                return action.target
        return None