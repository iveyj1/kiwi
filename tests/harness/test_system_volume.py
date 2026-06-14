from kiwi_client.system_volume import SystemVolumeControl


def test_system_volume_parses_backend_outputs():
    assert SystemVolumeControl._parse_percent("Volume: 0.10") == 10
    assert SystemVolumeControl._parse_percent("Volume: 1.25") == 125
    assert SystemVolumeControl._parse_percent("front-left: 65536 / 100% / 0.00 dB") == 100
    assert SystemVolumeControl._parse_percent("Mono: Playback 12 [12%] [-52.50dB]") == 12


def test_system_volume_prefers_wpctl_when_available(monkeypatch):
    def fake_which(name):
        return f"/usr/bin/{name}" if name == "wpctl" else None

    monkeypatch.setattr("shutil.which", fake_which)

    assert SystemVolumeControl._command(55) == ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "55%"]


def test_system_volume_falls_back_to_pactl(monkeypatch):
    def fake_which(name):
        return f"/usr/bin/{name}" if name == "pactl" else None

    monkeypatch.setattr("shutil.which", fake_which)

    assert SystemVolumeControl._command(55) == ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "55%"]


def test_system_volume_falls_back_to_amixer(monkeypatch):
    def fake_which(name):
        return f"/usr/bin/{name}" if name == "amixer" else None

    monkeypatch.setattr("shutil.which", fake_which)

    assert SystemVolumeControl._command(55) == ["amixer", "sset", "Master", "55%"]


def test_system_volume_reports_missing_backend(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert SystemVolumeControl._command(55) is None
