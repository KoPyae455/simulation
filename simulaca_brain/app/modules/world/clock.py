"""Framework-independent timekeeping for the simulated world."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from threading import RLock


@dataclass(frozen=True, slots=True)
class SimulationTick:
    """An immutable record of one completed simulation tick."""

    number: int
    simulation_datetime: datetime


TickListener = Callable[[SimulationTick], None]


class SimulationClock:
    """Advance world time deterministically and publish completed ticks to listeners."""

    def __init__(
        self,
        start_datetime: datetime,
        tick_duration: timedelta = timedelta(minutes=1),
        speed: float = 1.0,
    ) -> None:
        """Create a clock beginning at ``start_datetime`` with the supplied tick settings."""
        if start_datetime.tzinfo is None or start_datetime.utcoffset() is None:
            raise ValueError("start_datetime must be timezone-aware.")
        if tick_duration <= timedelta(0):
            raise ValueError("tick_duration must be greater than zero.")

        self._validate_speed(speed)
        self._current_tick = 0
        self._current_datetime = start_datetime
        self._tick_duration = tick_duration
        self._speed = speed
        self._is_paused = False
        self._listeners: dict[int, TickListener] = {}
        self._next_subscription_id = 1
        self._lock = RLock()

    @property
    def current_tick(self) -> int:
        """Return the number of completed simulation ticks."""
        with self._lock:
            return self._current_tick

    @property
    def current_datetime(self) -> datetime:
        """Return the current datetime in simulated world time."""
        with self._lock:
            return self._current_datetime

    @property
    def speed(self) -> float:
        """Return the simulation-time multiplier applied to each tick."""
        with self._lock:
            return self._speed

    @property
    def is_paused(self) -> bool:
        """Return whether calls to ``tick`` currently leave time unchanged."""
        with self._lock:
            return self._is_paused

    def set_speed(self, speed: float) -> None:
        """Set a positive, finite multiplier for future simulation ticks."""
        self._validate_speed(speed)
        with self._lock:
            self._speed = speed

    def pause(self) -> None:
        """Pause simulation-time advancement and tick publication."""
        with self._lock:
            self._is_paused = True

    def resume(self) -> None:
        """Resume simulation-time advancement and tick publication."""
        with self._lock:
            self._is_paused = False

    def subscribe(self, listener: TickListener) -> int:
        """Register a listener and return its subscription identifier."""
        with self._lock:
            subscription_id = self._next_subscription_id
            self._next_subscription_id += 1
            self._listeners[subscription_id] = listener
            return subscription_id

    def unsubscribe(self, subscription_id: int) -> bool:
        """Remove a listener, returning whether an active subscription was removed."""
        with self._lock:
            return self._listeners.pop(subscription_id, None) is not None

    def tick(self) -> SimulationTick | None:
        """Advance one tick, notify listeners, and return its event; return ``None`` if paused."""
        with self._lock:
            if self._is_paused:
                return None

            self._current_tick += 1
            self._current_datetime += self._tick_duration * self._speed
            event = SimulationTick(self._current_tick, self._current_datetime)
            listeners = tuple(self._listeners.values())

        for listener in listeners:
            listener(event)
        return event

    @staticmethod
    def _validate_speed(speed: float) -> None:
        """Reject speed values that cannot produce meaningful simulation progression."""
        if not isfinite(speed) or speed <= 0:
            raise ValueError("speed must be a positive, finite number.")
