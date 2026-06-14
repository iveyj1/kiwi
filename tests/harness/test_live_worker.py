import time

from kiwi_client.live_worker import BackgroundOperation


def test_background_operation_reports_result():
    worker = BackgroundOperation()

    worker.start("test", lambda stop_event: {"stopped": stop_event.is_set()})
    status = worker.join(timeout=1.0)

    assert not status.running
    assert status.name == "test"
    assert status.result == {"stopped": False}
    assert status.error is None


def test_background_operation_stop_is_cooperative():
    worker = BackgroundOperation()

    def target(stop_event):
        while not stop_event.is_set():
            time.sleep(0.01)
        return {"stopped": True}

    worker.start("test", target)
    stopped = worker.stop()
    final = worker.join(timeout=1.0)

    assert stopped.stop_requested
    assert not final.running
    assert final.result == {"stopped": True}
