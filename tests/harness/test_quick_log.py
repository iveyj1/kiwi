from pathlib import Path
import json

import pytest

from kiwi_client.console_panels import cell_width, main_panel_rows
from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
from kiwi_client.integrated_terminal import run_fixture_shell, tune_rna_component
from kiwi_client.ndb_logbook import Logbook
from kiwi_client.quick_log import QuickLogEntry
from kiwi_client.reception_ui import quick_log_line
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.waterfall_levels import WaterfallLevelController

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def setup():
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    browser.set_receiver('fixture', 378)
    tune_rna_component(browser, model)
    return browser, model


def entry(browser, model, existing=None):
    return QuickLogEntry.open(browser, model.session.state, receiver='fixture',
                              source_kind='fixture', event='CLE332', existing=existing)


def test_quick_draft_freezes_new_evidence_and_defaults_confirmed(tmp_path):
    browser, model = setup()
    draft = entry(browser, model)
    original = dict(draft.draft)
    browser.move(1)
    model.set_tuned_frequency(380)
    draft.draft['notes'] = 'weak but complete ID'
    draft.save(tmp_path / 'log.sqlite')
    with Logbook(tmp_path / 'log.sqlite') as book:
        saved = book.entries()[0]
    assert saved['status'] == 'confirmed'
    for key in ('heard_utc', 'ident', 'tuned_khz', 'rf_center_khz', 'component', 'bandwidth_hz'):
        assert saved[key] == original[key]
    assert saved['notes'] == 'weak but complete ID'


def test_update_retains_tentative_time_and_evidence_and_checks_stale_record(tmp_path):
    browser, model = setup()
    first = entry(browser, model)
    first.toggle_status()
    first.draft['heard_utc'] = '2026-01-01T01:02:03+00:00'
    path = tmp_path / 'log.sqlite'
    first.save(path)
    with Logbook(path) as book: original = book.entries()[0]
    update = entry(browser, model, original)
    assert update.draft['status'] == 'tentative'
    update.draft['notes'] = 'better copy'
    update.save(path)
    with Logbook(path) as book:
        after = book.entries()[0]
    assert after['heard_utc'] == original['heard_utc']
    assert after['tuned_khz'] == original['tuned_khz']
    assert after['status'] == 'tentative'
    assert original['notes'] == ''  # editing never mutates the expected snapshot
    with pytest.raises(ValueError, match='changed'): update.save(path)
    fresh = entry(browser, model, after)
    fresh.toggle_status()
    assert fresh.draft['status'] == 'confirmed'


def test_guard_rejects_mismatched_selection_even_for_existing_entry():
    browser, model = setup()
    old = entry(browser, model).draft | {'log_id': 1}
    model.set_tuned_frequency(400)
    with pytest.raises(ValueError, match='tune the selected'): entry(browser, model, old)


@pytest.mark.parametrize('columns', [40, 80, 174])
@pytest.mark.parametrize('height', [5, 9, 12, 19])
def test_inline_layout_keeps_status_and_note_tail(columns, height):
    browser, model = setup()
    draft = entry(browser, model)
    draft.toggle_status()
    draft.draft['notes'] = '東京 ' * 200
    line = quick_log_line(draft.draft, columns - 5)
    assert 'NEW RJ' in line and 'TENTATIVE' in line and line.rstrip().endswith('_')
    rows = main_panel_rows(columns=columns, height=height, radio='CW', station=['RJ'],
                          reception=['NO'], filters='all', help_rows=['Tab status Enter save'],
                          message='failed write', log_line=line)
    assert len(rows) <= height
    assert all(cell_width(row) == columns - 1 for row in rows)
    active = next(i for i, row in enumerate(rows) if 'LOG NEW' in row)
    if any(' KEYS ' in row for row in rows):
        assert active < next(i for i, row in enumerate(rows) if ' KEYS ' in row)
    assert any('failed write' in row for row in rows)


def shell_run(tmp_path, monkeypatch, keys):
    import kiwi_client.integrated_terminal as shell
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn, images = [], []
    sequence = iter(keys)

    class Screen:
        last_key = None
        def get_wch(self):
            self.last_key = next(sequence)
            return self.last_key
        def getmaxyx(self): return 40, 174
        def addnstr(self, row, column, text, *args): drawn.append(text)
        def __getattr__(self, name): return lambda *args: None

    screen = Screen()

    class Presenter:
        def draw(self, *args, **kwargs): images.append(screen.last_key)
        def __getattr__(self, name): return lambda *args, **kwargs: None

    browser, model = setup()
    model.load_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl')
    model.display_frequency_range()  # initialize fixture mapping before selecting a view
    model.recenter()
    assert model.display_frequency_range()[0] < 380 < 384 < model.display_frequency_range()[1]
    path = tmp_path / 'log.sqlite'
    run_fixture_shell(screen, model=model,
        timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=None, tui_config=None, source_fps=20, refresh_hz=1000,
        scale_font_backend='bitmap', rna_browser=browser, logbook_path=path, log_event='CLE332')
    return path, browser, model, drawn, images


