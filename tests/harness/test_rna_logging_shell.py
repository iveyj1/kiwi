from pathlib import Path

import pytest

from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
from kiwi_client.integrated_terminal import run_fixture_shell
from kiwi_client.ndb_logbook import Logbook
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.waterfall_levels import WaterfallLevelController

FIXTURES = Path(__file__).parents[1] / 'fixtures'


@pytest.mark.parametrize('decision,status', [('y', 'confirmed'), ('t', 'tentative'), ('\x1b', None)])
def test_shell_logging_requires_explicit_decision_and_fixture_provenance(tmp_path, monkeypatch, decision, status):
    import kiwi_client.integrated_terminal as shell
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)

    class Screen:
        keys = iter(['y', 'w', '\n', decision, 'q'])
        def get_wch(self):
            return next(self.keys)
        def getmaxyx(self):
            return 40, 140
        def __getattr__(self, name):
            return lambda *args: None

    class Presenter:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    path = tmp_path / 'receptions.sqlite'
    run_fixture_shell(Screen(), model=model,
                      timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
                      live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
                      tui_controller=None, tui_config=None, source_fps=20, refresh_hz=1000,
                      scale_font_backend='bitmap', rna_browser=browser, logbook_path=path, log_event='CLE332')
    if status is None:
        assert not path.exists()
    else:
        with Logbook(path) as book:
            entries = book.entries()
        assert len(entries) == 1
        assert entries[0]['status'] == status
        assert entries[0]['source_kind'] == 'fixture'
        assert entries[0]['receiver'] == 'fixture'
        assert entries[0]['ident'] == 'RJ'
        assert entries[0]['event'] == 'CLE332'
