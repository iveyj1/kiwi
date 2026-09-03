import threading
import time

import pytest

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


def frame(sequence, value, *, start_khz=100.0, span_khz=20.0):
    return WaterfallFrame(
        sequence=sequence,
        bins=(0, 0),
        dbm=(value, value + 1),
        start_khz=start_khz,
        span_khz=span_khz,
        center_khz=start_khz + span_khz / 2,
        bin_width_hz=span_khz * 1000 / 2,
        flags_x_zoom_server=sequence,
    )


def test_snapshot_publisher_retains_bounded_immutable_numeric_rows():
    publisher = WaterfallSnapshotPublisher(max_rows=2, clock=iter((1.0, 2.0, 3.0)).__next__)

    publisher.append(frame(1, -100))
    first = publisher.latest()
    publisher.append(frame(2, -90))
    publisher.append(frame(3, -80))
    latest = publisher.latest()

    assert first is not None
    assert first.generation == 1
    assert [row.dbm for row in first.rows] == [(-100, -99)]
    assert latest is not None
    assert latest.generation == 3
    assert [row.dbm for row in latest.rows] == [(-90, -89), (-80, -79)]
    assert [row.received_at for row in latest.rows] == [2.0, 3.0]
    assert publisher.max_rows == 2


def test_snapshot_rows_preserve_original_frequency_mapping_across_zoom_changes():
    publisher = WaterfallSnapshotPublisher(max_rows=3)

    publisher.append(frame(1, -100, start_khz=100.0, span_khz=20.0))
    publisher.append(frame(2, -90, start_khz=105.0, span_khz=10.0))
    snapshot = publisher.latest()

    assert snapshot is not None
    assert [(row.start_khz, row.span_khz, row.bin_width_hz) for row in snapshot.rows] == [
        (100.0, 20.0, 10_000.0),
        (105.0, 10.0, 5_000.0),
    ]
    assert snapshot.current_start_khz == 105.0
    assert snapshot.current_span_khz == 10.0


def test_wait_for_newer_coalesces_superseded_snapshots():
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    publisher.append(frame(1, -100))
    publisher.append(frame(2, -90))
    publisher.append(frame(3, -80))

    snapshot = publisher.wait_for_newer(0, timeout=0)

    assert snapshot is not None
    assert snapshot.generation == 3
    assert [row.sequence for row in snapshot.rows] == [1, 2, 3]
    assert publisher.wait_for_newer(3, timeout=0) is None


def test_waiting_consumer_wakes_for_frame_and_close():
    publisher = WaterfallSnapshotPublisher(max_rows=2)
    results = []

    def consume():
        results.append(publisher.wait_for_newer(0, timeout=1.0))
        results.append(publisher.wait_for_newer(1, timeout=1.0))

    thread = threading.Thread(target=consume)
    thread.start()
    time.sleep(0.01)
    publisher.append(frame(1, -100))
    time.sleep(0.01)
    publisher.close()
    thread.join(1.0)

    assert results[0] is not None and results[0].generation == 1
    assert results[1] is None
    assert thread.is_alive() is False


def test_snapshot_publisher_rejects_empty_or_changed_bin_width():
    publisher = WaterfallSnapshotPublisher(max_rows=2)
    publisher.append(frame(1, -100))

    with pytest.raises(ValueError, match="width"):
        publisher.append(WaterfallFrame(sequence=2, bins=(0,), dbm=(-90,)))
