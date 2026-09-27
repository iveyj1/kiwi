from pathlib import Path

from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.waterfall_raster import RasterImage
from kiwi_client.waterfall_scale import FrequencyAnnotation, STATION_MARKER_COLORS, STATION_BAR_RGB, compose_waterfall_scale

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
    assert result.image.rgb[:len(original.rgb)] == original.rgb  # No lines inside the waterfall.
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
    assert set(result.station_labels) == {'RJ', '378.000 c', '377.590', '378.405'}
    for x, color in [(90, STATION_MARKER_COLORS['lsb']), (500, STATION_MARKER_COLORS['carrier']), (905, (255, 255, 255))]:
        assert pixel(result.image, x, 12) == color
        assert pixel(result.image, x, 13) == (0, 0, 0)  # Dots confined to the footer.
        assert pixel(result.image, x, 15) == color
        assert pixel(result.image, x, result.station_stem_top) == color
    assert result.tick_top < result.station_stem_top < result.preset_stem_top
    assert all(pixel(result.image, x, result.station_stem_top) == STATION_BAR_RGB for x in range(94, 498))
    plain = compose(())
    assert {x for x in range(1001) if pixel(result.image, x, 12) != pixel(plain.image, x, 12)} == {90, 500, 905}


def test_other_catalogue_labels_cannot_hide_selected_station_row():
    b = browser()
    crowd = tuple(FrequencyAnnotation(378 + i * .001, f'OTHER{i}') for i in range(-15, 16))
    result = compose(b.annotations(377.5, 378.5) + crowd)
    assert '378.000 c' in result.station_labels
    assert result.station_labels.count('RJ') == 1
    assert not any('OTHER' in label for label in result.station_labels)
    assert pixel(result.image, 500, 12) == STATION_MARKER_COLORS['carrier']


def test_unknown_offsets_and_offscreen_components_are_not_invented():
    b = browser()
    b.move(1)  # UNK at 380, with no sideband offsets.
    focused = [a for a in b.annotations(379, 381) if a.station_selected]
    assert [(a.kind, a.frequency_khz) for a in focused] == [('carrier', 380)]
    b.move(-1)
    result = compose(b.annotations(378.3, 378.5), start=378.3, end=378.5)
    assert result.station_labels == ('RJ', '378.405')
    assert pixel(result.image, 0, 0) == pixel(result.image, 1000, 0) == (0, 0, 0)
    offscreen = compose((FrequencyAnnotation(999, 'OFF', station_selected=True),))
    assert offscreen.station_stem_top is None and not offscreen.station_labels


def test_stored_marker_and_component_switch_keep_all_station_guides():
    b = browser()
    key = b.selected.station.key
    b.memory.update(key, dict(choice='stored', stored=dict(carrier_khz=378, offset_hz=425.5, bandwidth_hz=5)))
    stored_column = round((378.4255 - 377.5) * 1000)
    result = compose(b.annotations(377.5, 378.5))
    assert f'{378.4255:.3f}' in result.station_labels
    assert b.component.frequency_khz == 378.4255  # Only label precision changes.
    assert pixel(result.image, stored_column, result.station_stem_top) == (255, 255, 255)
    assert pixel(result.image, stored_column, 12) == pixel(compose(()).image, stored_column, 12)  # No fourth connector.
    assert pixel(result.image, 905, 12) == STATION_MARKER_COLORS['usb']
    b.cycle_component()  # stored -> carrier
    result = compose(b.annotations(377.5, 378.5))
    assert pixel(result.image, 500, 12) == (255, 255, 255)
    assert pixel(result.image, stored_column, result.station_stem_top) == STATION_MARKER_COLORS['stored']
    b.move(1)
    assert not any(a.station_selected and 377.5 <= a.frequency_khz <= 378.5 for a in b.annotations(377.5, 378.5))
    result = compose(b.annotations(377.5, 378.5))
    assert result.station_stem_top is None
    assert pixel(result.image, 500, 0) == (0, 0, 0)


def test_clipped_station_span_has_no_fake_edge_connectors():
    b = browser()
    start, end = 378.1, 378.2  # Between carrier and USB; no component is in view.
    result = compose(b.annotations(start, end), start=start, end=end)
    plain = compose((), start=start, end=end)
    assert result.station_stem_top is not None and result.station_labels == ('RJ',)
    assert all(pixel(result.image, x, result.station_stem_top) == STATION_BAR_RGB for x in range(1001))
    assert all(pixel(result.image, x, 12) == pixel(plain.image, x, 12) for x in range(1001))


def test_identifier_is_drawn_once_at_left_and_only_carrier_is_tagged(monkeypatch):
    import kiwi_client.waterfall_scale as scale
    renderer = scale.scale_text_renderer('bitmap', font_scale=1)
    draw = renderer.render
    labels = []
    def capture(rgb, width, height, text):
        labels.extend(text)
        return draw(rgb, width, height, text)
    monkeypatch.setattr(renderer, 'render', capture)
    monkeypatch.setattr(scale, 'scale_text_renderer', lambda *args, **kwargs: renderer)
    result = compose(browser().annotations(377.5, 378.5))
    assert sum(text == 'RJ' for _, _, text, _ in labels) == 1
    assert not any(text.startswith('RJ:') for _, _, text, _ in labels)
    ident = next(item for item in labels if item[2] == 'RJ')
    assert ident[:2] == (0, result.station_stem_top + 6)
    assert {text for _, y, text, _ in labels if y == ident[1]} == {'RJ', '377.590', '378.000 c', '378.405'}


def test_carrier_at_left_edge_and_coincident_sideband_keep_carrier_tag():
    annotations = (FrequencyAnnotation(378, 'RJ:C', station_selected=True),
                   FrequencyAnnotation(378, 'RJ:U', 'usb', selected=True, station_selected=True))
    result = compose(annotations, start=378, end=379, width=160)
    assert result.station_labels == ('RJ', '378.000 c')
    assert pixel(result.image, 0, result.station_stem_top) == (255, 255, 255)


def test_same_pixel_active_marker_wins_and_labels_still_clip_safely():
    annotations = (FrequencyAnnotation(378, 'A:C', station_selected=True),
                   FrequencyAnnotation(378, 'A:U', 'usb', selected=True, station_selected=True))
    result = compose(annotations, width=12)
    x = round(.5 * 11)
    assert pixel(result.image, x, 12) == (255, 255, 255)
    assert result.station_labels == ('A',)  # Tiny viewport keeps ID and stems, not a clipped frequency.
    assert len(result.image.rgb) == result.image.width * result.image.height * 3
