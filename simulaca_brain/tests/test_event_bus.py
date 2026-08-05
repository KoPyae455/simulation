"""Unit tests for the in-process event bus adapter."""

from dataclasses import dataclass
from threading import Thread

from app.core.events import InMemoryEventBus


@dataclass(frozen=True)
class WorldEvent:
    """Base event used to test polymorphic subscriptions."""

    identifier: int


@dataclass(frozen=True)
class TickCompleted(WorldEvent):
    """Concrete event used to test exact-type subscriptions."""


def test_event_is_delivered_to_multiple_matching_subscribers() -> None:
    """Exact and base-type handlers each receive a compatible event once."""
    event_bus = InMemoryEventBus()
    received_by_base: list[WorldEvent] = []
    received_by_tick: list[TickCompleted] = []
    event_bus.subscribe(WorldEvent, received_by_base.append)
    event_bus.subscribe(TickCompleted, received_by_tick.append)
    event = TickCompleted(identifier=1)

    event_bus.publish(event)

    assert received_by_base == [event]
    assert received_by_tick == [event]


def test_unsubscribe_stops_only_the_target_handler() -> None:
    """A subscription handle safely removes one handler without affecting others."""
    event_bus = InMemoryEventBus()
    first: list[TickCompleted] = []
    second: list[TickCompleted] = []
    subscription = event_bus.subscribe(TickCompleted, first.append)
    event_bus.subscribe(TickCompleted, second.append)

    assert event_bus.unsubscribe(subscription)
    assert not event_bus.unsubscribe(subscription)
    event_bus.publish(TickCompleted(identifier=1))

    assert first == []
    assert len(second) == 1


def test_subscriptions_can_change_while_handlers_are_running() -> None:
    """Publishing uses a stable snapshot rather than iterating mutable subscriptions."""
    event_bus = InMemoryEventBus()
    received: list[TickCompleted] = []

    def subscribe_during_dispatch(event: TickCompleted) -> None:
        """Register an additional handler during the first event dispatch."""
        event_bus.subscribe(TickCompleted, received.append)

    event_bus.subscribe(TickCompleted, subscribe_during_dispatch)
    event_bus.publish(TickCompleted(identifier=1))
    event_bus.publish(TickCompleted(identifier=2))

    assert [event.identifier for event in received] == [2]


def test_concurrent_subscriptions_are_safe() -> None:
    """Threaded callers can register handlers without losing subscriptions."""
    event_bus = InMemoryEventBus()
    received: list[int] = []
    threads = [
        Thread(target=lambda: event_bus.subscribe(TickCompleted, lambda event: received.append(event.identifier)))
        for _ in range(20)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    event_bus.publish(TickCompleted(identifier=7))

    assert received == [7] * 20
