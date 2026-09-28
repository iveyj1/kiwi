import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher

FIXTURE = json.loads((Path(__file__).parents[1] / 'fixtures/kiwi/wf-view-transition.json').read_text())


def mapped(center, value=-90, zoom=7):
    width = FIXTURE['width']
    span = FIXTURE['bandwidth_khz'] / 2 ** zoom
    start = max(0, min(center - span / 2, FIXTURE['bandwidth_khz'] - span))
    return WaterfallFrame(sequence=0, bins=(0,) * width, dbm=(value,) * width,
        start_khz=start, center_khz=start + span / 2, span_khz=span,
        bin_width_hz=span * 1000 / width, flags_x_zoom_server=0x20000 | zoom)


def test_view_reset_rejects_delayed_old_rows_and_clears_raster_cache():
    from kiwi_client.gui_app import SnapshotRasterizer
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    old = publisher.append(mapped(855))
    raster = SnapshotRasterizer(min_dbm=-120, max_dbm=-30)
    raster.update(old)
    publisher.expect_view(FIXTURE['requested_center_khz'], FIXTURE['zoom'])
    assert publisher.latest() is None
    for row in FIXTURE['rows']:
        publisher.append(mapped(row['center_khz'], row['value']))
    current = publisher.latest()
    assert [row.dbm[0] for row in current.rows] == [-80, -79]
    assert old.rows[0].dbm[0] == -90
    image = raster.update(current)
    assert image.rgb[:3 * image.width * 3] == b'\0' * (3 * image.width * 3)


@pytest.mark.parametrize('center,zoom', [(0, 7), (30000, 7), (1000, 0), (1000, 14)])
def test_expected_view_accepts_server_edge_clamping_and_rejects_wrong_zoom(center, zoom):
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    publisher.expect_view(center, zoom)
    frame = mapped(center, zoom=zoom)
    assert publisher.append(replace(frame, flags_x_zoom_server=(zoom + 1) % 15)) is None
    assert publisher.append(replace(frame, start_khz=None)) is None
    assert publisher.append(frame) is not None


def test_live_controller_gates_before_sending_view_command():
    from kiwi_client.client_app import ClientController
    from kiwi_client.session_manager import RecenterWaterfall
    current = ClientController()
    current.configure_waterfall_session(center_khz=855, zoom=7, speed=1, interp=13)
    current.waterfall_snapshots.append(mapped(855))
    current.paired_session.state = replace(current.paired_session.state, selected_khz=1000)
    sent = []
    class Background:
        def status(self): return SimpleNamespace(running=True, name='radio', as_dict=lambda: {})
        def send_command(self, command):
            assert current.waterfall_snapshots.latest() is None
            sent.append(command)
    current.background = Background()
    current.dispatch_session_action(RecenterWaterfall())
    assert sent
    assert current.waterfall_snapshots.append(mapped(855)) is None
    from kiwi_client.gui_app import WaterfallGuiModel
    from kiwi_client.integrated_terminal import set_console_frequency
    model = WaterfallGuiModel(tuned_khz=1000, selected_khz=1000)
    model.publisher = current.waterfall_snapshots
    model.session = current.paired_session
    model.action_dispatch = current.dispatch_session_action
    model._session_mapped = True
    set_console_frequency(model, 2000)  # Second tune before the first requested view arrives.
    assert current.waterfall_snapshots.append(mapped(1000)) is None
    assert current.waterfall_snapshots.append(mapped(2000)) is not None
    assert not current.waterfall_snapshots.awaiting_view
