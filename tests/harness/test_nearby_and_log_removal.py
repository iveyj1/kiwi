import json

import pytest

from kiwi_client.ndb_logbook import Logbook, cle332_report
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser


@pytest.fixture
def nearby(tmp_path):
    path = tmp_path / 'near.csv'
    path.write_text('KHz,ID,Type,Active,LSB,USB\n'
                    '300,AA,NDB,Y,,\n'
                    '299.69,BB,NDB,Y,,400\n'
                    '300.18,CC,NDB,Y,,\n'
                    '400,DD,NDB,Y,,\n')
    browser = RnaBrowser(load_catalogue(path), near_radius_hz=100)
    browser.set_receiver('fixture', 300)
    return browser


def test_nearby_uses_components_groups_stations_and_fixed_anchor(nearby):
    hits = nearby.nearby_components(300)
    assert [(m.station.ident, c.kind) for m, c in hits] == [('AA', 'carrier'), ('BB', 'usb')]
    nearby.cycle_nearby(300, 1)
    assert nearby.selected.station.ident == 'BB' and nearby.component.kind == 'usb'
    nearby.nearby_tuned(300.09)
    # Do not walk towards CC at 300.18 just because the last choice retuned to BB.
    nearby.cycle_nearby(300.09, 1)
    assert nearby.selected.station.ident == 'AA'
    nearby.nearby_tuned(300)
    nearby.cycle_nearby(300, -1)
    assert nearby.selected.station.ident == 'BB'
    nearby.nearby_tuned(300.09)
    # Manual tuning away starts a fresh neighborhood.
    nearby.cycle_nearby(300.18, 1)
    assert nearby.selected.station.ident == 'CC'


def test_near_radius_validation_filter_reset_and_stored_component(nearby):
    station = next(m.station for m in nearby.matches if m.station.ident == 'DD')
    nearby.memory.update(station.key, dict(choice='stored', stored=dict(carrier_khz=400, offset_hz=-99950, bandwidth_hz=50)))
    assert any(m.station.ident == 'DD' and c.kind == 'stored' for m, c in nearby.nearby_components(300))
    nearby.command('rna near 50', 300)
    assert {m.station.ident for m, _ in nearby.nearby_components(300)} == {'AA', 'DD'}
    for value in ('nan', '-1', 'inf'):
        with pytest.raises(ValueError):
            nearby.command('rna near ' + value, 300)
        assert nearby.near_radius_hz == 50
    nearby.command('rna search BB', 300)
    with pytest.raises(ValueError, match='filters apply'):
        nearby.cycle_nearby(300, 1)


def test_nearby_shell_keys_tune_matching_sideband(nearby, monkeypatch):
    from dataclasses import replace
    from pathlib import Path
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.gui_app import WaterfallGuiModel, FixtureWaterfallTimeline
    from kiwi_client.waterfall_levels import WaterfallLevelController
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    class Screen:
        keys = iter('..,q')
        def get_wch(self): return next(self.keys)
        def getmaxyx(self): return 40, 160
        def __getattr__(self, name): return lambda *args: None
    class Presenter:
        def __getattr__(self, name): return lambda *args, **kwargs: None
    model = WaterfallGuiModel(tuned_khz=300, selected_khz=300)
    model.session.state = replace(model.session.state, mode='cw', low_cut_hz=600, high_cut_hz=1000)
    fixture = Path(__file__).parents[1] / 'fixtures/kiwi/local-wf-am-855-zoom7.jsonl'
    shell.run_fixture_shell(Screen(), model=model, timeline=FixtureWaterfallTimeline.from_fixture(fixture, repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(), tui_controller=None,
        tui_config=None, source_fps=20, refresh_hz=1000, scale_font_backend='bitmap', rna_browser=nearby)
    assert nearby.selected.station.ident == 'BB'
    assert nearby.component.kind == 'usb'
    assert model.session.state.frequency_khz == pytest.approx(300.09)
    assert nearby._near_anchor == 300


@pytest.fixture
def reception():
    return dict(schema=1, status='confirmed', source_kind='live', event='CLE332',
                heard_utc='2026-09-26T01:00:00Z', receiver='test', station_key='PH332', ident='PH',
                catalogue_sha256='fixture', carrier_khz=332, component_khz=333.035, tuned_khz=333.035,
                mode='cw', low_cut_hz=600, high_cut_hz=1000, cw_offset_hz=-800,
                catalogue_fields={}, notes='')


def test_not_heard_excluded_and_delete_audited_without_id_reuse(tmp_path, reception):
    profile = dict(listener='Test', receiver='test', timezone='UTC', locator='FN25aa', location='Test',
                   equipment='KiwiSDR', aerial='loop', remote=False, public=False)
    with Logbook(tmp_path / 'logs.sqlite') as book:
        key, _ = book.save(reception)
        book.revise(key, status='not-heard')
        with pytest.raises(ValueError, match='no eligible'):
            cle332_report(book.entries(), profile)
        original = book.entries()[0]
        book.delete(key, expected=original)
        assert book.entries() == []
        audit = json.loads(book.connection.execute('SELECT payload FROM revisions ORDER BY id DESC LIMIT 1').fetchone()[0])
        assert audit['status'] == 'not-heard' and 'deleted_utc' in audit
        assert book.save(reception)[0] > key


def test_cli_not_heard_and_explicit_delete_confirmation(tmp_path, reception):
    from kiwi_client.ndb_logbook import main
    path = tmp_path / 'logs.sqlite'
    with Logbook(path) as book:
        key, _ = book.save(reception)
    base = ['--logbook', str(path)]
    assert main(base + ['edit', str(key), '--status', 'not-heard']) == 0
    with pytest.raises(SystemExit):
        main(base + ['delete', str(key)])
    with Logbook(path) as book:
        assert book.entries()[0]['status'] == 'not-heard'
    assert main(base + ['delete', str(key), '--yes']) == 0
    with Logbook(path) as book:
        assert book.entries() == []


def test_delete_conflict_and_audit_failure_rollback(tmp_path, reception, monkeypatch):
    with Logbook(tmp_path / 'logs.sqlite') as book:
        key, _ = book.save(reception)
        original = book.entries()[0]
        book.revise(key, notes='external edit')
        with pytest.raises(ValueError, match='changed since'):
            book.delete(key, expected=original)
        def fail(*args):
            raise RuntimeError('audit failure')
        monkeypatch.setattr(book, '_audit', fail)
        with pytest.raises(RuntimeError):
            book.delete(key)
        assert book.entries()[0]['notes'] == 'external edit'
