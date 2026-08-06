"""Framework-independent orchestration for simulation cycles."""

from datetime import timedelta
from threading import Event, RLock, Thread, current_thread
from typing import Protocol

from app.core.events import EventBus
from app.modules.world.clock import SimulationClock, SimulationTick


class AgentUpdater(Protocol):
    """Port used by the engine to update all agents for a completed tick."""

    def update_agents(self, tick: SimulationTick) -> None:
        """Update agent state for ``tick``."""


class SimulationEngine:
    """Coordinate clock, agent updates, and event publication in a managed loop."""

    def __init__(
        self,
        clock: SimulationClock,
        agent_updater: AgentUpdater,
        event_bus: EventBus,
        tick_interval: timedelta = timedelta(seconds=1),
    ) -> None:
        """Create an engine with injected world-time, update, and event collaborators."""
        if tick_interval <= timedelta(0):
            raise ValueError("tick_interval must be greater than zero.")

        self._clock = clock
        self._agent_updater = agent_updater
        self._event_bus = event_bus
        self._tick_interval = tick_interval
        self._loop_stop = Event()
        self._loop_thread: Thread | None = None
        self._lock = RLock()

    @property
    def is_running(self) -> bool:
        """Return whether the engine's background simulation loop is active."""
        with self._lock:
            return self._loop_thread is not None and self._loop_thread.is_alive()

    @property
    def tick_count(self) -> int:
        """Return the number of completed simulation ticks."""
        return self._clock.current_tick

    def step(self) -> SimulationTick | None:
        """Advance the world by one tick and return the resulting event."""
        return self.run_tick()

    def run_tick(self) -> SimulationTick | None:
        """Execute one simulation cycle and return its event, or ``None`` when paused."""
        tick = self._clock.tick()
        if tick is None:
            return None

        self._agent_updater.update_agents(tick)
        self._event_bus.publish(tick)
        return tick

    def start(self) -> None:
        """Start the background loop; repeated calls while active have no effect."""
        with self._lock:
            if self._loop_thread is not None and self._loop_thread.is_alive():
                return

            self._loop_stop.clear()
            self._loop_thread = Thread(target=self._run_loop, name="simulation-engine", daemon=True)
            self._loop_thread.start()

    def stop(self, timeout: float | None = None) -> None:
        """Request loop shutdown and wait up to ``timeout`` seconds for it to finish."""
        with self._lock:
            thread = self._loop_thread
            self._loop_stop.set()

        if thread is not None and thread is not current_thread():
            thread.join(timeout)

    def _run_loop(self) -> None:
        """Run simulation cycles until the loop stop signal is set."""
        try:
            while not self._loop_stop.is_set():
                self.run_tick()
                self._loop_stop.wait(self._tick_interval.total_seconds())
        finally:
            with self._lock:
                if self._loop_thread is current_thread():
                    self._loop_thread = None
