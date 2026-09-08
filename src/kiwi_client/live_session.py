"""Headless paired SND/W/F operation for controller and TUI use."""

from __future__ import annotations

import asyncio
import queue
from dataclasses import asdict, dataclass, replace
from threading import Event
from typing import Any, Callable

from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig, play_live_snd
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig, capture_live_waterfall
from kiwi_client.paired_session import PairedSessionCoordinator, pair_session_configs
from kiwi_client.playback import AudioSink
from kiwi_client.session_bootstrap import KiwiBootstrapError, resolve_connection_timestamp
from kiwi_client.waterfall import WaterfallFrame


@dataclass(frozen=True)
class RoutedSessionCommand:
    stream: str
    command: str

    def __post_init__(self) -> None:
        if self.stream not in ("snd", "wf"):
            raise ValueError("session command stream must be 'snd' or 'wf'")


class PrimarySndSession:
    """UI-neutral primary SND task with readiness and error status."""

    def __init__(
        self,
        config,
        sink,
        *,
        runner=play_live_snd,
        status_callback=None,
        finish_timeout_seconds: float = 1.0,
    ):
        self.config = config
        self.sink = sink
        self.runner = runner
        self.status_callback = status_callback
        self.finish_timeout_seconds = finish_timeout_seconds
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.stop_event: Event | None = None
        self.task: asyncio.Task | None = None
        self.ready = asyncio.Event()
        self.error: str | None = None
        self.result = None

    def start(self) -> bool:
        if self.task is not None and not self.task.done():
            return False
        self.stop_event = Event()
        self.task = asyncio.create_task(self._run())
        return True

    async def _run(self) -> None:
        def ready():
            self.ready.set()
            if self.status_callback:
                self.status_callback({"snd_status": "running"})

        try:
            self.result = await self.runner(
                self.config,
                self.sink,
                allow_live=True,
                stop_event=self.stop_event,
                command_queue=self.command_queue,
                status_callback=self.status_callback,
                session_ready_callback=ready,
            )
        except Exception as exc:
            self.error = str(exc)
            if self.status_callback:
                self.status_callback({"snd_status": "failed", "snd_error": self.error})

    async def wait_ready(self) -> bool:
        if self.task is None:
            return False
        ready_task = asyncio.create_task(self.ready.wait())
        done, _ = await asyncio.wait((ready_task, self.task), return_when=asyncio.FIRST_COMPLETED)
        if ready_task in done and ready_task.result():
            return True
        ready_task.cancel()
        await asyncio.gather(ready_task, return_exceptions=True)
        return False

    async def finish(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
        if self.task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(self.task), timeout=self.finish_timeout_seconds)
        except asyncio.TimeoutError:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


async def run_live_paired_session(
    waterfall_config: LiveWaterfallCaptureConfig,
    snd_config: LiveSndPlaybackConfig,
    sink: AudioSink,
    *,
    allow_live: bool,
    stop_event: Event,
    command_queue: queue.Queue,
    status_callback: Callable[[dict], None] | None = None,
    frame_callback: Callable[[WaterfallFrame], None] | None = None,
    snd_runner=play_live_snd,
    waterfall_runner=capture_live_waterfall,
    timestamp_resolver=resolve_connection_timestamp,
) -> dict[str, Any]:
    """Run one headless paired session and route controller commands by stream."""
    if waterfall_config.timestamp is None and snd_config.timestamp is None:
        try:
            timestamp = await timestamp_resolver(snd_config.host, snd_config.port)
        except KiwiBootstrapError as exc:
            raise LiveCaptureError(str(exc)) from exc
        waterfall_config = replace(waterfall_config, timestamp=timestamp)
        snd_config = replace(snd_config, timestamp=timestamp)
    waterfall_config, snd_config = pair_session_configs(waterfall_config, snd_config)
    primary = PrimarySndSession(
        snd_config,
        sink,
        runner=snd_runner,
        status_callback=status_callback,
    )
    coordinator = PairedSessionCoordinator(primary=primary, stop_event=stop_event)

    async def route_commands():
        while not stop_event.is_set():
            try:
                item = command_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
            if isinstance(item, RoutedSessionCommand):
                target = primary.command_queue if item.stream == "snd" else coordinator.waterfall_command_queue
                target.put(item.command)
            else:
                primary.command_queue.put(str(item))

    def publish_waterfall_metrics(metrics: dict) -> None:
        if status_callback is None:
            return
        renamed = {
            "sequence_gaps": "wf_sequence_gaps",
            "out_of_order": "wf_out_of_order",
        }
        filtered = {
            renamed.get(key, key): value
            for key, value in metrics.items()
            if key != "ascii_row"
        }
        status_callback(filtered)

    async def run_waterfall(paired_stop, wf_commands):
        router = asyncio.create_task(route_commands())
        publish_waterfall_metrics({"wf_status": "running"})
        try:
            return await waterfall_runner(
                waterfall_config,
                allow_live=allow_live,
                stop_event=paired_stop,
                status_callback=publish_waterfall_metrics,
                frame_callback=frame_callback,
                command_queue=wf_commands,
                save_events=False,
            )
        except Exception as exc:
            publish_waterfall_metrics({"wf_status": "failed", "wf_error": str(exc)})
            raise
        finally:
            router.cancel()
            await asyncio.gather(router, return_exceptions=True)

    path = await coordinator.run(run_waterfall)
    return {
        "waterfall": str(path),
        "snd": None if primary.result is None else {**asdict(primary.result), "path": str(primary.result.path)},
        "snd_error": primary.error,
    }
