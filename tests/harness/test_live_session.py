import asyncio
import queue
import threading
from pathlib import Path

from kiwi_client.live_play import LiveSndPlaybackConfig
from kiwi_client.live_session import RoutedSessionCommand, run_live_paired_session
from kiwi_client.live_waterfall import LiveWaterfallCaptureConfig
from kiwi_client.playback import NullAudioSink, PlaybackResult
from kiwi_client.waterfall import WaterfallFrame


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
    assert snd_commands == ["SET mod=am low_cut=-5000 high_cut=5000 freq=6000.000"]
    assert wf_commands == ["SET zoom=8 cf=6000.000"]
    assert {status.get("snd_status") for status in statuses} >= {"running"}
    assert {status.get("wf_status") for status in statuses} >= {"running"}
    assert any(status.get("wf_frames") == 3 and status.get("wf_sequence_gaps") == 1 for status in statuses)
    assert all("ascii_row" not in status for status in statuses)
    assert [frame.sequence for frame in frames] == [1]
    assert result["waterfall"].endswith("wf.jsonl")
    assert result["snd_error"] is None
