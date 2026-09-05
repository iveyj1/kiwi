import json
from pathlib import Path

import pytest

from kiwi_client.gui_app import (
    FixtureWaterfallTimeline,
    SnapshotRasterizer,
    WaterfallGuiModel,
    gui_close_key,
    gui_control_action,
    gui_focus_target,
    logical_display_height,
    main,
)


from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_raster import (
    CURSOR_MARKER_RGB,
    PASSBAND_MARKER_RGB,
    TUNED_MARKER_RGB,
    render_dbm_rows,
)
from kiwi_client.waterfall_snapshots import WaterfallSnapshotPublisher


FIXTURE = Path("tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl")


def test_fixture_gui_model_publishes_mapped_rows_and_direct_rgb():
    model = WaterfallGuiModel(history_rows=12, render_min_db=-110, render_max_db=-30)

    frames = model.load_fixture(FIXTURE, repeat=2)
    snapshot = model.publisher.latest()
    image = model.image()

    assert frames == 10
    assert snapshot is not None
    assert snapshot.generation == 10
    assert len(snapshot.rows) == 10
    assert snapshot.current_start_khz is not None
    assert snapshot.current_span_khz is not None
    assert image.width == 1024
    assert image.height == 12
    assert len(image.rgb) == 1024 * 12 * 3
    assert model.frequency_text().endswith("kHz")
    assert "source 10 | presented 10" in model.status_text()


def test_gui_model_can_delegate_session_actions_to_controller_router():
    routed = []
    model = WaterfallGuiModel(history_rows=5, action_dispatch=lambda action: routed.append(action))
    model.load_fixture(FIXTURE)

    model.move_selection(1)
    model.tune_selected()
    model.recenter()
    model.zoom(1)
    model.set_direct_frequency(860.0)

    assert [type(action).__name__ for action in routed] == [
        "SelectFrequency",
        "TuneSelected",
        "RecenterWaterfall",
        "ZoomWaterfall",
        "DirectFrequency",
    ]


def test_gui_model_routes_local_frequency_actions_through_shared_session():
    model = WaterfallGuiModel(
        history_rows=5,
        tuned_khz=855.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
        main_step_hz=1000,
        small_step_hz=100,
    )
    model.load_fixture(FIXTURE)

    moved = model.move_selection(1)
    tuned = model.tune_selected()
    recentered = model.recenter()
    zoomed = model.zoom(1)
    direct = model.set_direct_frequency(860.125)

    assert moved.state.selected_khz == pytest.approx(856.0)
    assert tuned.commands.snd == ("SET mod=am low_cut=-5000 high_cut=5000 freq=856.000",)
    assert recentered.commands.waterfall == ("SET zoom=7 cf=856.000",)
    assert zoomed.commands.waterfall == ("SET zoom=8 cf=856.000",)
    assert direct.state.frequency_khz == direct.state.selected_khz == pytest.approx(860.125)
    assert direct.state.waterfall_center_khz == pytest.approx(860.125)


def test_gui_model_draws_tuned_passband_and_cursor_overlays():
    model = WaterfallGuiModel(
        history_rows=5,
        tuned_khz=855.0,
        selected_khz=860.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
    )
    model.load_fixture(FIXTURE)

    image = model.image()
    snapshot = model.publisher.latest()
    start = snapshot.current_start_khz
    end = start + snapshot.current_span_khz

    def pixel(frequency_khz):
        column = round((frequency_khz - start) / (end - start) * (image.width - 1))
        offset = ((image.height - 1) * image.width + column) * 3
        return tuple(image.rgb[offset:offset + 3])

    assert pixel(855.0) == TUNED_MARKER_RGB
    assert pixel(850.0) == PASSBAND_MARKER_RGB
    assert pixel(860.0) == CURSOR_MARKER_RGB  # cursor wins at high passband edge


def test_gui_fixture_zoom_and_recenter_change_visible_frequency_range():
    model = WaterfallGuiModel(history_rows=5)
    model.load_fixture(FIXTURE)
    initial_start, initial_end = model.display_frequency_range()

    model.zoom(-1)
    wider_start, wider_end = model.display_frequency_range()
    assert wider_end - wider_start == pytest.approx(2 * (initial_end - initial_start))

    model.set_direct_frequency(900.0)
    centered_start, centered_end = model.display_frequency_range()
    assert (centered_start + centered_end) / 2 == pytest.approx(900.0)

    for _ in range(20):
        model.zoom(-1)
    assert model.session.state.waterfall_zoom == 0
    image = model.image()
    assert image.width == 1024
    bottom_left = (image.height - 1) * image.width * 3
    assert tuple(image.rgb[bottom_left:bottom_left + 3]) == (0, 0, 0)


def test_tune_selected_reveals_tuned_marker_when_selection_coincides():
    model = WaterfallGuiModel(history_rows=5)
    model.load_fixture(FIXTURE)
    model.move_selection(1)
    model.tune_selected()
    image = model.image()
    start, end = model.display_frequency_range()
    column = round((model.session.state.frequency_khz - start) / (end - start) * (image.width - 1))
    offset = ((image.height - 1) * image.width + column) * 3

    assert tuple(image.rgb[offset:offset + 3]) == TUNED_MARKER_RGB
    assert tuple(image.rgb[offset + 3:offset + 6]) == TUNED_MARKER_RGB


def test_gui_focus_policy_starts_and_returns_to_display():
    assert gui_focus_target("startup") == "display"
    assert gui_focus_target("frequency_requested") == "frequency"
    assert gui_focus_target("frequency_accepted") == "display"


