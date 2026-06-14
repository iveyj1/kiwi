import json
import time
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientCommandError, ClientController, run_script, main


class FakeOperations:
    def __init__(self):
        self.calls = []

    def play(self, config, *, null_sink: bool, stop_event=None, command_queue=None, status_callback=None):
        self.calls.append(("play", config, null_sink, stop_event, command_queue, status_callback))
        commands = []
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if command_queue is not None:
                    try:
                        commands.append(command_queue.get(timeout=0.02))
                    except Exception:
                        pass
                if stop_event.is_set() and (command_queue is None or command_queue.empty()):
                    break
                time.sleep(0.01)
        if status_callback is not None:
            status_callback({"smeter": 850, "rssi_db": -42.0, "snd_frames": 1})
        return {"frames": 1024, "dry_run": null_sink, "stopped": bool(stop_event and stop_event.is_set()), "commands": commands}

    def record(self, config, *, stop_event=None, status_callback=None):
        self.calls.append(("record", config, stop_event, status_callback))
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        if status_callback is not None:
            status_callback({"smeter": 760, "rssi_db": -51.0, "snd_frames": 2})
        return {"path": str(config.output), "frames": 2048, "stopped": bool(stop_event and stop_event.is_set())}

    def capture(self, config, *, stop_event=None, status_callback=None):
        self.calls.append(("capture", config, stop_event, status_callback))
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        if status_callback is not None:
            status_callback({"smeter": 770, "rssi_db": -50.0, "snd_frames": 3})
        return {"path": str(config.output), "stopped": bool(stop_event and stop_event.is_set())}


def test_client_controller_status_and_state_changes():
    controller = ClientController()

    controller.execute("receiver 10.0.0.41:8073")
    controller.execute("tune 10000")
    controller.execute("mode usb 300 2700")
    response = controller.execute("status")

    state = response["state"]
    assert state["receiver"] == "10.0.0.41:8073"
    assert state["frequency_khz"] == 10000.0
    assert state["mode"] == "usb"
    assert state["low_cut_hz"] == 300
    assert state["high_cut_hz"] == 2700


def test_client_command_aliases_update_state_and_status():
    controller = ClientController()

    controller.execute("re 10.0.0.41:8073")
    controller.execute("tu 10000")
    controller.execute("mo usb 300 2700")
    controller.execute("fi 100 2400")
    controller.execute("du 45")
    controller.execute("fr 1200")
    response = controller.execute("?")

    state = response["state"]
    assert response["type"] == "status"
    assert state["receiver"] == "10.0.0.41:8073"
    assert state["frequency_khz"] == 10000.0
    assert state["mode"] == "usb"
    assert state["low_cut_hz"] == 100
    assert state["high_cut_hz"] == 2400
    assert state["duration_seconds"] == 45.0
    assert state["max_frames"] == 1200


def test_client_operation_aliases_with_injected_operations():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    started = controller.execute("pb --allow-live --null-sink")
    assert started["operation"]["running"] is True
    stopped = controller.execute("sp")
    assert stopped["operation"]["stop_requested"] is True
    controller.execute("wait 2")

    record_started = controller.execute("rb recordings/alias.wav --allow-live --overwrite")
    assert record_started["operation"]["running"] is True
    controller.execute("sp")
    controller.execute("wait 2")

    capture_started = controller.execute("cb tests/fixtures/kiwi/alias.jsonl --allow-live --overwrite")
    assert capture_started["operation"]["running"] is True
    controller.execute("sp")
    controller.execute("wait 2")

    assert controller.execute("he")["type"] == "help"
    assert controller.execute("qu")["type"] == "quit"


def test_client_controller_connect_disconnect_state_only():
    controller = ClientController()

    assert controller.execute("connect")["state"]["connected"] is True
    assert controller.execute("disconnect")["state"]["connected"] is False


