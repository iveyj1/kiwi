import curses
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.config import load_config
from kiwi_client.console_panels import cell_width
from kiwi_client.receiver_popup import ReceiverPopup
from kiwi_client.gui_app import WaterfallGuiModel, FixtureWaterfallTimeline
from kiwi_client.waterfall_levels import WaterfallLevelController


@pytest.mark.parametrize('count', [0, 1, 3, 36])
@pytest.mark.parametrize('columns,height', [(40, 6), (80, 12), (174, 20)])
def test_popup_geometry_and_scrolling(count, columns, height):
    from kiwi_client.tui import REGISTER_KEYS
    entries = [(REGISTER_KEYS[i], f'fixture-{i}:8073', '広い description' * 20) for i in range(count)]
    popup = ReceiverPopup(entries, 'fixture-0:8073')
    initial = popup.lines(columns, height)
    popup.move(1000)
    rows = popup.lines(columns, height)
    assert len(rows) == len(initial) <= height
    assert all(cell_width(row) == min(78, columns - 2) for row in rows)
    if count:
        assert any(f'fixture-{count - 1}:8073' in row for row in rows)
        assert popup.selected_register == entries[-1][0]
    else:
        assert popup.selected_register is None
    popup.move(-1000)
    assert popup.index == 0


def test_picker_preserves_register_mapping_and_selects_current():
    config = load_config()
    controller = ClientController(state=ClientState(host='fixture-3'), receiver_presets={
        3: {'receiver': 'fixture-3:8073', 'description': 'three'},
        1: {'receiver': 'fixture-1:8073', 'description': 'one'}})
    popup = ReceiverPopup.open(config, controller)
    assert [entry[0] for entry in popup.entries] == ['1', '3']
    assert popup.selected_register == '3'
    assert '* 3 fixture-3:8073' in '\n'.join(popup.lines(100, 15))


@pytest.mark.parametrize('keys,expected', [
    (['r', curses.KEY_DOWN, '\n', 'q'], ['fixture-2:8073']),
    (['r', '2', 'q'], ['fixture-2:8073']),
    (['r', curses.KEY_DOWN, '\x1b', 'q'], []),
    (['r', '?', '\x1b', 'q'], []),
])
def test_shell_popup_routes_selection_and_cancellation(monkeypatch, keys, expected):
    import kiwi_client.integrated_terminal as shell
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    controller = ClientController(state=ClientState(host='fixture-1'), receiver_presets={
        i: {'receiver': f'fixture-{i}:8073', 'description': str(i)} for i in (1, 2, 3)})
    switched = []
    def switch(receiver, **kwargs):
        switched.append(receiver)
        return None, 'switched'
    monkeypatch.setattr(controller, 'switch_receiver', switch)
    drawn = []
    class Screen:
        inputs = iter([None, *keys])
        def get_wch(self):
            return next(self.inputs)
        def getmaxyx(self):
            return 40, 160
        def addnstr(self, row, col, text, *args):
            drawn.append((row, col, text))
        def __getattr__(self, name):
            return lambda *args: None
    class Presenter:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    model = WaterfallGuiModel()
    shell.run_fixture_shell(Screen(), model=model,
        timeline=FixtureWaterfallTimeline.from_fixture(Path('tests/fixtures/kiwi/local-wf-am-855-zoom7.jsonl')),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=controller, tui_config=load_config(), source_fps=20,
        refresh_hz=10000, scale_font_backend='bitmap')
    assert switched == expected
    overlay = [(row, col, text) for row, col, text in drawn if col > 0]
    assert any('Receivers' in text for _, _, text in overlay)
    assert all(row >= 20 for row, _, _ in overlay)
