from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.rna_catalogue import CatalogueFilter, ReceiverSite, load_catalogue, select_stations
from kiwi_client.rna_console import CallsignSearchPage, RnaBrowser


@pytest.fixture
def browser(tmp_path):
    path = tmp_path / 'stations.csv'
    path.write_text("KHz,ID,Type,Active,USB,Pwr,Lat,Lon,'Name' and Location\n"
                    '209,MT,NDB,Y,410,500,0,0,Chibougamau\n'
                    '210,ARX,NDB,Y,1005,200,0,1,Araxa\n'
                    '362,MT,NDB,Y,1034,,0,2,Manitowac\n'
                    '398,MT,NDB,N,407,50,,,St Nazaire\n'
                    '400,ZZ,NDB,Y,,NaN,,,MT in location only\n'
                    '402,AMT,NDB,Y,,500,0,3,Partial ID\n')
    b = RnaBrowser(load_catalogue(path), cle332_only=True,
                   sites={'fixture': ReceiverSite('test', 0, 0, 'UTC')})
    b.set_receiver('fixture', 210)
    return b


def test_mt_is_hidden_by_nominal_cle_channel_and_search_explains_it(browser):
    assert not any(a.label == 'MT:U' and a.frequency_khz == 209.410 for a in browser.annotations(208, 211))
    assert any(a.label == 'ARX:C' for a in browser.annotations(208, 211))
    page = CallsignSearchPage(browser, 'mt')
    assert len(page.hits) == 4
    assert [h.station.ident for h in page.hits] == ['MT', 'MT', 'MT', 'AMT']
    assert 'CLE332 nominal channel' in browser.exclusion_reason(page.hits[0])
    with pytest.raises(ValueError, match='Hidden'):
        page.select()
    assert browser.selected.station.ident == 'ARX'
    browser.command('rna cle off', 210)
    page.select()
    assert browser.selected.station.carrier_khz == 209
    assert any(a.frequency_khz == 209.410 for a in browser.annotations(208, 211))


def test_power_inclusive_and_unknown_excluded(browser):
    browser.command('rna cle off', 210)
    browser.command('rna power 500', 210)
    assert {m.station.ident for m in browser.matches} == {'MT', 'AMT'}
    assert all(m.station.power_w == 500 for m in browser.matches)
    browser.command('rna power off', 210)
    assert any(m.station.power_w is None for m in browser.matches)


def test_range_inclusive_strict_unknown_and_distance_sort(browser):
    browser.command('rna cle off', 210)
    browser.command('rna range 0', 210)
    assert [m.station.carrier_khz for m in browser.matches] == [209]
    browser.command('rna range off', 210)
    assert any(m.distance_km is None for m in browser.matches)
    browser.command('rna site 0 2 UTC', 210)
    browser.command('rna sort distance', 210)
    assert browser.matches[0].station.carrier_khz == 362
    assert browser.matches[-1].distance_km is None
    browser.command('rna sort frequency', 210)
    assert browser.matches[0].station.carrier_khz == 209


@pytest.mark.parametrize('command', ['rna range -1', 'rna power nan', 'rna sort wrong',
                                    'rna cle yes', 'rna site 91 0 UTC', 'rna power 500 extra'])
def test_invalid_command_is_atomic(browser, command):
    before = (browser.filters, dict(browser.sites), browser.cle332_only, browser.matches)
    with pytest.raises(ValueError):
        browser.command(command, 210)
    assert (browser.filters, browser.sites, browser.cle332_only, browser.matches) == before


def test_distance_command_needs_current_receiver_site(browser):
    browser.set_receiver('unconfigured', 210)
    with pytest.raises(ValueError, match='receiver site'):
        browser.command('rna range 1000', 210)
    with pytest.raises(ValueError, match='receiver site'):
        browser.command('rna sort distance', 210)
    assert browser.filters.max_distance_km is None
    browser.command('rna site 0 0 UTC', 210)
    browser.command('rna range 1000', 210)
    assert browser.filters.max_distance_km == 1000


def test_search_pagination_empty_hits_and_selection_does_not_change_filters(browser):
    page = CallsignSearchPage(browser, 'mt')
    original = browser.filters
    page.move(100)
    assert page.index == 3
    assert len(page.rows(6)) <= 6
    assert 'AMT' in '\n'.join(page.rows(6))
    page.move(-100)
    assert page.index == 0
    empty = CallsignSearchPage(browser, 'not-an-id')
    with pytest.raises(ValueError, match='no callsign'):
        empty.select()
    assert browser.filters == original


@pytest.mark.parametrize('live_editor', [False, True])
def test_shell_search_and_colon_commands(browser, monkeypatch, tmp_path, live_editor):
    import kiwi_client.integrated_terminal as shell
    from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
    from kiwi_client.waterfall_levels import WaterfallLevelController
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    drawn = []

    class Screen:
        keys = iter(':rna cle off\n/MT\n\nq')
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

    model = WaterfallGuiModel(tuned_khz=210, selected_khz=210)
    controller = config = None
    forwarded = []
    if live_editor:
        from kiwi_client.client_app import ClientController, ClientState
        from kiwi_client.config import default_config
        controller = ClientController(state=ClientState(frequency_khz=210))
        model.session = controller.paired_session
        model.action_dispatch = controller.dispatch_session_action
        config = default_config()
        config = replace(config, startup=replace(config.startup, state_file=str(tmp_path / 'state.json')),
                         presets=replace(config.presets, file=str(tmp_path / 'presets.toml')))
        original = controller.execute
        def execute(command):
            forwarded.append(command)
            return original(command)
        monkeypatch.setattr(controller, 'execute', execute)
    fixture = Path(__file__).parents[1] / 'fixtures/kiwi/local-wf-am-855-zoom7.jsonl'
    shell.run_fixture_shell(Screen(), model=model, timeline=FixtureWaterfallTimeline.from_fixture(fixture, repeat=1),
                            live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
                            tui_controller=controller, tui_config=config, source_fps=20, refresh_hz=10000,
                            scale_font_backend='bitmap', rna_browser=browser)
    assert all(not command.startswith('rna') for command in forwarded)
    assert not browser.cle332_only
    assert browser.selected.station.carrier_khz == 209
    assert model.session.state.frequency_khz == 209.410
    assert any('CALLSIGN /MT' in row for row in drawn)
    assert any('NDB callsign: /' in row for row in drawn)
