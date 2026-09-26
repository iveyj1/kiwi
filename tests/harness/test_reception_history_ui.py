from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.gui_app import WaterfallGuiModel, FixtureWaterfallTimeline
from kiwi_client.ndb_logbook import Logbook, reception_draft
from kiwi_client.reception_ui import ReceptionIndex, logging_panel_rows
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser, CallsignSearchPage
from kiwi_client.integrated_terminal import tune_rna_component

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def sample():
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    browser.set_receiver('fixture', 378)
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    tune_rna_component(browser, model)
    record = reception_draft(browser, model.session.state, receiver='fixture', source_kind='fixture',
                             event='CLE332', heard_utc='2026-09-26T01:02:03Z')
    return browser, model, record


def test_read_only_history_scope_latest_time_and_confirmed_status(tmp_path):
    browser, model, record = sample()
    path = tmp_path / 'logs.sqlite'
    index = ReceptionIndex(path)
    index.refresh()
    assert not path.exists()
    key = (record['station_key'], 'fixture', 'CLE332', 'fixture')
    assert 'NOT LOGGED' in index.status(*key)
    with Logbook(path) as book:
        book.save(dict(record, status='confirmed'))
        book.save(dict(record, receiver='another'))
        book.save(dict(record, event=None))
        book.save(dict(record, source_kind='live'))
        book.save(dict(record, heard_utc='2026-09-26T02:02:03Z', notes='newer'))
        book.save(dict(record, heard_utc='2026-09-26T00:00:00Z'))
    before = path.read_bytes()
    index.refresh()
    assert path.read_bytes() == before
    assert len(index.matching(*key)) == 3
    assert index.latest(*key)['notes'] == 'newer'  # not the last inserted row
    status = index.status(*key)
    assert 'TENTATIVE 2026-09-26 02:02:03Z' in status
    assert 'last CONFIRMED 2026-09-26 01:02:03Z' in status
    page = CallsignSearchPage(browser, 'RJ', log_status=lambda station_key: index.status(station_key, *key[1:]))
    assert any('TENTATIVE 2026-09-26' in row for row in page.rows(20))
    with Logbook(path) as book:
        book.revise(5, status='confirmed')
    index.refresh()
    assert index.status(*key).startswith('CONFIRMED 2026-09-26 02:02:03Z')


def test_broken_history_is_unavailable_not_not_logged(tmp_path):
    path = tmp_path / 'bad.sqlite'
    path.write_text('not a database')
    index = ReceptionIndex(path)
    index.refresh()
    assert index.error
    assert 'unavailable' in index.status('x', 'rx', None, 'live')
    with pytest.raises(ValueError):
        index.latest('x', 'rx', None, 'live')
    assert path.read_text() == 'not a database'


def test_optimistic_revision_preserves_external_edits(tmp_path):
    record = sample()[2]
    with Logbook(tmp_path / 'logs.sqlite') as book:
        key, _ = book.save(record)
        original = book.entries()[0]
        book.revise(key, notes='external change')
        with pytest.raises(ValueError, match='changed since'):
            book.revise(key, notes='stale UI', expected=original)
        assert book.entries()[0]['notes'] == 'external change'


@pytest.mark.parametrize('action,expected_count,expected_status', [('edit', 1, 'tentative'), ('cancel', 1, 'confirmed'), ('new', 2, 'confirmed')])
def test_shell_w_edits_existing_without_retune_W_creates_repeat(tmp_path, monkeypatch, action, expected_count, expected_status):
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.waterfall_levels import WaterfallLevelController
    browser, model, record = sample()
    path = tmp_path / 'logs.sqlite'
    original = dict(record, status='confirmed', notes='original note')
    with Logbook(path) as book:
        book.save(original)
    if action != 'new':
        model.session.state = replace(model.session.state, frequency_khz=390)  # old edit need not retune
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn = []
    sequences = {'edit': [None, 'w', '\n', 't', 'q'], 'cancel': [None, 'w', '\x1b', 'q'], 'new': [None, 'W', '\n', 'y', 'q']}

    class Screen:
        keys = iter(sequences[action])
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

    shell.run_fixture_shell(Screen(), model=model,
        timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=None, tui_config=None, source_fps=20, refresh_hz=10000, scale_font_backend='bitmap',
        rna_browser=browser, logbook_path=path, log_event='CLE332')
    with Logbook(path) as book:
        entries = book.entries()
        revisions = book.connection.execute('SELECT count(*) FROM revisions').fetchone()[0]
    assert len(entries) == expected_count
    assert entries[0]['status'] == expected_status
    assert entries[0]['tuned_khz'] == original['tuned_khz']
    assert entries[0]['notes'] == 'original note'
    assert revisions == (1 if action == 'cancel' else 2)
    assert any('CONFIRMED 2026-09-26 01:02:03Z' in line for line in drawn)
    assert any(('NEW RECEPTION' if action == 'new' else 'EDIT LOG #1') in line for line in drawn)
    if action == 'edit':
        assert any('TENTATIVE' in line for line in drawn)


def test_logging_panel_identifies_frozen_record_and_edit_mode():
    record = dict(sample()[2], log_id=17)
    rows = logging_panel_rows(record, prompt='time | notes', message='test', history='CONFIRMED yesterday')
    assert 'EDIT LOG #17' in rows[0]
    assert any('SNAPSHOT center' in row for row in rows)
    assert any('CONFIRMED yesterday' in row for row in rows)
