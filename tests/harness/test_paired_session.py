import asyncio
import queue
import threading

import pytest

from kiwi_client.live_capture import LiveCaptureError
from kiwi_client.live_play import LiveSndPlaybackConfig
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig
from kiwi_client.paired_session import PairedSessionCoordinator, pair_session_configs


class FakePrimary:
    def __init__(self, order, *, ready=True, error=None):
        self.order = order
        self.ready_result = ready
        self.error = error
        self.command_queue = queue.Queue()
        self.finished = False

    def start(self):
        self.order.append("snd-start")
        return True

    async def wait_ready(self):
        self.order.append("snd-wait-ready")
        return self.ready_result

    async def finish(self):
        self.order.append("snd-finish")
        self.finished = True


def test_pair_session_configs_assigns_one_timestamp_to_both_streams(tmp_path):
    wf, snd = pair_session_configs(
        LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "wf.jsonl", timestamp=None),
        LiveSndPlaybackConfig(timestamp=None),
        clock=lambda: 123456.9,
    )

    assert wf.timestamp == snd.timestamp == 123456
    assert wf.websocket_uri().endswith("/123456/W/F")
    assert snd.websocket_uri().endswith("/123456/SND")


def test_pair_session_configs_preserves_explicit_timestamp_and_rejects_mismatch(tmp_path):
    wf, snd = pair_session_configs(
        LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "wf.jsonl", timestamp=777),
        LiveSndPlaybackConfig(timestamp=None),
        clock=lambda: 123456.9,
    )
    assert wf.timestamp == snd.timestamp == 777

    with pytest.raises(ValueError, match="timestamp"):
        pair_session_configs(
            LiveWaterfallCaptureConfig(host="10.0.0.40", port=8073, output=tmp_path / "bad.jsonl", timestamp=1),
            LiveSndPlaybackConfig(timestamp=2),
        )


def test_coordinator_starts_primary_before_waterfall_and_stops_both():
    order = []
    primary = FakePrimary(order)
    coordinator = PairedSessionCoordinator(primary=primary)

    async def waterfall(stop_event, command_queue):
        order.append("wf-start")
        assert isinstance(stop_event, threading.Event)
        assert isinstance(command_queue, queue.Queue)
        return "wf-result"

    result = asyncio.run(coordinator.run(waterfall))

    assert result == "wf-result"
    assert order == ["snd-start", "snd-wait-ready", "wf-start", "snd-finish"]
    assert coordinator.stop_event.is_set()
    assert coordinator.snd_command_queue is primary.command_queue
    assert coordinator.snd_command_queue is not coordinator.waterfall_command_queue
    assert primary.finished is True


def test_coordinator_cancellation_stops_primary_and_shared_boundary():
    order = []
    primary = FakePrimary(order)
    coordinator = PairedSessionCoordinator(primary=primary)

    async def exercise():
        started = asyncio.Event()

        async def waterfall(*args):
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(coordinator.run(waterfall))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert coordinator.stop_event.is_set()
    assert primary.finished is True


def test_coordinator_does_not_start_waterfall_when_primary_fails_before_ready():
    order = []
    primary = FakePrimary(order, ready=False, error="SND refused")
    coordinator = PairedSessionCoordinator(primary=primary)

    async def waterfall(*args):
        order.append("wf-start")

    with pytest.raises(LiveCaptureError, match="SND refused"):
        asyncio.run(coordinator.run(waterfall))

    assert "wf-start" not in order
    assert primary.finished is True
    assert coordinator.stop_event.is_set()


def test_coordinator_stops_primary_when_waterfall_fails():
    order = []
    primary = FakePrimary(order)
    coordinator = PairedSessionCoordinator(primary=primary)

    async def waterfall(*args):
        order.append("wf-start")
        raise RuntimeError("W/F failed")

    with pytest.raises(RuntimeError, match="W/F failed"):
        asyncio.run(coordinator.run(waterfall))

    assert primary.finished is True
    assert coordinator.stop_event.is_set()


def test_post_ready_primary_error_does_not_implicitly_abort_waterfall():
    order = []
    primary = FakePrimary(order, error="audio ended")
    coordinator = PairedSessionCoordinator(primary=primary)

    async def waterfall(*args):
        order.append("wf-complete")
        return 42

    assert asyncio.run(coordinator.run(waterfall)) == 42
    assert "wf-complete" in order
