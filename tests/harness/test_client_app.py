import json
import time
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientCommandError, ClientController, run_script, main


class FakeOperations:
    def __init__(self):
        self.calls = []

    def play(self, config, *, null_sink: bool, stop_event=None):
        self.calls.append(("play", config, null_sink, stop_event))
        if stop_event is not None:
            deadline = time.monotonic() + 1.0
            while not stop_event.is_set() and time.monotonic() < deadline:
                time.sleep(0.01)
        return {"frames": 1024, "dry_run": null_sink, "stopped": bool(stop_event and stop_event.is_set())}

    def record(self, config):
        self.calls.append(("record", config))
        return {"path": str(config.output), "frames": 2048}

    def capture(self, config):
        self.calls.append(("capture", config))
        return {"path": str(config.output)}


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


def test_client_controller_connect_disconnect_state_only():
    controller = ClientController()

    assert controller.execute("connect")["state"]["connected"] is True
    assert controller.execute("disconnect")["state"]["connected"] is False


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

    assert play == {"type": "play", "result": {"frames": 1024, "dry_run": True, "stopped": False}}
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


def test_client_refuses_live_operations_without_allow_live():
    controller = ClientController(operations=FakeOperations())

    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("play --null-sink")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("record recordings/x.wav")
    with pytest.raises(ClientCommandError, match="without --allow-live"):
        controller.execute("capture tests/fixtures/kiwi/x.jsonl")


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
