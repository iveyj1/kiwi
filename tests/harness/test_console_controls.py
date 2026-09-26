from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
from kiwi_client.integrated_terminal import (
    CW_BANDWIDTHS_HZ, run_fixture_shell, step_console_cw_bandwidth,
)
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.waterfall_levels import WaterfallLevelController

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def cw_model(low=600, high=1000):
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378, main_step_hz=100, small_step_hz=10)
    model.session.state = replace(model.session.state, mode='cw', low_cut_hz=low, high_cut_hz=high, frequency_decimals=4)
    return model


def test_bandwidth_ladder_preserves_center_and_tuning():
    model = cw_model()
    from kiwi_client.station_memory import passband_center_khz
    for expected in (100, 50, 30, 20, 10, 5, 2, 2):
        step_console_cw_bandwidth(model, -1)
        state = model.session.state
        assert state.high_cut_hz - state.low_cut_hz == expected
        assert state.high_cut_hz + state.low_cut_hz == (1601 if expected == 5 else 1600)
        assert passband_center_khz(state) == pytest.approx(378)
        assert state.frequency_khz == state.selected_khz == pytest.approx(378 - (0.0005 if expected == 5 else 0))
    for expected in (*CW_BANDWIDTHS_HZ[1:], 500):
        step_console_cw_bandwidth(model, 1)
        assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == expected
        assert passband_center_khz(model.session.state) == pytest.approx(378)


@pytest.mark.parametrize('low,high', [(650, 1050), (-1000, -600)])
def test_controller_bandwidth_uses_actual_center_and_existing_filter_command(low, high):
    controller = ClientController(state=ClientState(mode='cw', frequency_khz=378, low_cut_hz=low, high_cut_hz=high))
    model = cw_model(low, high)
    model.session = controller.paired_session
    step_console_cw_bandwidth(model, 1, controller)
    assert controller.state.high_cut_hz - controller.state.low_cut_hz == 500
    assert controller.state.high_cut_hz + controller.state.low_cut_hz == low + high
    assert model.session.state.high_cut_hz == controller.state.high_cut_hz
    assert controller.state.frequency_khz == 378


def test_non_cw_and_half_hz_center_with_coarse_precision():
    model = WaterfallGuiModel()
    original = model.session.state
    assert 'CW mode only' in step_console_cw_bandwidth(model, -1)
    assert model.session.state == original
    model = cw_model(600, 1001)
    model.session.state = replace(model.session.state, frequency_decimals=3)
    step_console_cw_bandwidth(model, -1)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 5
    original = model.session.state
    assert 'No centered step' in step_console_cw_bandwidth(model, -1)
    assert model.session.state == original


@pytest.mark.parametrize('key,frequency,width', [('h', 377.990, 400), ('l', 378.010, 400),
    ('H', 377.900, 400), ('L', 378.100, 400), ('j', 378, 100), ('k', 378, 500),
    ('n', 380, 400), ('N', 384, 400), ('v', 378, 400)])
def test_shell_key_bindings_and_section_text(monkeypatch, key, frequency, width):
    import kiwi_client.integrated_terminal as shell
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn = []

    class Screen:
        keys = iter([key, 'q'])
        def get_wch(self):
            return next(self.keys)
        def getmaxyx(self):
            return 40, 160
        def addnstr(self, row, column, text, *args):
            drawn.append(text)
        def __getattr__(self, name):
            return lambda *args: None

    class Presenter:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    model = cw_model()
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    run_fixture_shell(Screen(), model=model,
                      timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
                      live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
                      tui_controller=None, tui_config=None, source_fps=20, refresh_hz=1000,
                      scale_font_backend='bitmap', rna_browser=browser)
    assert model.session.state.frequency_khz == pytest.approx(frequency)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == width
    assert any('STATION / CATALOGUE' in row and 'RECEPTION / LOG' in row for row in drawn)
    assert any(row.startswith('╭') for row in drawn)
    assert any('h/l small H/L large j/k BW' in row for row in drawn)
