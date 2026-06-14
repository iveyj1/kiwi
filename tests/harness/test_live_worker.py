import time

from kiwi_client.live_worker import BackgroundOperation


def test_background_operation_reports_result():
    worker = BackgroundOperation()

    worker.start("test", lambda stop_event, command_queue, status_callback: {"stopped": stop_event.is_set()})
    status = worker.join(timeout=1.0)

    assert not status.running
    assert status.name == "test"
    assert status.result == {"stopped": False}
    assert status.error is None


def test_background_operation_stop_is_cooperative():
    worker = BackgroundOperation()

    def target(stop_event, command_queue, status_callback):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    worker.start("test", target)
    stopped = worker.stop()
    final = worker.join(timeout=1.0)

    assert stopped.stop_requested
    assert not final.running
    assert final.result == {"stopped": True}


def test_background_operation_queues_commands():
    worker = BackgroundOperation()

    def target(stop_event, command_queue, status_callback):
        command = command_queue.get(timeout=1.0)
        return {"command": command}

    worker.start("test", target)
    queued = worker.send_command("SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000")
    final = worker.join(timeout=1.0)

    assert queued.running
    assert final.result == {"command": "SET mod=am low_cut=-5000 high_cut=5000 freq=7000.000"}


def test_background_operation_reports_live_metrics():
    worker = BackgroundOperation()

    def target(stop_event, command_queue, status_callback):
        status_callback({"rssi_db": -42.0, "smeter": 850})
        return {"done": True}

    worker.start("test", target)
    final = worker.join(timeout=1.0)

    assert final.metrics == {"rssi_db": -42.0, "smeter": 850}
    assert final.as_dict()["metrics"] == {"rssi_db": -42.0, "smeter": 850}