def test_client_agc_commands_update_state_and_encode_command():
    controller = ClientController()

    assert controller.execute("agc off")["agc_command"] == "SET agc=0 hang=0 thresh=-100 slope=6 decay=1000 manGain=50"
    assert controller.execute("agc hang on")["agc_command"] == "SET agc=0 hang=1 thresh=-100 slope=6 decay=1000 manGain=50"
    assert controller.execute("agc threshold -90")["agc_command"] == "SET agc=0 hang=1 thresh=-90 slope=6 decay=1000 manGain=50"
    assert controller.execute("agc slope 4")["agc_command"] == "SET agc=0 hang=1 thresh=-90 slope=4 decay=1000 manGain=50"
    assert controller.execute("agc decay 500")["agc_command"] == "SET agc=0 hang=1 thresh=-90 slope=4 decay=500 manGain=50"
    assert controller.execute("agc gain 42")["agc_command"] == "SET agc=0 hang=1 thresh=-90 slope=4 decay=500 manGain=42"

    response = controller.execute("agc set on=true hang=false thresh=-95 slope=5 decay=750 gain=33")
    assert response["agc_command"] == "SET agc=1 hang=0 thresh=-95 slope=5 decay=750 manGain=33"
    assert response["state"]["agc_on"] is True
    assert response["state"]["agc_gain"] == 33


def test_client_agc_alias_and_query():
    controller = ClientController()

    response = controller.execute("ag")

    assert response["type"] == "state"
    assert response["agc_command"] == "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50"


def test_client_tune_step_and_volume_commands():
    controller = ClientController()

    assert controller.execute("tune-step +medium")["state"]["frequency_khz"] == pytest.approx(5001.0)
    assert controller.execute("tune-step -small")["state"]["frequency_khz"] == pytest.approx(5000.9)
    assert controller.execute("tune-step +5000")["state"]["frequency_khz"] == pytest.approx(5005.9)
    assert controller.execute("volume 55")["state"]["volume_percent"] == 55
    assert controller.execute("volume-step 10")["state"]["volume_percent"] == 65
    assert controller.execute("volume-step -1000")["state"]["volume_percent"] == 0
    assert controller.execute("volume 1000")["state"]["volume_percent"] == 200


def test_client_plans_reuse_current_state():
    controller = ClientController()
    controller.execute("tune 5000")
    controller.execute("mode am -5000 5000")
    controller.execute("duration 45")
    controller.execute("frames 1200")

    play = controller.execute("play-plan")["plan"]
    record = controller.execute("record-plan recordings/test.wav")["plan"]
    capture = controller.execute("capture-plan tests/fixtures/kiwi/test.jsonl")["plan"]

    for plan in (play, record, capture):
        assert plan["frequency_khz"] == 5000.0
        assert plan["mode"] == "am"
        assert plan["low_cut_hz"] == -5000
        assert plan["high_cut_hz"] == 5000
        assert plan["duration_seconds"] == 45.0
        assert plan["max_frames"] == 1200
        assert "SET mod=am low_cut=-5000 high_cut=5000 freq=5000.000" in plan["dynamic_commands"]
    assert record["output"] == "recordings/test.wav"
    assert capture["output"] == "tests/fixtures/kiwi/test.jsonl"


def test_run_script_stops_at_quit():
    responses = run_script([
        "status",
        "quit",
        "tune 7000",
    ])

    assert [response["type"] for response in responses] == ["status", "quit"]


def test_client_executes_play_record_capture_with_injected_operations():
    operations = FakeOperations()
    controller = ClientController(operations=operations)
    controller.execute("tune 5000")
    controller.execute("mode am -5000 5000")

    play = controller.execute("play --allow-live --null-sink")
    record = controller.execute("record recordings/shell.wav --allow-live --overwrite")
    capture = controller.execute("capture tests/fixtures/kiwi/shell.jsonl --allow-live --overwrite")

    assert play == {"type": "play", "result": {"frames": 1024, "dry_run": True, "stopped": False, "commands": []}}
    assert record["result"]["path"] == "recordings/shell.wav"
    assert capture["result"]["path"] == "tests/fixtures/kiwi/shell.jsonl"
    assert operations.calls[0][0] == "play"
    assert operations.calls[0][1].frequency_khz == 5000.0
    assert operations.calls[0][1].low_cut_hz == -5000
    assert operations.calls[0][1].duration_seconds == 60.0
    assert operations.calls[0][1].max_frames == 1500
    assert operations.calls[1][1].overwrite is True
    assert operations.calls[2][1].overwrite is True


def test_client_play_bg_and_stop_with_injected_operations():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    started = controller.execute("play-bg --allow-live --null-sink")
    assert started["operation"]["running"] is True

    stopped = controller.execute("stop")
    assert stopped["operation"]["stop_requested"] is True
    final = controller.background.join(timeout=2.0)

    assert final.running is False
    assert final.result["stopped"] is True
    assert controller.execute("operation-status")["operation"]["running"] is False


