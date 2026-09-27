import io
import json
from pathlib import Path
import struct
import sys

import pytest

from kiwi_client import terminal_geometry
from kiwi_client.integrated_terminal import IntegratedTerminalLayout, KittyPanePresenter
from kiwi_client.waterfall_raster import RasterImage, resize_raster_nearest
from kiwi_client.waterfall_scale import (
    FrequencyAnnotation, ScalePaneTooSmall, STATION_MARKER_COLORS, compose_waterfall_scale, scale_text_renderer,
)

FIXTURES = Path(__file__).parents[1] / 'fixtures'
CASES = json.loads((FIXTURES / 'terminal/pixel-geometry.json').read_text())['cases']


def compose(width, height, *, backend='bitmap', font_scale=2, annotations=()):
    source = RasterImage(64, 12, bytes([12, 34, 56]) * 64 * 12)
    result = compose_waterfall_scale(source, 377.5, 378.5, tuned_khz=378.405, selected_khz=378.405,
        passband_reference_khz=377.605, low_cut_hz=600, high_cut_hz=1000, presets={},
        font_backend=backend, font_scale=font_scale, canvas_size=(width, height), annotations=annotations)
    assert source.rgb == bytes([12, 34, 56]) * 64 * 12
    assert result.image.rgb[:width * result.tuning_top * 3] == bytes([12, 34, 56]) * width * result.tuning_top
    return result


@pytest.mark.parametrize('case', CASES)
def test_terminal_pixel_fixture_and_exact_pane_dimensions(monkeypatch, case):
    monkeypatch.setattr(terminal_geometry.fcntl, 'ioctl', lambda *args: struct.pack('HHHH', *case['winsize']))
    cells = terminal_geometry.terminal_cell_pixels(case['columns'], case['lines'])
    assert (cells.width, cells.height) == tuple(case['cell'])
    assert cells.measured == case['measured']
    layout = IntegratedTerminalLayout.compute(columns=case['columns'], lines=case['lines'])
    size = layout.columns * cells.width, layout.waterfall_rows * cells.height
    result = compose(*size, font_scale=max(1, round(cells.height / 10)))
    assert (result.image.width, result.image.height) == size


def test_geometry_no_tty_and_descriptor_fallback(monkeypatch):
    def unavailable(*args):
        raise OSError('not a tty')
    monkeypatch.setattr(terminal_geometry.fcntl, 'ioctl', unavailable)
    assert terminal_geometry.terminal_cell_pixels(174, 40) == terminal_geometry.TerminalCellPixels()
    def stdin_tty(fd, *args):
        if fd != 0:
            raise OSError('not a tty')
        return struct.pack('HHHH', 40, 174, 1740, 800)
    monkeypatch.setattr(terminal_geometry.fcntl, 'ioctl', stdin_tty)
    assert terminal_geometry.terminal_cell_pixels(174, 40).measured
    with pytest.raises(ValueError):
        terminal_geometry.terminal_cell_pixels(0, 40)


def crop(image, left, top, width, height):
    return b''.join(image.rgb[((top + y) * image.width + left) * 3:((top + y) * image.width + left + width) * 3]
                    for y in range(height))


@pytest.mark.parametrize('backend', ['bitmap', 'pillow'])
def test_frequency_glyph_pixels_identical_at_80_and_174_columns(backend):
    if backend == 'pillow':
        pytest.importorskip('PIL')
    renderer = scale_text_renderer(backend, font_scale=2)
    label = '378.0'
    glyph_width = renderer.width(label)
    crops = []
    for width, height in ((800, 400), (1740, 400), (1740, 600)):
        result = compose(width, height, backend=backend)
        assert label in result.frequency_labels and result.font_scale == 2
        column = round(.5 * (width - 1))
        crops.append(crop(result.image, column - glyph_width // 2, result.tick_top + 6,
                          glyph_width, renderer.line_height))
    assert any(crops[0]) and all(value == crops[0] for value in crops)  # No horizontal or vertical text stretch.