@pytest.mark.parametrize('keys,status,notes', [
    (case['keys'], case['status'], case['notes'])
    for case in json.loads((FIXTURES / 'terminal/quick-log.json').read_text())
])
def test_inline_keys_keep_waterfall_and_do_not_trigger_radio_shortcuts(tmp_path, monkeypatch, keys, status, notes):
    path, browser, model, drawn, images = shell_run(tmp_path, monkeypatch, keys)
    assert 'w' in images  # main-page waterfall is still presented during entry
    assert any('LOG NEW RJ' in row for row in drawn)
    assert any('Tab status' in row for row in drawn)
    assert browser.selected.station.ident == 'RJ' and model.session.state.frequency_khz == pytest.approx(378.405)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 400
    assert not model.session.state.audio_enabled
    if status is None:
        assert not path.exists()
    else:
        with Logbook(path) as book: records = book.entries()
        assert len(records) == 1 and records[0]['status'] == status
        assert records[0]['notes'] == notes and records[0]['source_kind'] == 'fixture'


def test_w_updates_and_W_creates_repeat_without_promoting_tentative(tmp_path, monkeypatch):
    path, _, _, rows, _ = shell_run(tmp_path, monkeypatch,
        ['w', '\t', '\n', 'w', 'x', '\n', 'W', '\n', 'q'])
    with Logbook(path) as book: records = book.entries()
    assert len(records) == 2
    assert records[0]['status'] == 'tentative' and records[0]['notes'] == 'x'
    assert records[1]['status'] == 'confirmed'
    assert any('LOG UPDATE' in row for row in rows)


def test_escape_on_existing_leaves_it_unchanged_and_f2_keeps_draft(tmp_path, monkeypatch):
    import curses
    path, _, _, _, _ = shell_run(tmp_path, monkeypatch,
        ['w', '\n', 'w', 'x', '\t', '\x1b', 'W', 'z', curses.KEY_F2, '\n', 'n', 'q'])
    with Logbook(path) as book: records = book.entries()
    assert len(records) == 2
    assert records[0]['status'] == 'confirmed' and records[0]['notes'] == ''
    assert records[1]['status'] == 'not-heard' and records[1]['notes'] == 'z'


@pytest.mark.parametrize('key,frequency', [('n', 380), ('N', 384)])
def test_catalogue_steps_center_even_inside_current_view(tmp_path, monkeypatch, key, frequency):
    _, _, model, _, _ = shell_run(tmp_path, monkeypatch, [key, 'q'])
    assert model.session.state.frequency_khz == frequency
    assert model.session.state.selected_khz == frequency
    assert model.session.state.waterfall_center_khz == frequency


def test_save_error_retains_inline_draft_for_retry(tmp_path, monkeypatch):
    original = QuickLogEntry.save
    attempts = []
    def save(self, path):
        attempts.append(dict(self.draft))
        if len(attempts) == 1:
            raise OSError('synthetic disk failure')
        return original(self, path)
    monkeypatch.setattr(QuickLogEntry, 'save', save)
    path, _, _, rows, _ = shell_run(tmp_path, monkeypatch, ['w', 'x', '\t', '\n', '\n', 'q'])
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert any('log NOT saved' in row for row in rows)
    with Logbook(path) as book: records = book.entries()
    assert len(records) == 1 and records[0]['status'] == 'tentative' and records[0]['notes'] == 'x'


def test_center_initializes_fixture_mapping_before_centering():
    browser, model = setup()
    model.load_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl')
    browser.move(1)
    tune_rna_component(browser, model, center=True)
    start, end = model.display_frequency_range()
    assert (start + end) / 2 == pytest.approx(model.session.state.selected_khz)


def test_center_supersedes_pending_view():
    browser, model = setup()
    model.publisher.expect_view(378, 7)
    browser.move(1)
    tune_rna_component(browser, model, center=True)
    assert model.session.state.waterfall_center_khz == 380