def test_client_wait_joins_background_operation():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    controller.execute("play-bg --allow-live --null-sink")
    controller.execute("stop")
    waited = controller.execute("wait 2")

    assert waited["operation"]["running"] is False
    assert waited["operation"]["result"]["stopped"] is True


def test_tune_mode_filter_queue_commands_to_active_background_playback():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    controller.execute("play-bg --allow-live --null-sink")
    tuned = controller.execute("tune 7000")
    mode = controller.execute("mode usb 300 2700")
    filt = controller.execute("filter 100 2400")
    controller.execute("stop")
    final = controller.background.join(timeout=2.0)

    assert tuned["active_command"] == "SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000"
    assert mode["active_command"] == "SET mod=usb low_cut=300 high_cut=2700 freq=7000.000"
    assert filt["active_command"] == "SET mod=usb low_cut=100 high_cut=2400 freq=7000.000"
    assert final.result["commands"] == [
        "SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000",
        "SET mod=usb low_cut=300 high_cut=2700 freq=7000.000",
        "SET mod=usb low_cut=100 high_cut=2400 freq=7000.000",
    ]


def test_agc_commands_queue_to_active_background_playback():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    controller.execute("play-bg --allow-live --null-sink")
    response = controller.execute("agc gain 35")
    controller.execute("stop")
    final = controller.background.join(timeout=2.0)

    assert response["active_command"] == "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=35"
    assert final.result["commands"] == ["SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=35"]


def test_client_record_bg_and_capture_bg_stop_with_metrics():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    record_started = controller.execute("record-bg recordings/bg.wav --allow-live --overwrite")
    assert record_started["operation"]["running"] is True
    controller.execute("stop")
    record_final = controller.execute("wait 2")["operation"]

    assert record_final["running"] is False
    assert record_final["result"]["path"] == "recordings/bg.wav"
    assert record_final["result"]["stopped"] is True
    assert record_final["metrics"] == {"smeter": 760, "rssi_db": -51.0, "snd_frames": 2}

    capture_started = controller.execute("capture-bg tests/fixtures/kiwi/bg.jsonl --allow-live --overwrite")
    assert capture_started["operation"]["running"] is True
    controller.execute("stop")
    capture_final = controller.execute("wait 2")["operation"]

    assert capture_final["running"] is False
    assert capture_final["result"]["path"] == "tests/fixtures/kiwi/bg.jsonl"
    assert capture_final["result"]["stopped"] is True
    assert capture_final["metrics"] == {"smeter": 770, "rssi_db": -50.0, "snd_frames": 3}


def test_tune_does_not_report_active_command_during_background_record():
    operations = FakeOperations()
    controller = ClientController(operations=operations)

    controller.execute("record-bg recordings/bg.wav --allow-live --overwrite")
    tuned = controller.execute("tune 7000")
    controller.execute("stop")
    controller.execute("wait 2")

    assert tuned["type"] == "state"
    assert "active_command" not in tuned


def test_client_allow_live_default_allows_background_alias_without_flag():
    operations = FakeOperations()
    controller = ClientController(operations=operations, allow_live_default=True)

    started = controller.execute("pb --null-sink")
    assert started["operation"]["running"] is True
    controller.execute("sp")
    final = controller.execute("wait 2")

    assert final["operation"]["running"] is False
    assert operations.calls[0][0] == "play"


def test_client_refuses_live_operations_without_allow_live():
    controller = ClientController(operations=FakeOperations())

    with pytest.raises(ClientCommandError, match="allow_live = true"):
        controller.execute("play --null-sink")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("record recordings/x.wav")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("capture tests/fixtures/kiwi/x.jsonl")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("record-bg recordings/x.wav")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("capture-bg tests/fixtures/kiwi/x.jsonl")


def test_client_rejects_bad_command():
    with pytest.raises(ClientCommandError, match="unknown command"):
        ClientController().execute("wat")


def test_client_app_script_json_output(tmp_path: Path, capsys):
    script = tmp_path / "client.txt"
    script.write_text("tune 5000\nplay-plan\n", encoding="utf-8")

    code = main(["--script", str(script), "--json"])

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    decoded = [json.loads(line) for line in lines]
    assert decoded[0]["state"]["frequency_khz"] == 5000.0
    assert decoded[1]["type"] == "play-plan"
