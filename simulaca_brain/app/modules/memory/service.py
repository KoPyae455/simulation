"""Application service for recording and reading agent memory."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.events import EventBus
from app.modules.activity.models import AgentEventType
from app.modules.activity.service import AgentEventService
from app.modules.memory.events import MemoryRecorded
from app.modules.memory.models import CreateMemoryRequest, Memory, MemoryType
from app.modules.memory.repository import MemoryRepository


class MemoryService:
    """Record memories through injected persistence and event-publication ports."""

    def __init__(
        self,
        repository: MemoryRepository,
        event_bus: EventBus,
        event_service: AgentEventService | None = None,
    ) -> None:
        """Create the service with its persistence and integration dependencies."""
        self._repository = repository
        self._event_bus = event_bus
        self._event_service = event_service

    def record(self, request: CreateMemoryRequest) -> Memory:
        """Persist a new memory and publish an event after persistence succeeds."""
        memory = Memory(
            id=uuid4(),
            agent_id=request.agent_id,
            memory_type=request.memory_type,
            content=request.content,
            tick=request.tick,
            timestamp=request.timestamp,
            event_type=request.event_type,
            description=request.description,
            location=request.location,
            result=request.result,
            importance=request.importance,
            metadata=request.metadata,
            attributes=request.attributes,
            created_at=request.timestamp or datetime.now(UTC),
        )
        persisted_memory = self._repository.save(memory)
        if self._event_bus is not None:
            self._event_bus.publish(MemoryRecorded(memory=persisted_memory))
        self._emit_memory_event(persisted_memory)
        return persisted_memory

    def list_memories(self, agent_id: UUID | None = None, limit: int = 20) -> list[Memory]:
        """Return the most recent memory records, optionally filtered to one agent."""
        return self._repository.list(agent_id=agent_id, limit=limit)

    def _emit_memory_event(self, memory: Memory) -> None:
        """Record a memory_created activity event for durable memories.

        Working-memory churn (rewritten every tick) is deliberately skipped
        so the activity timeline stays meaningful.
        """
        if self._event_service is None or memory.memory_type is MemoryType.WORKING:
            return
        self._event_service.record(
            agent_id=memory.agent_id,
            tick=memory.tick or 0,
            event_type=AgentEventType.MEMORY_CREATED,
            message=memory.content,
            metadata={
                "memory_id": str(memory.id),
                "memory_type": memory.memory_type.value,
                "importance": memory.importance,
                "event_type": memory.event_type,
            },
        )

    def recent_memories(self, agent_id: UUID | None = None, limit: int = 20) -> list[Memory]:
        """Return the most recent memory records in newest-first order."""
        return self.list_memories(agent_id=agent_id, limit=limit)

    def delete_memory(self, memory_id: UUID) -> None:
        """Remove one memory record from storage."""
        self._repository.delete(memory_id)

    def recall(self, agent_id: UUID, goal: str, limit: int = 5) -> list[Memory]:
        """Return the most relevant memories for ``goal`` in deterministic rank order."""
        memories = self.list_memories(agent_id=agent_id, limit=100)
        relevant = [memory for memory in memories if self._matches_goal(memory, goal)]
        relevant.sort(key=lambda memory: self._recall_score(memory, goal), reverse=True)
        return relevant[:limit]

    def set_working_memory(self, agent_id: UUID, *, current_goal: str, current_action: str, target: str, started_at: datetime) -> Memory:
        """Replace the agent's current working-memory snapshot with the latest state."""
        for existing in self.list_memories(agent_id=agent_id, limit=100):
            if existing.memory_type is MemoryType.WORKING:
                self.delete_memory(existing.id)

        recalled = self.recall(agent_id=agent_id, goal=current_goal)
        selected_memory = recalled[0] if recalled else None
        working_content = f"Current thought: {current_goal}/{current_action}"
        if selected_memory is not None:
            working_content = f"{working_content} | Selected memory: {selected_memory.content}"

        return self.record(
            CreateMemoryRequest(
                agent_id=agent_id,
                memory_type=MemoryType.WORKING,
                content=working_content,
                tick=None,
                timestamp=started_at,
                event_type="working_memory",
                description=f"Goal={current_goal}; Action={current_action}; Target={target}",
                location=target,
                result="working_memory_updated",
                importance=0.5,
                metadata={
                    "current_goal": current_goal,
                    "current_action": current_action,
                    "target": target,
                    "recalled_memories": [memory.content for memory in recalled],
                    "selected_memory": selected_memory.content if selected_memory is not None else None,
                },
            )
        )

    def upsert_semantic_knowledge(
        self,
        *,
        agent_id: UUID,
        subject: str,
        predicate: str,
        object_value: str,
        confidence: float,
        observed_at: datetime,
        source_episode_id: str | None = None,
        lesson: str | None = None,
    ) -> Memory:
        """Create or strengthen one semantic knowledge memory for an agent."""
        normalized = {
            "subject": subject.strip(),
            "predicate": predicate.strip(),
            "object": object_value.strip(),
        }
        key = self._knowledge_key(normalized["subject"], normalized["predicate"], normalized["object"])
        existing = self._find_existing_knowledge(agent_id, key)

        if existing is None:
            return self.record(
                CreateMemoryRequest(
                    agent_id=agent_id,
                    memory_type=MemoryType.SEMANTIC,
                    content=f"{normalized['subject']} {normalized['predicate']} {normalized['object']}",
                    timestamp=observed_at,
                    event_type="knowledge",
                    description=lesson,
                    importance=max(0.4, min(1.0, confidence)),
                    metadata={
                        "knowledge": normalized,
                        "knowledge_key": key,
                        "confidence": max(0.0, min(1.0, confidence)),
                        "times_observed": 1,
                        "first_observed": observed_at.isoformat(),
                        "last_observed": observed_at.isoformat(),
                        "source_episode_id": source_episode_id,
                    },
                )
            )

        previous_times = int(existing.metadata.get("times_observed", 1))
        previous_confidence = float(existing.metadata.get("confidence", existing.importance))
        next_times = previous_times + 1
        strengthened_confidence = min(1.0, max(previous_confidence, confidence) + 0.08)
        updated_memory = existing.model_copy(deep=True)
        updated_memory.timestamp = observed_at
        updated_memory.importance = max(updated_memory.importance, strengthened_confidence)
        updated_memory.description = lesson or updated_memory.description
        updated_memory.metadata = {
            **updated_memory.metadata,
            "knowledge": normalized,
            "knowledge_key": key,
            "confidence": strengthened_confidence,
            "times_observed": next_times,
            "first_observed": updated_memory.metadata.get("first_observed", observed_at.isoformat()),
            "last_observed": observed_at.isoformat(),
            "source_episode_id": source_episode_id or updated_memory.metadata.get("source_episode_id"),
        }
        return self._repository.update(updated_memory)

    @staticmethod
    def _matches_goal(memory: Memory, goal: str) -> bool:
        goal_value = goal.lower()
        if memory.event_type is not None and memory.event_type.lower() == goal_value:
            return True
        if memory.memory_type is MemoryType.SEMANTIC:
            knowledge = memory.metadata.get("knowledge", {})
            semantic_text = " ".join(
                [
                    str(knowledge.get("subject", "")),
                    str(knowledge.get("predicate", "")),
                    str(knowledge.get("object", "")),
                    str(memory.description or ""),
                ]
            ).lower()
            if goal_value in semantic_text:
                return True
            goal_hints: dict[str, tuple[str, ...]] = {
                "drink": ("water", "drinkable", "river", "well", "spring", "pond"),
                "eat": ("food", "edible", "kitchen", "shop", "market", "farm"),
                "sleep": ("rest", "bed", "home", "shelter"),
            }
            if any(hint in semantic_text for hint in goal_hints.get(goal_value, ())):
                return True
        description = (memory.description or "").lower()
        return goal_value in description or goal_value in (memory.content.lower())

    @staticmethod
    def _recall_score(memory: Memory, goal: str) -> tuple[int, float, datetime]:
        relevance = 2 if (memory.event_type or "").lower() == goal.lower() else 1 if goal.lower() in (memory.content.lower() + " " + (memory.description or "").lower()) else 0
        confidence = float(memory.metadata.get("confidence", memory.importance))
        if memory.memory_type is MemoryType.SEMANTIC:
            relevance += 1
        return (relevance, confidence, memory.timestamp or memory.created_at)

    def _find_existing_knowledge(self, agent_id: UUID, knowledge_key: str) -> Memory | None:
        for memory in self.list_memories(agent_id=agent_id, limit=500):
            if memory.memory_type is not MemoryType.SEMANTIC:
                continue
            if memory.metadata.get("knowledge_key") == knowledge_key:
                return memory
        return None

    @staticmethod
    def _knowledge_key(subject: str, predicate: str, object_value: str) -> str:
        return f"{subject.strip().lower()}|{predicate.strip().lower()}|{object_value.strip().lower()}"
