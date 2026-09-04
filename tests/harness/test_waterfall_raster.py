import struct
import zlib

import pytest

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_raster import (
    RasterImage,
    CURSOR_MARKER_RGB,
    PASSBAND_MARKER_RGB,
    TUNED_MARKER_RGB,
    WaterfallHistory,
    WaterfallRasterHistory,
    WaterfallOverlay,
    apply_frequency_overlay,
    dbm_to_rgb,
    encode_png,
    render_dbm_rows,
)


def frame(*values: int) -> WaterfallFrame:
    return WaterfallFrame(sequence=0, bins=tuple(0 for _ in values), dbm=tuple(values))


def test_history_scrolls_and_preserves_conventional_orientation():
    history = WaterfallHistory(max_rows=2)

    history.append(frame(-100, -90))
    history.append(frame(-80, -70))
    history.append(frame(-60, -50))

    assert history.width == 2
    assert history.rows() == ((-80, -70), (-60, -50))
    assert history.rows(newest_at_top=True) == ((-60, -50), (-80, -70))


def test_history_pads_missing_old_rows_at_the_top():
    history = WaterfallHistory(max_rows=3)
    history.append(frame(-80, -70))

    assert history.rows(pad_dbm=-255) == ((-255, -255), (-255, -255), (-80, -70))


def test_history_rejects_mismatched_frame_width():
    history = WaterfallHistory(max_rows=3)
    history.append(frame(-80, -70))

    with pytest.raises(ValueError, match="width"):
        history.append(frame(-80))


def test_raster_history_converts_each_row_once_and_preserves_padding_orientation(monkeypatch):
    calls = []
    original = render_dbm_rows

    def counted(rows, *, min_dbm, max_dbm):
        calls.append(tuple(tuple(row) for row in rows))
        return original(rows, min_dbm=min_dbm, max_dbm=max_dbm)

    monkeypatch.setattr("kiwi_client.waterfall_raster.render_dbm_rows", counted)
    history = WaterfallRasterHistory(max_rows=3, min_dbm=-100, max_dbm=0)
    history.append(frame(-100, -50))
    history.append(frame(-50, 0))

    bottom = history.image()
    top = history.image(newest_at_top=True)

    assert calls == [((-100, -50),), ((-50, 0),)]
    assert bottom == original(
        ((-255, -255), (-100, -50), (-50, 0)),
        min_dbm=-100,
        max_dbm=0,
    )
    assert top == original(
        ((-50, 0), (-100, -50), (-255, -255)),
        min_dbm=-100,
        max_dbm=0,
    )


def test_raster_history_is_bounded_and_rejects_mismatched_width():
    history = WaterfallRasterHistory(max_rows=2, min_dbm=-100, max_dbm=0)
    history.append(frame(-100, -90))
    history.append(frame(-80, -70))
    history.append(frame(-60, -50))

    assert len(history) == 2
    assert history.image().height == 2
    with pytest.raises(ValueError, match="width"):
        history.append(frame(-80))


def test_dbm_to_rgb_is_deterministic_and_clamps():
    assert dbm_to_rgb(-200, min_dbm=-100, max_dbm=0) == (0, 0, 0)
    assert dbm_to_rgb(-100, min_dbm=-100, max_dbm=0) == (0, 0, 0)
    assert dbm_to_rgb(-50, min_dbm=-100, max_dbm=0) == (0, 255, 255)
    assert dbm_to_rgb(0, min_dbm=-100, max_dbm=0) == (255, 255, 255)
    assert dbm_to_rgb(20, min_dbm=-100, max_dbm=0) == (255, 255, 255)


def test_render_rows_and_dependency_free_png_encoding(monkeypatch):
    image = render_dbm_rows(((-100, -50, 0),), min_dbm=-100, max_dbm=0)

    assert image == RasterImage(
        width=3,
        height=1,
        rgb=bytes((0, 0, 0, 0, 255, 255, 255, 255, 255)),
    )

    real_compress = zlib.compress
    compression_levels = []

    def capture_compress(data, level=-1):
        compression_levels.append(level)
        return real_compress(data, level)

    monkeypatch.setattr("kiwi_client.waterfall_raster.zlib.compress", capture_compress)
    png = encode_png(image)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", png[16:24]) == (3, 1)

    idat_start = png.index(b"IDAT")
    idat_length = struct.unpack(">I", png[idat_start - 4:idat_start])[0]
    scanline = zlib.decompress(png[idat_start + 4:idat_start + 4 + idat_length])
    assert scanline == b"\x00" + image.rgb
    assert compression_levels == [1]

    with pytest.raises(ValueError, match="compression_level"):
        encode_png(image, compression_level=10)


def test_frequency_overlay_supports_two_pixel_markers():
    image = RasterImage(width=11, height=2, rgb=bytes((0, 0, 0)) * 22)
    rendered = apply_frequency_overlay(
        image,
        WaterfallOverlay(start_khz=0, end_khz=10, tuned_khz=5, marker_width=2),
    )

    for column in (5, 6):
        assert tuple(rendered.rgb[column * 3:(column + 1) * 3]) == TUNED_MARKER_RGB
    assert tuple(rendered.rgb[12:15]) == (0, 0, 0)


def test_frequency_overlay_draws_tuned_and_passband_columns():
    image = RasterImage(width=5, height=2, rgb=b"\x00" * 5 * 2 * 3)
    overlay = WaterfallOverlay(
        start_khz=100.0,
        end_khz=200.0,
        tuned_khz=150.0,
        low_cut_hz=-25_000,
        high_cut_hz=25_000,
    )

    rendered = apply_frequency_overlay(image, overlay)

    for row in range(2):
        pixels = [tuple(rendered.rgb[(row * 5 + column) * 3:(row * 5 + column + 1) * 3]) for column in range(5)]
        assert pixels == [(0, 0, 0), PASSBAND_MARKER_RGB, TUNED_MARKER_RGB, PASSBAND_MARKER_RGB, (0, 0, 0)]
    assert image.rgb == b"\x00" * 5 * 2 * 3


def test_frequency_overlay_draws_cursor_after_tuned_marker():
    image = RasterImage(width=5, height=1, rgb=b"\x00" * 15)
    overlay = WaterfallOverlay(
        start_khz=100.0,
        end_khz=200.0,
        tuned_khz=150.0,
        cursor_khz=150.0,
    )

    rendered = apply_frequency_overlay(image, overlay)

    assert tuple(rendered.rgb[6:9]) == CURSOR_MARKER_RGB


def test_frequency_overlay_omits_markers_outside_visible_span():
    image = RasterImage(width=3, height=1, rgb=b"\x01" * 9)
    overlay = WaterfallOverlay(start_khz=100.0, end_khz=200.0, tuned_khz=300.0)

    assert apply_frequency_overlay(image, overlay) == image


def test_frequency_overlay_rejects_reversed_passband():
    with pytest.raises(ValueError, match="low_cut_hz"):
        WaterfallOverlay(
            start_khz=100.0,
            end_khz=200.0,
            tuned_khz=150.0,
            low_cut_hz=1000,
            high_cut_hz=-1000,
        )


def test_raster_rejects_non_rectangular_rows_and_invalid_scale():
    with pytest.raises(ValueError, match="rectangular"):
        render_dbm_rows(((-100, -50), (-80,)), min_dbm=-100, max_dbm=0)
    with pytest.raises(ValueError, match="greater"):
        dbm_to_rgb(-50, min_dbm=0, max_dbm=0)
