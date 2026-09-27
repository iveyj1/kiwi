import pytest

from kiwi_client.waterfall_raster import CURSOR_MARKER_RGB, RasterImage
from kiwi_client.waterfall_scale import (
    FREQUENCY_SCALE_RGB,
    PASSBAND_SCALE_RGB,
    PRESET_SCALE_RGB,
    RECEIVER_SCALE_RGB,
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
    # Each labeled interval is split into ten; minor ticks are shorter.
    assert pixel(result.image, 5, tick_top) == FREQUENCY_SCALE_RGB
    assert pixel(result.image, 5, tick_top + 1) == FREQUENCY_SCALE_RGB
    assert pixel(result.image, 5, tick_top + 2) != FREQUENCY_SCALE_RGB
    assert pixel(result.image, 45, tick_top) == FREQUENCY_SCALE_RGB

    assert pixel(result.image, 20, result.preset_stem_top) == PRESET_SCALE_RGB
    assert result.preset_labels == ("A 120.000",)


@pytest.mark.parametrize('show_reference', [False, True])
def test_graphical_cw_passband_uses_offset_radio_frequency_but_marks_user_frequency(show_reference):
    waterfall = RasterImage(width=1001, height=1, rgb=b"\x00" * 1001 * 3)
    result = compose_waterfall_scale(
        waterfall,
        299.0,
        301.0,
        tuned_khz=300.0,
        passband_reference_khz=299.2,
        show_reference_marker=show_reference,
        selected_khz=300.0,
        low_cut_hz=600,
        high_cut_hz=1000,
        presets={},
        font_backend="bitmap",
        font_scale=1,
    )

    assert pixel(result.image, 100, result.tuning_top + 6) == (RECEIVER_SCALE_RGB if show_reference else (0, 0, 0))
    assert pixel(result.image, 400, result.tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 500, result.tuning_top + 6) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 600, result.tuning_top + 2) == PASSBAND_SCALE_RGB
    assert pixel(result.image, 800, result.tuning_top + 2) != PASSBAND_SCALE_RGB


def test_frequency_marker_heads_widen_by_two_pixels_without_changing_tails():
    image = RasterImage(101, 2, b'\0' * 101 * 2 * 3)
    result = compose_waterfall_scale(image, 100, 200, tuned_khz=150, selected_khz=170,
        passband_reference_khz=101, low_cut_hz=0, high_cut_hz=3000, presets={}, font_backend='bitmap')
    top = result.tuning_top
    def columns(y, color, start=0, stop=101):
        return {x for x in range(start, stop) if pixel(result.image, x, top + y) == color}
    assert columns(2, PASSBAND_SCALE_RGB, 45, 56) == {49, 50, 51, 52}
    for y in range(3, 7):
        assert columns(y, PASSBAND_SCALE_RGB, 45, 56) == {50, 51}
    assert not columns(1, PASSBAND_SCALE_RGB, 45, 56)
    assert columns(5, CURSOR_MARKER_RGB) == set(range(67, 74))
    assert columns(6, CURSOR_MARKER_RGB) == {69, 70, 71}
    assert columns(7, CURSOR_MARKER_RGB) == {70}
    assert not columns(4, CURSOR_MARKER_RGB)
    assert result.image.rgb[:len(image.rgb)] == image.rgb


@pytest.mark.parametrize('tuned,selected', [(100, 200), (200, 100)])
def test_wider_frequency_heads_clip_at_viewport_edges(tuned, selected):
    result = compose_waterfall_scale(RasterImage(101, 1, b'\0' * 303), 100, 200,
        tuned_khz=tuned, selected_khz=selected, passband_reference_khz=145,
        low_cut_hz=-1000, high_cut_hz=1000, presets={}, font_backend='bitmap')
    c, s = tuned - 100, selected - 100
    for x in range(101):
        if x not in {44, 45, 46}:
            assert (pixel(result.image, x, result.tuning_top + 2) == PASSBAND_SCALE_RGB) == (c - 1 <= x <= c + 2)
        assert (pixel(result.image, x, result.tuning_top + 5) == CURSOR_MARKER_RGB) == (s - 3 <= x <= s + 3)


@pytest.mark.parametrize('width_hz', [10, 50, 100])
def test_minimum_passband_gets_nine_by_seven_pointer(width_hz):
    result = compose_waterfall_scale(RasterImage(1001, 1, b'\0' * 3003), 100, 200,
        tuned_khz=150, selected_khz=150, low_cut_hz=0, high_cut_hz=width_hz,
        presets={}, font_backend='bitmap')
    for dy, expected in enumerate([set(range(496, 505)), set(range(497, 504)), set(range(498, 503)),
                                    {499, 500, 501}, {500, 501}, {500, 501}, {500, 501}]):
        actual = {x for x in range(490, 510) if pixel(result.image, x, result.tuning_top + dy) == PASSBAND_SCALE_RGB}
        assert actual == expected


@pytest.mark.parametrize('frequency', [100, 200])
def test_minimum_pointer_clips_without_wrapping(frequency):
    result = compose_waterfall_scale(RasterImage(101, 1, b'\0' * 303), 100, 200,
        tuned_khz=frequency, selected_khz=frequency, low_cut_hz=0, high_cut_hz=10,
        presets={}, font_backend='bitmap')
    center = int(frequency - 100)
    actual = {x for x in range(101) if pixel(result.image, x, result.tuning_top) == PASSBAND_SCALE_RGB}
    assert actual == set(range(max(0, center - 4), min(101, center + 5)))


def test_clipped_wide_passband_does_not_get_minimum_pointer():
    result = compose_waterfall_scale(RasterImage(101, 1, b'\0' * 303), 100, 200,
        tuned_khz=150, selected_khz=150, passband_reference_khz=90, low_cut_hz=0,
        high_cut_hz=11000, presets={}, font_backend='bitmap')
    assert pixel(result.image, 50, result.tuning_top) == (0, 0, 0)
    assert pixel(result.image, 50, result.tuning_top + 6) == PASSBAND_SCALE_RGB


def test_cw_reference_cli_is_opt_in():
    from kiwi_client.integrated_terminal import build_arg_parser
    parser = build_arg_parser()
    assert not parser.parse_args([]).show_cw_offset_marker
    assert parser.parse_args(['--show-cw-offset-marker']).show_cw_offset_marker


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
