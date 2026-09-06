import pytest

from kiwi_client.waterfall_raster import CURSOR_MARKER_RGB, RasterImage
from kiwi_client.waterfall_scale import (
    FREQUENCY_SCALE_RGB,
    PASSBAND_SCALE_RGB,
    PRESET_SCALE_RGB,
    bitmap_text_width,
    compose_waterfall_scale,
    draw_bitmap_text,
    scale_text_renderer,
)


def pixel(image, column, row):
    offset = (row * image.width + column) * 3
    return tuple(image.rgb[offset:offset + 3])


def test_bitmap_font_draws_deterministic_numeric_and_register_text():
    canvas = bytearray(80 * 16 * 3)
    draw_bitmap_text(canvas, 80, 16, 1, 1, "A 760.0", FREQUENCY_SCALE_RGB, scale=2)

    assert bitmap_text_width("A 760.0", scale=2) == 82
    assert any(canvas)
    assert tuple(canvas[(1 * 80 + 3) * 3:(1 * 80 + 3) * 3 + 3]) == FREQUENCY_SCALE_RGB


def test_pillow_freetype_renderer_is_antialiased_when_available():
    pytest.importorskip("PIL")
    renderer = scale_text_renderer("pillow", font_scale=2)
    rendered = renderer.render(
        b"\x00" * 120 * 24 * 3,
        120,
        24,
        [(1, 1, "850.0", (255, 255, 255))],
    )

    channel_values = set(rendered[0::3])
    assert renderer.backend == "pillow"
    assert 255 in channel_values
    assert any(0 < value < 255 for value in channel_values)


def test_graphical_scale_uses_exact_frequency_columns_for_all_markers():
    waterfall = RasterImage(width=101, height=2, rgb=b"\x00" * 101 * 2 * 3)
    result = compose_waterfall_scale(
        waterfall,
        100.0,
        200.0,
        tuned_khz=150.0,
        selected_khz=170.0,
        low_cut_hz=-10_000,
        high_cut_hz=10_000,
        presets={"a": {"frequency_khz": 120.0}},
        label_target_pixels=30,
        font_scale=1,
    )

    assert result.image.width == 101
    assert result.image.height > waterfall.height
    tuning_top = waterfall.height
    assert pixel(result.image, 40, tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 50, tuning_top + 6) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 60, tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 70, tuning_top + 7) == CURSOR_MARKER_RGB

    tick_top = tuning_top + 8
    assert pixel(result.image, 0, tick_top) == FREQUENCY_SCALE_RGB
    assert pixel(result.image, 50, tick_top) == FREQUENCY_SCALE_RGB
    assert pixel(result.image, 100, tick_top) == FREQUENCY_SCALE_RGB

    assert pixel(result.image, 20, result.preset_stem_top) == PRESET_SCALE_RGB
    assert result.preset_labels == ("A 120.000",)


def test_graphical_cw_passband_uses_offset_radio_frequency_but_marks_user_frequency():
    waterfall = RasterImage(width=1001, height=1, rgb=b"\x00" * 1001 * 3)
    result = compose_waterfall_scale(
        waterfall,
        299.0,
        301.0,
        tuned_khz=300.0,
        passband_reference_khz=299.2,
        selected_khz=300.0,
        low_cut_hz=650,
        high_cut_hz=1050,
        presets={},
        font_backend="bitmap",
        font_scale=1,
    )

    assert pixel(result.image, 425, result.tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 500, result.tuning_top + 6) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 625, result.tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 825, result.tuning_top + 2) != PASSBAND_SCALE_RGB


def test_graphical_passband_clips_at_visible_viewport_edge():
    waterfall = RasterImage(width=101, height=1, rgb=b"\x00" * 101 * 3)
    result = compose_waterfall_scale(
        waterfall,
        100.0,
        200.0,
        tuned_khz=102.0,
        selected_khz=102.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
        presets={},
        font_backend="bitmap",
        font_scale=1,
    )

    assert pixel(result.image, 0, result.tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 2, result.tuning_top + 6) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 7, result.tuning_top + 2) == PASSBAND_SCALE_RGB


def test_graphical_scale_omits_irregular_edge_and_rejects_colliding_presets():
    waterfall = RasterImage(width=401, height=1, rgb=b"\x00" * 401 * 3)
    result = compose_waterfall_scale(
        waterfall,
        260.0,
        308.6,
        tuned_khz=280.0,
        selected_khz=280.0,
        low_cut_hz=-5000,
        high_cut_hz=5000,
        presets={
            "a": {"frequency_khz": 280.0},
            "b": {"frequency_khz": 280.1},
            "x": {"frequency_khz": 1000.0},
        },
        label_target_pixels=100,
        font_scale=1,
    )

    assert "308.6" not in result.frequency_labels
    assert "280" in result.frequency_labels
    assert result.preset_labels == ("A 280.000",)