@pytest.mark.parametrize('width,height', [(640, 320), (800, 400), (1740, 400), (1740, 500)])
def test_station_connectors_use_final_rf_columns_and_leave_history_clear(width, height):
    annotations = tuple(FrequencyAnnotation(f, label, kind, selected=kind == 'usb', station_selected=True)
        for f, label, kind in [(377.590, 'RJ:L', 'lsb'), (378, 'RJ:C', 'carrier'), (378.405, 'RJ:U', 'usb')])
    result = compose(width, height, annotations=annotations)
    for frequency, label, kind in [(377.590, 'RJ:L', 'lsb'), (378, 'RJ:C', 'carrier'), (378.405, 'RJ:U', 'usb')]:
        x = round((frequency - 377.5) * (width - 1))
        color = (255, 255, 255) if kind == 'usb' else STATION_MARKER_COLORS[kind]
        assert crop(result.image, x, result.station_stem_top, 1, 1) == bytes(color)
        assert crop(result.image, x, result.tuning_top, 1, 1) == bytes(color)
        assert any(value.startswith(label) for value in result.station_labels)
    assert result.station_stem_top > result.tuning_top


@pytest.mark.parametrize('target', [(2, 2), (8, 6), (1, 1), (7, 3)])
def test_nearest_resizing_pillow_and_dependency_free_paths_match(monkeypatch, target):
    pytest.importorskip('PIL')
    original = RasterImage(4, 3, bytes(range(36)))
    expected = resize_raster_nearest(original, *target)
    monkeypatch.setitem(sys.modules, 'PIL', None)
    assert resize_raster_nearest(original, *target) == expected
    assert original.rgb == bytes(range(36))
    assert resize_raster_nearest(original, 4, 3) is original
    with pytest.raises(ValueError):
        resize_raster_nearest(original, 0, 10)


def test_auto_font_and_resizer_work_without_pillow(monkeypatch):
    monkeypatch.setitem(sys.modules, 'PIL', None)
    result = compose(640, 320, backend='auto')
    assert result.text_backend == 'bitmap'
    assert (result.image.width, result.image.height) == (640, 320)


def test_short_pane_compacts_fonts_or_reports_insufficient_space():
    annotations = (FrequencyAnnotation(378, 'RJ:C', station_selected=True),)
    result = compose(320, 80, annotations=annotations)
    assert result.font_scale == 1 and result.image.height == 80 and result.tuning_top > 0
    with pytest.raises(ScalePaneTooSmall):
        compose(320, 30, annotations=annotations)
    with pytest.raises(ValueError, match='canvas'):
        compose(0, 400)


def test_shell_composes_native_pixels_on_resize_without_retuning(monkeypatch):
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
    from kiwi_client.waterfall_levels import WaterfallLevelController
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    monkeypatch.setattr(shell, 'terminal_cell_pixels', lambda *args: terminal_geometry.TerminalCellPixels(10, 20, True))
    class Screen:
        columns = 80
        keys = iter([None, shell.curses.KEY_RESIZE, None, 'q'])
        def get_wch(self):
            key = next(self.keys)
            if key == shell.curses.KEY_RESIZE:
                self.columns = 174
            return key
        def getmaxyx(self):
            return 40, self.columns
        def __getattr__(self, name):
            return lambda *args: None
    seen, frequencies = [], []
    class Presenter:
        def draw(self, image, layout, **kwargs):
            seen.append((image.width, image.height))
            frequencies.append(model.session.state.frequency_khz)
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    model = WaterfallGuiModel()
    shell.run_fixture_shell(Screen(), model=model,
        timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=None, tui_config=None, source_fps=20, refresh_hz=10000, scale_font_backend='bitmap')
    assert seen[0] == (800, 400) and (1740, 400) in seen
    assert len(set(frequencies)) == 1  # After normal fixture initialization, resize never retunes.
    assert model.session.state.frequency_khz == frequencies[0]


def test_presenter_repaints_pixel_metric_change_even_without_cell_or_frame_change():
    output = io.BytesIO()
    presenter = KittyPanePresenter(output=output, force=True)
    layout = IntegratedTerminalLayout.compute(columns=80, lines=40)
    first = compose(800, 400).image
    changed = compose(960, 480).image
    assert presenter.draw(first, layout, generation=1)
    assert not presenter.draw(first, layout, generation=1)
    assert presenter.draw(changed, layout, generation=1)
    assert not presenter.draw(changed, layout, generation=1)
    presenter.finish()
