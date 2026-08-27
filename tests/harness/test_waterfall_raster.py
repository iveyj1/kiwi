import struct
import zlib

import pytest

from kiwi_client.waterfall import WaterfallFrame
from kiwi_client.waterfall_raster import (
    RasterImage,
    PASSBAND_MARKER_RGB,
    TUNED_MARKER_RGB,
    WaterfallHistory,
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


def test_dbm_to_rgb_is_deterministic_and_clamps():
    assert dbm_to_rgb(-200, min_dbm=-100, max_dbm=0) == (0, 0, 0)
    assert dbm_to_rgb(-100, min_dbm=-100, max_dbm=0) == (0, 0, 0)
    assert dbm_to_rgb(-50, min_dbm=-100, max_dbm=0) == (0, 255, 255)
    assert dbm_to_rgb(0, min_dbm=-100, max_dbm=0) == (255, 255, 255)
    assert dbm_to_rgb(20, min_dbm=-100, max_dbm=0) == (255, 255, 255)


def test_render_rows_and_dependency_free_png_encoding():
    image = render_dbm_rows(((-100, -50, 0),), min_dbm=-100, max_dbm=0)

    assert image == RasterImage(
        width=3,
        height=1,
        rgb=bytes((0, 0, 0, 0, 255, 255, 255, 255, 255)),
    )

    png = encode_png(image)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", png[16:24]) == (3, 1)

    idat_start = png.index(b"IDAT")
    idat_length = struct.unpack(">I", png[idat_start - 4:idat_start])[0]
    scanline = zlib.decompress(png[idat_start + 4:idat_start + 4 + idat_length])
    assert scanline == b"\x00" + image.rgb


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
