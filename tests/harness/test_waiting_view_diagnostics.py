from dataclasses import replace

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


def test_waiting_diagnostics_distinguish_no_frames_from_rejected_frames():
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    publisher.expect_view(1000, 7)
    assert 'no frames received' in publisher.waiting_detail
    span = 30000 / 128
    frame = WaterfallFrame(sequence=0, bins=(0,) * 1024, dbm=(-90,) * 1024,
        start_khz=855 - span / 2, center_khz=855, span_khz=span,
        bin_width_hz=span * 1000 / 1024, flags_x_zoom_server=7)
    assert publisher.append(frame) is None
    assert 'requested 1000.000000 kHz z7' in publisher.waiting_detail
    assert 'received 855.000000 kHz z7 (1 rejected)' in publisher.waiting_detail
    assert publisher.latest() is None
    publisher.expect_view(2000, 7)
    assert 'no frames received' in publisher.waiting_detail
    publisher.append(replace(frame, start_khz=2000 - span / 2, center_khz=2000))
    assert publisher.waiting_detail == ''
    assert not publisher.awaiting_view


def test_waiting_diagnostic_tolerates_unmapped_frames_and_close():
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    publisher.expect_view(1000, 7)
    publisher.append(WaterfallFrame(sequence=0, bins=(0,), dbm=(-90,)))
    assert 'received ? kHz zNone' in publisher.waiting_detail
    publisher.close()
    assert publisher.waiting_detail == ''
