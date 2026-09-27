from pathlib import Path

from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.waterfall_raster import RasterImage
from kiwi_client.waterfall_scale import FrequencyAnnotation, STATION_MARKER_COLORS, compose_waterfall_scale

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def browser():
    result = RnaBrowser(load_catalogue(FIXTURE))
    result.set_receiver('fixture', 378)
    return result


def compose(annotations, start=377.5, end=378.5, width=1001):
    original = RasterImage(width, 12, b'\0' * (width * 12 * 3))
    result = compose_waterfall_scale(original, start, end, tuned_khz=378.405, selected_khz=378.405,
                                    passband_reference_khz=377.605, low_cut_hz=600, high_cut_hz=1000,
                                    presets={}, annotations=annotations, font_backend='bitmap', font_scale=1)
    assert original.rgb == b'\0' * (width * 12 * 3)
    return result


def pixel(image, x, y):
    index = (y * image.width + x) * 3
    return tuple(image.rgb[index:index + 3])


def test_selected_station_marks_asymmetric_components_at_rf_not_cw_reference():
    b = browser()
    annotations = b.annotations(377.5, 378.5)
    assert len([a for a in annotations if a.station_selected]) == 3
    assert len([a for a in annotations if a.selected]) == 1
    result = compose(annotations)
    assert result.station_stem_top is not None
    assert set(result.station_labels) == {'RJ:C 378.0000', 'RJ:L 377.5900', 'RJ:U 378.4050'}
    for x, color in [(90, STATION_MARKER_COLORS['lsb']), (500, STATION_MARKER_COLORS['carrier']), (905, (255, 255, 255))]:
        assert pixel(result.image, x, 0) == color
        assert pixel(result.image, x, 1) == color
        assert pixel(result.image, x, 2) == (0, 0, 0)  # Dashed, not an opaque vertical stripe.
        assert pixel(result.image, x, 6) == color
        assert pixel(result.image, x, result.station_stem_top) == color
    assert pixel(result.image, 105, 0) == (0, 0, 0)  # 377.605 CW reference is not an RNA component.


def test_other_catalogue_labels_cannot_hide_selected_station_row():
    b = browser()
    crowd = tuple(FrequencyAnnotation(378 + i * .001, f'OTHER{i}') for i in range(-15, 16))
    result = compose(b.annotations(377.5, 378.5) + crowd)
    assert 'RJ:C 378.0000' in result.station_labels
    assert all(label.startswith('RJ:') for label in result.station_labels)
    assert pixel(result.image, 500, 0) == STATION_MARKER_COLORS['carrier']


def test_unknown_offsets_and_offscreen_components_are_not_invented():
    b = browser()
    b.move(1)  # UNK at 380, with no sideband offsets.
    focused = [a for a in b.annotations(379, 381) if a.station_selected]
    assert [(a.kind, a.frequency_khz) for a in focused] == [('carrier', 380)]
    b.move(-1)
    result = compose(b.annotations(378.3, 378.5), start=378.3, end=378.5)
    assert result.station_labels == ('RJ:U 378.4050',)
    assert pixel(result.image, 0, 0) == pixel(result.image, 1000, 0) == (0, 0, 0)
    offscreen = compose((FrequencyAnnotation(999, 'OFF', station_selected=True),))
    assert offscreen.station_stem_top is None and not offscreen.station_labels


def test_stored_marker_and_component_switch_keep_all_station_guides():
    b = browser()
    key = b.selected.station.key
    b.memory.update(key, dict(choice='stored', stored=dict(carrier_khz=378, offset_hz=425.5, bandwidth_hz=5)))
    stored_column = round((378.4255 - 377.5) * 1000)
    result = compose(b.annotations(377.5, 378.5))
    assert 'RJ:S 378.4255' in result.station_labels
    assert pixel(result.image, stored_column, 0) == (255, 255, 255)
    assert pixel(result.image, 905, 0) == STATION_MARKER_COLORS['usb']
    b.cycle_component()  # stored -> carrier
    result = compose(b.annotations(377.5, 378.5))
    assert pixel(result.image, 500, 0) == (255, 255, 255)
    assert pixel(result.image, stored_column, 0) == STATION_MARKER_COLORS['stored']
    b.move(1)
    assert not any(a.station_selected for a in b.annotations(377.5, 378.5))
    result = compose(b.annotations(377.5, 378.5))
    assert result.station_stem_top is None
    assert pixel(result.image, 500, 0) == (0, 0, 0)


def test_same_pixel_active_marker_wins_and_labels_still_clip_safely():
    annotations = (FrequencyAnnotation(378, 'A:C', station_selected=True),
                   FrequencyAnnotation(378, 'A:U', 'usb', selected=True, station_selected=True))
    result = compose(annotations, width=12)
    x = round(.5 * 11)
    assert pixel(result.image, x, 0) == (255, 255, 255)
    assert result.station_labels == ('A:U 378.0000',)
    assert len(result.image.rgb) == result.image.width * result.image.height * 3
