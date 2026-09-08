import asyncio
import queue
import threading
from pathlib import Path

from kiwi_client.live_play import LiveSndPlaybackConfig
from kiwi_client.live_session import PrimarySndSession, RoutedSessionCommand, run_live_paired_session
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig
from kiwi_client.playback import NullAudioSink, PlaybackResult
from kiwi_client.waterfall import WaterfallFrame


def test_primary_snd_finish_cancels_runner_that_ignores_cooperative_stop():
    async def stuck_runner(config, sink, **kwargs):
        kwargs["session_ready_callback"]()
        await asyncio.Event().wait()

    async def exercise():
        primary = PrimarySndSession(
            LiveSndPlaybackConfig(timestamp=123),
            NullAudioSink(),
            runner=stuck_runner,
            finish_timeout_seconds=0.01,
        )
        primary.start()
        assert await primary.wait_ready()
        await asyncio.wait_for(primary.finish(), timeout=0.2)
        assert primary.task.cancelled()

    asyncio.run(exercise())


def test_headless_paired_session_routes_commands_and_publishes_status(tmp_path):
    order = []
    snd_commands = []
    wf_commands = []
    statuses = []
    frames = []
    external_commands = queue.Queue()
    stop_event = threading.Event()

    async def snd_runner(config, sink, **kwargs):
        order.append("snd")
        kwargs["session_ready_callback"]()
        while not kwargs["stop_event"].is_set():
            try:
                snd_commands.append(kwargs["command_queue"].get_nowait())
            except queue.Empty:
                await asyncio.sleep(0.005)
        return PlaybackResult(Path("<snd>"), 12000, 1, 2, 0, 0, 0, True)

    async def wf_runner(config, **kwargs):
        order.append("wf")
        kwargs["status_callback"]({"wf_frames": 3, "sequence_gaps": 1, "ascii_row": "large"})
        kwargs["frame_callback"](WaterfallFrame(sequence=1, bins=(0,), dbm=(-100,)))
        while not kwargs["stop_event"].is_set():
            try:
                wf_commands.append(kwargs["command_queue"].get_nowait())
            except queue.Empty:
                await asyncio.sleep(0.005)
        return config.output

    resolved = []

    async def resolve_timestamp(host, port):
        resolved.append((host, port))
        return 4611686286989819482

    async def exercise():
        task = asyncio.create_task(
            run_live_paired_session(
                LiveWaterfallCaptureConfig("10.0.0.40", 8073, tmp_path / "wf.jsonl"),
                LiveSndPlaybackConfig(),
                NullAudioSink(),
                allow_live=True,
                stop_event=stop_event,
                command_queue=external_commands,
                status_callback=statuses.append,
                frame_callback=frames.append,
                snd_runner=snd_runner,
                waterfall_runner=wf_runner,
                timestamp_resolver=resolve_timestamp,
            )
        )
        while order != ["snd", "wf"]:
            await asyncio.sleep(0.005)
        external_commands.put("SET mod=am low_cut=-5000 high_cut=5000 freq=6000.000")
        external_commands.put(RoutedSessionCommand("wf", "SET zoom=8 cf=6000.000"))
        while not snd_commands or not wf_commands:
            await asyncio.sleep(0.005)
        stop_event.set()
        return await task

    result = asyncio.run(exercise())

    assert order == ["snd", "wf"]
    assert resolved == [("10.0.0.40", 8073)]
    assert snd_commands == ["SET mod=am low_cut=-5000 high_cut=5000 freq=6000.000"]
    assert wf_commands == ["SET zoom=8 cf=6000.000"]
    assert {status.get("snd_status") for status in statuses} >= {"running"}
    assert {status.get("wf_status") for status in statuses} >= {"running"}
    assert any(status.get("wf_frames") == 3 and status.get("wf_sequence_gaps") == 1 for status in statuses)
    assert all("ascii_row" not in status for status in statuses)
    assert [frame.sequence for frame in frames] == [1]
    assert result["waterfall"].endswith("wf.jsonl")
    assert result["snd_error"] is None
