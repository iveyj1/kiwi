import json
from dataclasses import replace
from pathlib import Path

from kiwi_client.waterfall import WaterfallFrame, WaterfallReceiverState, contextualize_waterfall_frame
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher
from kiwi_client.gui_app import WaterfallGuiModel

DATA = json.loads(Path('tests/fixtures/kiwi/wf-capped-view.json').read_text())


def capped_frame(center=DATA['received_center_khz'], zoom=11):
    state = WaterfallReceiverState().apply_msg_params(DATA['metadata'])
    start = center - 30000 / 2**zoom / 2
    x = round(start / 30000 * (1024 << 14))
    frame = WaterfallFrame(sequence=1, bins=(160,) * 1024, dbm=(-95,) * 1024,
                           x_bin_server=x, flags_x_zoom_server=zoom)
    return contextualize_waterfall_frame(frame, state)


def test_advertised_cap_accepts_correct_center_not_old_view():
    publisher = WaterfallSnapshotPublisher(max_rows=5)
    publisher.expect_view(DATA['requested_center_khz'], DATA['requested_zoom'])
    assert publisher.append(capped_frame(center=210.79)) is None
    assert publisher.append(capped_frame(zoom=10)) is None
    frame = capped_frame()
    assert frame.zoom_cap == 11
    assert frame.start_khz == DATA['received_start_khz']
    assert publisher.append(frame) is not None
    assert not publisher.awaiting_view
    # No implicit acceptance of arbitrary server zoom changes without metadata.
    publisher.expect_view(230.79, 12)
    assert publisher.append(replace(frame, zoom_cap=None)) is None


def test_local_display_zoom_is_retained_above_hardware_cap():
    model = WaterfallGuiModel(tuned_khz=230.79, selected_khz=230.79)
    model._session_mapped = True
    model.session.state = replace(model.session.state, waterfall_center_khz=230.79, waterfall_zoom=12)
    model.publisher.expect_view(230.79, 12)
    model.publisher.append(capped_frame())
    start, end = model.display_frequency_range()
    assert abs((end - start) - 30000 / 2**12) < 1e-8
    assert model.image().width == 1024
