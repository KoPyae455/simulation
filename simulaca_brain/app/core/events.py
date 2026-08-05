"""Contracts and in-process implementation for decoupled domain events."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any, Protocol, TypeVar, cast


EventT = TypeVar("EventT")
EventHandler = Callable[[EventT], None]


@dataclass(frozen=True, slots=True)
class EventSubscription:
    """Opaque handle returned when a handler is registered with an event bus."""

    identifier: int


class EventBus(Protocol):
    """Port for dispatching events without coupling their producers to consumers."""

    def publish(self, event: object) -> None:
        """Deliver ``event`` to every handler subscribed to its type."""

    def subscribe(self, event_type: type[EventT], handler: EventHandler[EventT]) -> EventSubscription:
        """Register ``handler`` for instances of ``event_type``."""

    def unsubscribe(self, subscription: EventSubscription) -> bool:
        """Remove a previously registered handler if it is still active."""


class InMemoryEventBus:
    """Thread-safe synchronous event bus suitable for a single-process runtime."""

    def __init__(self) -> None:
        """Create an empty event bus."""
        self._subscriptions: dict[int, tuple[type[object], EventHandler[Any]]] = {}
        self._next_identifier = 1
        self._lock = RLock()

    def publish(self, event: object) -> None:
        """Synchronously deliver an event to matching handlers in subscription order."""
        with self._lock:
            handlers = tuple(
                handler
                for event_type, handler in self._subscriptions.values()
                if isinstance(event, event_type)
            )

        for handler in handlers:
            handler(event)

    def subscribe(self, event_type: type[EventT], handler: EventHandler[EventT]) -> EventSubscription:
        """Register a handler and return a handle that can later unsubscribe it."""
        with self._lock:
            subscription = EventSubscription(self._next_identifier)
            self._next_identifier += 1
            self._subscriptions[subscription.identifier] = (event_type, cast(EventHandler[Any], handler))
            return subscription

    def unsubscribe(self, subscription: EventSubscription) -> bool:
        """Remove a subscription without failing when it was already removed."""
        with self._lock:
            return self._subscriptions.pop(subscription.identifier, None) is not None
