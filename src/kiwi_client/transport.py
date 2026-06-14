"""Transport abstractions and offline replay transport.

No live network transport is implemented here yet. The replay transport is a
harness tool for validating command/response order against fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass

from kiwi_client.fixtures import FixtureEvent


class ReplayTransportError(AssertionError):
    """Raised when fixture replay order or content does not match expectations."""


@dataclass(frozen=True)
class ReplayReceived:
    """One received fixture event from a replay transport."""

    stream: str
    type: str
    text: str | None = None
    payload: bytes | None = None


class ReplayTransport:
    """Replay tx/rx fixture events in strict chronological order.

    `send()` must match the next `tx`/`cmd` event. `receive()` returns the next
    `rx` event. This is intentionally small and deterministic so protocol and
    capture code can be tested without a receiver.
    """

    def __init__(self, events: list[FixtureEvent]):
        self._events = events
        self._index = 0

    @property
    def done(self) -> bool:
        """Return true when all fixture events have been consumed."""
        return self._index >= len(self._events)

    def send(self, text: str) -> None:
        """Validate that the next fixture event is this transmitted command."""
        event = self._next_event()
        if event.dir != "tx" or event.type != "cmd":
            raise ReplayTransportError(f"expected tx cmd event, got {event.dir}/{event.type}")
        expected = event.raw.get("text")
        if text != expected:
            raise ReplayTransportError(f"sent command mismatch: expected {expected!r}, got {text!r}")

    def receive(self) -> ReplayReceived:
        """Return the next received fixture event."""
        event = self._next_event()
        if event.dir != "rx":
            raise ReplayTransportError(f"expected rx event, got {event.dir}/{event.type}")
        if event.type == "msg":
            return ReplayReceived(stream=event.stream, type=event.type, text=str(event.raw["text"]))
        if event.type == "binary":
            return ReplayReceived(stream=event.stream, type=event.type, payload=event.binary_payload)
        raise ReplayTransportError(f"unsupported rx event type: {event.type!r}")

    def _next_event(self) -> FixtureEvent:
        if self.done:
            raise ReplayTransportError("fixture replay exhausted")
        event = self._events[self._index]
        self._index += 1
        return event
