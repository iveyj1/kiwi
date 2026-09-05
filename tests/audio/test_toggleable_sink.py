from kiwi_client.playback import SwitchableAudioSink


class Sink:
    def __init__(self):
        self.started = []
        self.writes = []
        self.stopped = 0

    def start(self, **format):
        self.started.append(format)

    def write(self, pcm):
        self.writes.append(pcm)

    def stop(self):
        self.stopped += 1


def test_toggleable_sink_lazily_opens_mutes_and_reopens_device():
    sinks = []

    def factory():
        sink = Sink()
        sinks.append(sink)
        return sink

    gate = SwitchableAudioSink(factory, enabled=False)
    gate.start(sample_rate_hz=12000, channels=1, sample_width_bytes=2)
    gate.write(b"muted")
    assert sinks == []

    assert gate.set_enabled(True) is True
    gate.write(b"audible")
    assert sinks[0].started == [{"sample_rate_hz": 12000, "channels": 1, "sample_width_bytes": 2}]
    assert sinks[0].writes == [b"audible"]

    assert gate.set_enabled(False) is True
    gate.write(b"muted again")
    assert sinks[0].stopped == 1

    gate.set_enabled(True)
    gate.stop()
    assert len(sinks) == 2
    assert sinks[1].stopped == 1


def test_toggleable_sink_rejects_writes_before_stream_start():
    gate = SwitchableAudioSink(Sink, enabled=False)
    try:
        gate.write(b"data")
    except RuntimeError as exc:
        assert "started" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
