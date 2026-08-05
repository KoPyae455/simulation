"""Unit tests for the framework-independent simulation engine."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest

from app.core.events import InMemoryEventBus
from app.modules.world.clock import SimulationClock, SimulationTick
from app.modules.world.engine import SimulationEngine


@dataclass
class RecordingAgentUpdater:
    """Test double that records agent-update requests."""

    ticks: list[SimulationTick] = field(default_factory=list)

    def update_agents(self, tick: SimulationTick) -> None:
        """Record an agent-update request."""
        self.ticks.append(tick)


def test_run_tick_updates_agents_before_publishing_the_event() -> None:
    """A simulation cycle coordinates collaborators in deterministic order."""
    clock = SimulationClock(datetime(2040, 1, 1, tzinfo=UTC))
    updater = RecordingAgentUpdater()
    event_bus = InMemoryEventBus()
    published_events: list[SimulationTick] = []
    event_bus.subscribe(SimulationTick, published_events.append)
    engine = SimulationEngine(clock, updater, event_bus)

    event = engine.run_tick()

    assert event is not None
    assert updater.ticks == [event]
    assert published_events == [event]


def test_paused_clock_skips_agent_updates_and_event_publication() -> None:
    """The engine leaves collaborator state unchanged when world time is paused."""
    clock = SimulationClock(datetime(2040, 1, 1, tzinfo=UTC))
    updater = RecordingAgentUpdater()
    event_bus = InMemoryEventBus()
    published_events: list[SimulationTick] = []
    event_bus.subscribe(SimulationTick, published_events.append)
    engine = SimulationEngine(clock, updater, event_bus)
    clock.pause()

    assert engine.run_tick() is None
    assert updater.ticks == []
    assert published_events == []


def test_start_runs_a_background_simulation_loop() -> None:
    """The managed loop performs ticks until it receives a stop request."""
    clock = SimulationClock(datetime(2040, 1, 1, tzinfo=UTC))
    tick_received = Event()

    class SignallingUpdater:
        """Test updater that reports when the loop performs an update."""

        def update_agents(self, tick: SimulationTick) -> None:
            """Signal completion of an agent-update request."""
            tick_received.set()

    engine = SimulationEngine(
        clock,
        SignallingUpdater(),
        InMemoryEventBus(),
        tick_interval=timedelta(milliseconds=10),
    )
    engine.start()

    assert tick_received.wait(timeout=1)
    engine.stop(timeout=1)
    assert not engine.is_running


def test_invalid_loop_interval_is_rejected() -> None:
    """The loop interval must prevent a busy simulation loop."""
    clock = SimulationClock(datetime(2040, 1, 1, tzinfo=UTC))

    with pytest.raises(ValueError, match="tick_interval"):
        SimulationEngine(clock, RecordingAgentUpdater(), InMemoryEventBus(), timedelta(0))
