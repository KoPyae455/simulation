"""Unit tests for framework-independent world timekeeping."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.world.clock import SimulationClock


def test_tick_advances_world_time_and_notifies_subscribers() -> None:
    """A completed tick advances state and sends one immutable event to each listener."""
    start = datetime(2040, 1, 1, tzinfo=UTC)
    received = []
    clock = SimulationClock(start, tick_duration=timedelta(minutes=10), speed=2.0)
    clock.subscribe(received.append)

    event = clock.tick()

    assert event is not None
    assert event.number == 1
    assert event.simulation_datetime == start + timedelta(minutes=20)
    assert clock.current_tick == 1
    assert clock.current_datetime == event.simulation_datetime
    assert received == [event]


def test_paused_clock_does_not_advance_or_notify() -> None:
    """Pausing suppresses both state changes and tick notifications until resumed."""
    clock = SimulationClock(datetime(2040, 1, 1, tzinfo=UTC))
    received = []
    clock.subscribe(received.append)
    clock.pause()

    assert clock.tick() is None
    assert clock.current_tick == 0
    assert received == []

    clock.resume()
    assert clock.tick() is not None
    assert clock.current_tick == 1
    assert len(received) == 1


def test_speed_and_subscriptions_can_be_updated() -> None:
    """Future ticks use the current speed and only active listeners receive events."""
    start = datetime(2040, 1, 1, tzinfo=UTC)
    clock = SimulationClock(start, tick_duration=timedelta(hours=1))
    received = []
    subscription_id = clock.subscribe(received.append)
    clock.set_speed(0.5)

    event = clock.tick()

    assert event is not None
    assert event.simulation_datetime == start + timedelta(minutes=30)
    assert clock.unsubscribe(subscription_id)
    assert not clock.unsubscribe(subscription_id)
    clock.tick()
    assert len(received) == 1


@pytest.mark.parametrize("speed", [0, -1, float("inf"), float("nan")])
def test_invalid_speed_is_rejected(speed: float) -> None:
    """Clock speed must always permit forward progress through world time."""
    with pytest.raises(ValueError, match="speed"):
        SimulationClock(datetime(2040, 1, 1, tzinfo=UTC), speed=speed)
