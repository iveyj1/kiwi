from dataclasses import replace
import json

import pytest

from kiwi_client.client_app import ClientController, ClientState, paired_snapshot_from_client_state
from kiwi_client.config import KiwiClientConfig
from kiwi_client.console_state import ConsoleSettingsCheckpoint, normalize_console_cw_bandwidth, startup_waterfall_zoom
from kiwi_client.session_manager import ZoomWaterfall
from kiwi_client.state_store import load_state_file, save_state_file
from kiwi_client.station_memory import passband_center_khz
from kiwi_client.tui import startup_state_and_presets


def config_at(tmp_path):
    config = KiwiClientConfig()
    return replace(config, startup=replace(config.startup, mode='last', state_file=str(tmp_path / 'state.json')),
                   presets=replace(config.presets, file=str(tmp_path / 'presets.toml')),
                   waterfall=replace(config.waterfall, zoom=7))


def controller():
    result = ClientController(state=ClientState(mode='cw', frequency_khz=378, frequency_command_decimals=4))
    result.configure_waterfall_session(center_khz=378, zoom=10, speed=1, interp=13)
    result.execute('filter 775 825')
    return result


def test_restart_restores_zoom_and_per_mode_bandwidth(tmp_path):
    config, current = config_at(tmp_path), controller()
    checkpoint = ConsoleSettingsCheckpoint(config)
    assert checkpoint.save_if_changed(current)
    assert not checkpoint.save_if_changed(current)
    current.dispatch_session_action(ZoomWaterfall(1))
    current.execute('filter 785 815; mode am; filter -2000 2000')
    assert checkpoint.save_if_changed(current)
    restored, _ = startup_state_and_presets(config)
    assert (restored.low_cut_hz, restored.high_cut_hz) == (-2000, 2000)
    assert restored.mode_passbands['cw'] == (785, 815)
    assert startup_waterfall_zoom(config) == 11
    # Legacy TUI saves must not drop the console zoom field.
    save_state_file(tmp_path / 'state.json', last_state=restored)
    assert startup_waterfall_zoom(config) == 11
    default = replace(config, startup=replace(config.startup, mode='default'))
    assert startup_waterfall_zoom(default) == 7


def test_console_keys_checkpoint_zoom_and_bandwidth_without_live_radio(tmp_path, monkeypatch):
    import kiwi_client.integrated_terminal as shell
    from pathlib import Path
    from kiwi_client.gui_app import FixtureWaterfallTimeline, WaterfallGuiModel
    from kiwi_client.waterfall_levels import WaterfallLevelController
    for name in ('mousemask', 'curs_set', 'doupdate'):
        monkeypatch.setattr(shell.curses, name, lambda *args: None)
    monkeypatch.setattr(shell.curses, 'has_colors', lambda: False)
    class Screen:
        keys = iter(['j', '+', None, 'q'])
        def get_wch(self):
            return next(self.keys)
        def getmaxyx(self):
            return 40, 174
        def __getattr__(self, name):
            return lambda *args: None
    class Presenter:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    config, current = config_at(tmp_path), controller()
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    model.session = current.paired_session
    model.action_dispatch = current.dispatch_session_action
    model._session_mapped = True
    fixture = Path(__file__).parents[1] / 'fixtures/kiwi/local-wf-am-855-zoom7.jsonl'
    shell.run_fixture_shell(Screen(), model=model, timeline=FixtureWaterfallTimeline.from_fixture(fixture, repeat=1),
        live_source=None, presets={}, presenter=Presenter(), levels=WaterfallLevelController(),
        tui_controller=current, tui_config=None, source_fps=20, refresh_hz=10000, scale_font_backend='bitmap',
        settings_checkpoint=ConsoleSettingsCheckpoint(config))
    restored, _ = startup_state_and_presets(config)
    assert restored.high_cut_hz - restored.low_cut_hz == 30
    assert restored.mode_passbands['cw'] == (785, 815)
    assert startup_waterfall_zoom(config) == 11


