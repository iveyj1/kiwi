import json
from pathlib import Path

from kiwi_client.waterfall_raster import RasterImage
from kiwi_client.waterfall_scale import compose_waterfall_scale, PASSBAND_SCALE_RGB

DATA = json.loads(Path('tests/fixtures/terminal/ndb-shading.json').read_text())


def render(enabled=True, **kwargs):
    options = dict(tuned_khz=290, selected_khz=290, low_cut_hz=-50,
                   high_cut_hz=50, presets={}, font_backend='bitmap', font_scale=1,
                   shade_ndb_regions=enabled)
    options.update(kwargs)
    return compose_waterfall_scale(RasterImage(1001, 2, bytes([11, 22, 33]) * 2002),
                                   DATA['start_khz'], DATA['end_khz'], **options).image


def pixel(image, x, y):
    i = (y * image.width + x) * 3
    return tuple(image.rgb[i:i + 3])


def test_shading_boundaries_and_history_unchanged():
    image = render()
    plain = render(False)
    assert image.rgb[:1001 * 2 * 3] == plain.rgb[:1001 * 2 * 3]
    assert image.rgb[1001 * 10 * 3:] == plain.rgb[1001 * 10 * 3:]
    for y in range(2, 10):
        for x in DATA['shaded_columns']:
            assert pixel(image, x, y) == (24, 24, 24)
        for x in DATA['unshaded_columns']:
            assert pixel(image, x, y) == (0, 0, 0)


def test_passband_stays_above_shading():
    image = render(tuned_khz=300.4, selected_khz=300.4)
    assert pixel(image, 400, 4) == PASSBAND_SCALE_RGB


def test_native_canvas_geometry_and_unresolved_guides():
    image = render(canvas_size=(501, 100))
    plain = render(False, canvas_size=(501, 100))
    changed = [i for i in range(0, len(image.rgb), 3) if image.rgb[i:i+3] != plain.rgb[i:i+3]]
    assert changed
    for i in changed:
        x = (i // 3) % 501
        hz = x * 2
        assert hz <= 100 or 350 <= hz <= 450 or 550 <= hz <= 650 or hz >= 900
    options = dict(tuned_khz=-1, selected_khz=-1, low_cut_hz=0, high_cut_hz=0,
                   presets={}, font_backend='bitmap', font_scale=1)
    waterfall = RasterImage(100, 2, bytes(600))
    assert compose_waterfall_scale(waterfall, 0, 30000, shade_ndb_regions=True, **options).image == compose_waterfall_scale(waterfall, 0, 30000, **options).image
