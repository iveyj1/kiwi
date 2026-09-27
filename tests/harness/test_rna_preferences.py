import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from kiwi_client.rna_catalogue import CatalogueFilter
from kiwi_client.rna_console import add_rna_arguments, browser_from_args

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'


def arguments(tmp_path, *extra):
    return ['--rna', str(FIXTURES / 'rna/catalogue.csv'), '--rna-state', str(tmp_path / 'state.json'),
            '--rna-memory', str(tmp_path / 'memory.json'), *extra]


def browser(tmp_path, *extra):
    parser = argparse.ArgumentParser()
    add_rna_arguments(parser)
    result = browser_from_args(parser.parse_args(arguments(tmp_path, *extra)))
    result.set_receiver('fixture', 378)
    return result


def test_restart_remembers_all_filters_activity_cle_near_and_runtime_site(tmp_path):
    b = browser(tmp_path, '--rna-min-khz', '300', '--rna-max-khz', '400', '--rna-exclude-unknown-distance')
    assert not (tmp_path / 'state.json').exists()  # Loading alone never writes.
    for command in ['rna site 40 -75 UTC', 'rna range 2000', 'rna power 10', 'rna search RJ',
                    'rna sort distance', 'rna cle on', 'rna near 125']:
        b.command(command, 378)
    b.cycle_activity(378)
    restored = browser(tmp_path)
    assert restored.filters == b.filters
    assert restored.filters.activity == 'active'
    assert not restored.filters.include_unknown_distance
    assert restored.cle332_only and restored.near_radius_hz == 125
    assert restored.sites == b.sites and not restored.error
    assert all(value in restored.filter_summary() for value in ['search=RJ', '300', '400', 'unknown-distance=exclude', 'near=125Hz'])
    restored.command('rna cle off', 378)
    assert not browser(tmp_path).cle332_only
    restored.command('rna power off', 378)
    assert browser(tmp_path).filters.min_power_w is None
    restored.set_receiver('unknown-site', 378)
    assert not restored.matches and 'receiver site' in restored.error
    assert restored.filters.max_distance_km == 2000  # Never silently disable range.


def test_explicit_cli_overrides_saved_values_and_site_file_is_read_only(tmp_path):
    b = browser(tmp_path, '--rna-cle332', '--rna-activity', 'all', '--rna-search', 'RJ', '--rna-near-hz', '25')
    b.command('rna site 40 -75 UTC', 378)
    site = tmp_path / 'sites.toml'
    content = '[sites.fixture]\nlatitude=45\nlongitude=-70\ntimezone="UTC"\n'
    site.write_text(content)
    b = browser(tmp_path, '--no-rna-cle332', '--rna-activity', 'active', '--rna-search', '',
                '--rna-near-hz', '50', '--rna-sites', str(site), '--no-rna-exclude-unknown-distance')
    assert not b.cle332_only and b.filters.search == '' and b.filters.activity == 'active'
    assert b.near_radius_hz == 50 and b.filters.include_unknown_distance
    assert b.sites['fixture'].latitude == 45
    b.save_preferences()
    assert browser(tmp_path).filters == b.filters
    assert site.read_text() == content


def test_reset_disable_and_invalid_commands_do_not_overwrite_saved_state(tmp_path):
    b = browser(tmp_path, '--rna-activity', 'all')
    b.save_preferences()
    path = tmp_path / 'state.json'
    original = path.read_bytes()
    for command in ['rna power nan', 'rna near -1', 'rna site 91 0 UTC', 'rna typo on']:
        with pytest.raises(ValueError):
            b.command(command, 378)
        assert path.read_bytes() == original
    reset = browser(tmp_path, '--rna-reset-state')
    assert reset.filters == CatalogueFilter() and path.read_bytes() == original
    disabled = browser(tmp_path, '--no-rna-state')
    disabled.command('rna activity active', 378)
    disabled.save_preferences()
    assert path.read_bytes() == original
    reset.save_preferences()
    assert browser(tmp_path).filters == CatalogueFilter()


