import io
import json
from pathlib import Path

import pytest

from kiwi_client.integrated_terminal import (
    IntegratedTerminalLayout,
    KittyPanePresenter,
    format_passband_scale,
    format_preset_ruler,
    main,
)
from kiwi_client.waterfall_raster import RasterImage


FIXTURE = Path("tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl")


def test_integrated_layout_reserves_waterfall_rulers_and_tui_region():
    layout = IntegratedTerminalLayout.compute(columns=120, lines=40)

    assert layout.waterfall_top == 0
    assert layout.waterfall_rows == 20
    assert layout.passband_row == 20
    assert layout.frequency_row == 21
    assert layout.preset_row == 22
    assert layout.tui_top == 24
    assert layout.tui_rows == 16
    assert layout.columns == 120


def test_integrated_layout_rejects_terminal_too_small():
    with pytest.raises(ValueError, match="at least"):
        IntegratedTerminalLayout.compute(columns=30, lines=8)


def test_passband_scale_uses_bracket_center_and_separate_selection_pointer():
    scale = format_passband_scale(
        737.0,
        972.0,
        tuned_khz=760.0,
        selected_khz=800.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
        columns=80,
    )

    assert len(scale) == 80
    assert "└" in scale and "┴" in scale and "┘" in scale
    assert "▼" in scale
    assert scale.index("▼") > scale.index("┘")


def test_preset_ruler_places_only_visible_non_overlapping_presets():
    ruler = format_preset_ruler(
        {
            "a": {"frequency_khz": 760.0},
            "b": {"frequency_khz": 800.0},
            "x": {"frequency_khz": 5000.0},
        },
        737.0,
        972.0,
        columns=80,
    )

    assert len(ruler) == 80
    assert "a 760.000" in ruler
    assert "b 800.000" in ruler
    assert "x 5000.000" not in ruler


def test_kitty_pane_presenter_uses_absolute_saved_cursor_and_deletes_image():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True, environ={})
    layout = IntegratedTerminalLayout.compute(columns=80, lines=24)
    image = RasterImage(width=2, height=1, rgb=bytes((0, 0, 0, 255, 255, 255)))

    presenter.draw(image, layout)
    presenter.finish()
    payload = output.getvalue()

    assert b"\x1b7\x1b[1;1H" in payload
    assert b"c=80" in payload
    assert f"r={layout.waterfall_rows}".encode() in payload
    assert b"\x1b8" in payload
    assert b"a=d,d=i,i=41,q=2" in payload


def test_integrated_fixture_dry_run_has_no_network_or_terminal_dependency(capsys):
    code = main([
        "--fixture", str(FIXTURE),
        "--presets", "presets.toml",
        "--repeat", "2",
        "--dry-run",
    ])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["backend"] == "kitty+curses"
    assert result["fixture_frames"] == 10
    assert result["network"] is False
    assert "a 760.000" in result["presets_visible"]


def test_kitty_pane_presenter_coalesces_identical_generation():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True, environ={})
    layout = IntegratedTerminalLayout.compute(columns=80, lines=24)
    image = RasterImage(width=1, height=1, rgb=b"\x00\x00\x00")

    assert presenter.draw(image, layout, generation=3) is True
    size = len(output.getvalue())
    assert presenter.draw(image, layout, generation=3) is False
    assert len(output.getvalue()) == size
    assert presenter.draw(image, layout, generation=4) is True
