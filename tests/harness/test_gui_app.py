import json
from pathlib import Path

from kiwi_client.gui_app import WaterfallGuiModel, main


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
    assert "10 frames" in model.status_text()


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