@pytest.mark.parametrize('command', ['rna activity active', 'rna cle on', 'rna near 20', 'rna site 40 -75 UTC', 'A'])
def test_failed_atomic_save_preserves_live_and_disk_state(tmp_path, monkeypatch, command):
    import kiwi_client.rna_preferences as preferences
    b = browser(tmp_path)
    b.save_preferences()
    path = tmp_path / 'state.json'
    original = path.read_bytes()
    snapshot = b.filters, b.cle332_only, b.near_radius_hz, dict(b.sites), b.matches
    def fail(*args):
        raise OSError('simulated replace failure')
    monkeypatch.setattr(preferences.os, 'replace', fail)
    with pytest.raises(OSError, match='simulated'):
        b.cycle_activity(378) if command == 'A' else b.command(command, 378)
    assert (b.filters, b.cle332_only, b.near_radius_hz, b.sites, b.matches) == snapshot
    assert path.read_bytes() == original and not list(tmp_path.glob('state.json.*'))


@pytest.mark.parametrize('field,value', [('schema', 2), ('filters', {'search': False}),
    ('filters', {'max_distance_km': -1}), ('near_radius_hz', float('nan')), ('cle332_only', 'off'), ('sites', [])])
def test_corrupt_state_is_not_silently_discarded_or_overwritten(tmp_path, field, value):
    data = dict(schema=1, filters=asdict(CatalogueFilter()), cle332_only=False, near_radius_hz=200, sites={})
    data[field] = value
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    with pytest.raises(ValueError, match='invalid RNA state'):
        browser(tmp_path)
    assert path.read_bytes() == original
    assert browser(tmp_path, '--no-rna-state').filters == CatalogueFilter()
    assert browser(tmp_path, '--rna-reset-state').filters == CatalogueFilter()
    assert path.read_bytes() == original


@pytest.mark.parametrize('fail_save', [False, True])
def test_interactive_entry_saves_cli_settings_without_needing_filter_changes(tmp_path, monkeypatch, fail_save):
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.gui_app import WaterfallGuiModel, FixtureWaterfallTimeline
    from kiwi_client.waterfall_levels import WaterfallLevelController
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn = []
    class Screen:
        keys = iter([None, 'q'])
        def get_wch(self):
            return next(self.keys)
        def getmaxyx(self):
            return 40, 174
        def addnstr(self, row, column, text, *args):
            drawn.append(text)
        def __getattr__(self, name):
            return lambda *args: None
    class Presenter:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    b = browser(tmp_path, '--rna-activity', 'all', '--rna-cle332')
    if fail_save:
        def fail(*args):
            raise OSError('simulated startup write failure')
        monkeypatch.setattr(b.preferences, 'save', fail)
    shell.run_fixture_shell(Screen(), model=WaterfallGuiModel(), rna_browser=b,
        timeline=FixtureWaterfallTimeline.from_fixture(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl', repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=None, tui_config=None, source_fps=20, refresh_hz=20,
        scale_font_backend='bitmap')
    if fail_save:
        assert not (tmp_path / 'state.json').exists()
        assert any('RNA state NOT saved: simulated startup write failure' in text for text in drawn)
    else:
        assert browser(tmp_path).cle332_only and browser(tmp_path).filters.activity == 'all'


def test_dry_run_does_not_create_or_change_state(tmp_path, capsys):
    from kiwi_client.integrated_terminal import main
    args = ['--fixture', str(FIXTURES / 'kiwi/local-wf-am-855-zoom7.jsonl'), '--dry-run']
    assert main(args + arguments(tmp_path, '--rna-activity', 'all')) == 0
    assert not (tmp_path / 'state.json').exists()
    b = browser(tmp_path, '--rna-cle332')
    b.save_preferences()
    original = (tmp_path / 'state.json').read_bytes()
    assert main(args + arguments(tmp_path, '--no-rna-cle332')) == 0
    assert (tmp_path / 'state.json').read_bytes() == original
