import json
from pathlib import Path

from kiwi_client.gui_app import (
    FixtureWaterfallTimeline,
    SnapshotRasterizer,
    WaterfallGuiModel,
    gui_close_key,
    main,
)


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


def test_gui_close_key_policy_supports_q_escape_and_control_q():
    assert gui_close_key("q") is True
    assert gui_close_key("Q") is True
    assert gui_close_key("escape") is True
    assert gui_close_key("q", control=True) is True
    assert gui_close_key("enter") is False


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