def test_gui_control_key_policy_maps_cursor_tune_recenter_and_zoom():
    assert gui_control_action("left") == ("move", -1, False)
    assert gui_control_action("right", shift=True) == ("move", 1, True)
    assert gui_control_action("enter") == ("tune", 0, False)
    assert gui_control_action("c") == ("recenter", 0, False)
    assert gui_control_action("+") == ("zoom", 1, False)
    assert gui_control_action("-") == ("zoom", -1, False)
    assert gui_control_action("x") is None


def test_display_height_defaults_to_one_physical_pixel_per_source_row():
    assert logical_display_height(400, row_pixels=1.0, device_pixel_ratio=1.0) == 400
    assert logical_display_height(400, row_pixels=1.0, device_pixel_ratio=2.0) == 200
    assert logical_display_height(
        800,
        row_pixels=1.0,
        device_pixel_ratio=1.0,
        available_logical_height=600,
    ) == 600
    assert logical_display_height(400, row_pixels=2.0, device_pixel_ratio=1.0) == 800


def test_gui_close_key_policy_supports_q_escape_and_control_q():
    assert gui_close_key("q") is True
    assert gui_close_key("Q") is True
    assert gui_close_key("escape") is True
    assert gui_close_key("q", control=True) is True
    assert gui_close_key("enter") is False


def test_gui_model_render_scale_change_invalidates_cached_rgb_history():
    model = WaterfallGuiModel(history_rows=5)
    model.load_fixture(FIXTURE)
    first = model.image()

    assert model.set_render_scale(-120, -20) is True
    second = model.image()

    assert model.rasterizer.presented_generation == 5
    assert second.rgb != first.rgb
    assert model.set_render_scale(-120, -20) is False


def test_fixture_timeline_publishes_incrementally_and_stops_after_repeats():
    model = WaterfallGuiModel(history_rows=12)
    timeline = FixtureWaterfallTimeline.from_fixture(FIXTURE, repeat=2)

    generations = []
    while timeline.advance(model.publisher):
        generations.append(model.publisher.latest().generation)

    assert generations == list(range(1, 11))
    assert timeline.total_frames == 10
    assert timeline.done is True
    assert timeline.advance(model.publisher) is False


def test_snapshot_rasterizer_consumes_latest_generation_and_pads_history(monkeypatch):
    model = WaterfallGuiModel(history_rows=12)
    timeline = FixtureWaterfallTimeline.from_fixture(FIXTURE, repeat=1)
    calls = []
    original = __import__("kiwi_client.gui_app", fromlist=["render_dbm_rows"]).render_dbm_rows

    def counted(rows, *, min_dbm, max_dbm):
        calls.append(len(rows))
        return original(rows, min_dbm=min_dbm, max_dbm=max_dbm)

    monkeypatch.setattr("kiwi_client.gui_app.render_dbm_rows", counted)
    rasterizer = SnapshotRasterizer(min_dbm=-100, max_dbm=-40)
    timeline.advance(model.publisher)
    timeline.advance(model.publisher)
    image = rasterizer.update(model.publisher.latest())
    same = rasterizer.update(model.publisher.latest())

    assert image == same
    assert image.width == 1024
    assert image.height == 12
    assert rasterizer.presented_generation == 2
    assert calls.count(1) == 3  # two data rows plus one cached padding row


def test_snapshot_rasterizer_remaps_each_history_row_from_its_original_frequency_mapping():
    publisher = WaterfallSnapshotPublisher(max_rows=2)
    publisher.append(WaterfallFrame(
        sequence=1,
        bins=(0,) * 5,
        dbm=(-100, -90, -80, -70, -60),
        start_khz=0.0,
        span_khz=100.0,
    ))
    snapshot = publisher.append(WaterfallFrame(
        sequence=2,
        bins=(0,) * 5,
        dbm=(-50,) * 5,
        start_khz=25.0,
        span_khz=50.0,
    ))
    rasterizer = SnapshotRasterizer(min_dbm=-110, max_dbm=-40)

    image = rasterizer.update(snapshot, target_start_khz=25.0, target_end_khz=75.0)
    expected_old_first = render_dbm_rows(((-90,),), min_dbm=-110, max_dbm=-40).rgb
    wrong_unmapped_first = render_dbm_rows(((-100,),), min_dbm=-110, max_dbm=-40).rgb

    assert image.rgb[:3] == expected_old_first
    assert image.rgb[:3] != wrong_unmapped_first
    assert image.rgb[image.width * 3:image.width * 3 + 3] == render_dbm_rows(
        ((-50,),), min_dbm=-110, max_dbm=-40
    ).rgb


def test_animated_fixture_dry_run_reports_timeline_and_presented_generation(capsys):
    code = main([
        "--fixture", str(FIXTURE),
        "--rows", "20",
        "--repeat", "2",
        "--animate",
        "--fps", "20",
        "--dry-run",
    ])

    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["frames"] == 10
    assert result["presented_generation"] == 10
    assert result["requested_fps"] == 20
    assert result["animated"] is True


def test_fixture_gui_dry_run_does_not_import_or_open_qt(capsys):
    code = main([
        "--fixture", str(FIXTURE),
        "--rows", "20",
        "--repeat", "2",
        "--dry-run",
    ])

    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["frames"] == 10
    assert result["image_width"] == 1024
    assert result["image_height"] == 20
    assert result["backend"] == "PySide6"
    assert result["requested_row_pixels"] == 1.0