def test_live_startup_dry_run_reports_saved_zoom_and_bandwidth_without_writes(tmp_path, capsys, monkeypatch):
    import kiwi_client.integrated_terminal as shell
    config, current = config_at(tmp_path), controller()
    current.dispatch_session_action(ZoomWaterfall(1))
    current.execute('filter 785 815')
    ConsoleSettingsCheckpoint(config).save_if_changed(current)
    path = tmp_path / 'state.json'
    original, modified = path.read_bytes(), path.stat().st_mtime_ns
    config_path = tmp_path / 'config.toml'
    config_path.write_text('[startup]\nmode="last"\nstate_file="state.json"\n[presets]\nfile="presets.toml"\n[waterfall]\nzoom=7\n')
    def no_start(*args):
        raise AssertionError('dry run must not connect')
    monkeypatch.setattr(shell.ControllerConsoleSource, 'start', no_start)
    assert shell.main(['--allow-live', '--receiver', '10.0.0.41:8073', '--config', str(config_path), '--dry-run']) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['waterfall_zoom'] == 11 and plan['passband_hz'] == [785, 815]
    assert plan['network'] is False
    assert path.read_bytes() == original and path.stat().st_mtime_ns == modified


def test_legacy_state_without_zoom_uses_config_and_load_is_read_only(tmp_path):
    config = config_at(tmp_path)
    assert startup_waterfall_zoom(config) == 7
    assert not list(tmp_path.iterdir())
    save_state_file(tmp_path / 'state.json', last_state=controller().state)
    original = (tmp_path / 'state.json').read_bytes()
    assert startup_waterfall_zoom(config) == 7
    assert (tmp_path / 'state.json').read_bytes() == original


@pytest.mark.parametrize('zoom', [-1, 15, True, 3.5])
def test_invalid_zoom_is_rejected_without_overwrite(tmp_path, zoom):
    path = tmp_path / 'state.json'
    state = controller().state
    save_state_file(path, last_state=state, waterfall_zoom=10)
    original = path.read_bytes()
    with pytest.raises(ValueError, match='zoom'):
        save_state_file(path, last_state=state, waterfall_zoom=zoom)
    assert path.read_bytes() == original
    path.write_text(json.dumps({'last_state': {'waterfall_zoom': zoom}}))
    with pytest.raises(ValueError, match='zoom'):
        load_state_file(path)


def test_failed_checkpoint_preserves_file_and_does_not_retry_each_frame(tmp_path, monkeypatch):
    import kiwi_client.state_store as store
    config, current = config_at(tmp_path), controller()
    checkpoint = ConsoleSettingsCheckpoint(config)
    checkpoint.save_if_changed(current)
    path = tmp_path / 'state.json'
    original = path.read_bytes()
    calls = []
    def fail(*args):
        calls.append(args)
        raise OSError('disk unavailable')
    monkeypatch.setattr(store.os, 'replace', fail)
    current.execute('filter 795 805')
    with pytest.raises(OSError):
        checkpoint.save_if_changed(current)
    assert not checkpoint.save_if_changed(current)
    with pytest.raises(OSError):
        checkpoint.save_if_changed(current, force=True)
    assert len(calls) == 2
    assert path.read_bytes() == original and not list(tmp_path.glob('state.json.*'))
    assert current.state.high_cut_hz - current.state.low_cut_hz == 10


@pytest.mark.parametrize('cuts', [(799, 801), (798, 803)])
def test_old_narrow_cw_state_widens_to_ten_preserving_rf_center(cuts):
    state = ClientState(mode='cw', frequency_khz=378, low_cut_hz=cuts[0], high_cut_hz=cuts[1],
                        mode_passbands={'cw': cuts}, frequency_command_decimals=4)
    before = passband_center_khz(paired_snapshot_from_client_state(state))
    restored = normalize_console_cw_bandwidth(state)
    assert restored.high_cut_hz - restored.low_cut_hz == 10
    assert restored.mode_passbands['cw'] == (restored.low_cut_hz, restored.high_cut_hz)
    assert passband_center_khz(paired_snapshot_from_client_state(restored)) == pytest.approx(before)
    inactive = replace(state, mode='am', low_cut_hz=-5000, high_cut_hz=5000)
    normalized = normalize_console_cw_bandwidth(inactive)
    assert normalized.frequency_khz == inactive.frequency_khz
    assert (normalized.low_cut_hz, normalized.high_cut_hz) == (-5000, 5000)
    assert normalized.mode_passbands['cw'][1] - normalized.mode_passbands['cw'][0] == 10
