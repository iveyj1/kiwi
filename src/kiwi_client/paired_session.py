"""UI-neutral ownership for paired Kiwi primary SND and W/F sessions."""

from __future__ import annotations

import queue
import time
from dataclasses import replace
from threading import Event
from typing import Awaitable, Callable, Protocol, TypeVar

from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig


class PrimarySession(Protocol):
    """Minimal primary-stream lifecycle required by the paired coordinator."""

    command_queue: queue.Queue[str]
    error: str | None

    def start(self) -> bool:
        """Start the primary SND task."""

    async def wait_ready(self) -> bool:
        """Wait until SND is open/authenticated or has failed."""

    async def finish(self) -> None:
        """Stop and join the primary SND task."""


def pair_session_configs(
    waterfall: LiveWaterfallCaptureConfig,
    snd: LiveSndPlaybackConfig,
    *,
    clock: Callable[[], float] = time.time,
) -> tuple[LiveWaterfallCaptureConfig, LiveSndPlaybackConfig]:
    """Return paired configs carrying one resolved Kiwi session timestamp."""
    if waterfall.timestamp is not None and snd.timestamp is not None and waterfall.timestamp != snd.timestamp:
        raise ValueError("paired SND and W/F timestamps must match")
    timestamp = waterfall.timestamp
    if timestamp is None:
        timestamp = snd.timestamp
    if timestamp is None:
        timestamp = int(clock())
    return replace(waterfall, timestamp=timestamp), replace(snd, timestamp=timestamp)


ResultT = TypeVar("ResultT")
WaterfallRunner = Callable[[Event, queue.Queue[str]], Awaitable[ResultT]]


class PairedSessionCoordinator:
    """Start primary SND before W/F and own their shared stop boundary."""

    def __init__(
        self,
        *,
        primary: PrimarySession | None,
        stop_event: Event | None = None,
        waterfall_command_queue: queue.Queue[str] | None = None,
    ) -> None:
        self.primary = primary
        self.stop_event = stop_event or Event()
        self.waterfall_command_queue = waterfall_command_queue or queue.Queue()

    @property
    def snd_command_queue(self) -> queue.Queue[str] | None:
        return None if self.primary is None else self.primary.command_queue

    async def run(self, waterfall_runner: WaterfallRunner[ResultT]) -> ResultT:
        """Run W/F only after primary readiness and always stop the pair."""
        try:
            if self.primary is not None:
                self.primary.start()
                if not await self.primary.wait_ready():
                    error = self.primary.error or "SND session ended before becoming ready"
                    raise LiveCaptureError(f"audio session failed before W/F startup: {error}")
            return await waterfall_runner(self.stop_event, self.waterfall_command_queue)
        finally:
            self.stop_event.set()
            if self.primary is not None:
                await self.primary.finish()
