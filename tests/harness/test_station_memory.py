from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.integrated_terminal import execute_console_rna_command, tune_rna_component
from kiwi_client.ndb_logbook import reception_draft, cle332_report
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.station_memory import StationMemory, passband_center_khz

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def browser(path=None):
    b = RnaBrowser(load_catalogue(FIXTURE), memory=StationMemory(path))
    b.set_receiver('fixture', 378)
    return b


def test_default_usb_fallback_carrier_and_per_station_choice_survive_restart(tmp_path):
    path = tmp_path / 'stations.json'
    b = browser(path)
    assert b.component.kind == 'usb'
    b.cycle_component()
    assert b.component.kind == 'carrier'
    b.cycle_component()
    assert b.component.kind == 'lsb'
    b.move(1)
    assert b.selected.station.ident == 'UNK' and b.component.kind == 'carrier'
    b.move(-1)
    assert b.component.kind == 'lsb'
    restored = browser(path)
    assert restored.component.kind == 'lsb'
    assert restored.catalogue.sha256 == load_catalogue(FIXTURE).sha256


def test_stored_center_bandwidth_cycle_log_and_forget(tmp_path):
    path = tmp_path / 'stations.json'
    b = browser(path)
    model = WaterfallGuiModel(tuned_khz=378.375, selected_khz=378.375)
    # Nonstandard 850 Hz audio midpoint, not the magnitude of the -800 CW offset.
    model.session.state = replace(model.session.state, mode='cw', low_cut_hz=825, high_cut_hz=875)
    assert passband_center_khz(model.session.state) == pytest.approx(378.425)
    execute_console_rna_command(b, 'rna store', model)
    assert b.component.kind == 'stored'
    assert b.component.frequency_khz == pytest.approx(378.425)
    assert 'RJ:S' in {a.label for a in b.annotations(378, 379)}
    b = browser(path)
    model.session.state = replace(model.session.state, frequency_khz=390, low_cut_hz=550, high_cut_hz=1050)
    tune_rna_component(b, model)
    assert passband_center_khz(model.session.state) == pytest.approx(378.425)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 50
    record = reception_draft(b, model.session.state, receiver='fixture', source_kind='fixture', event=None)
    assert record['rf_center_khz'] == pytest.approx(378.425)
    assert record['carrier_offset_hz'] == pytest.approx(425)
    assert record['bandwidth_hz'] == 50
    kinds = []
    for _ in range(4):
        b.cycle_component()
        kinds.append(b.component.kind)
    assert kinds == ['carrier', 'lsb', 'usb', 'stored']
    execute_console_rna_command(b, 'rna forget', model)
    assert b.component.kind == 'usb'
    assert 'stored' not in [c.kind for c in browser(path).components]
    assert record['carrier_offset_hz'] == pytest.approx(425)  # frozen logging snapshot


def test_stored_controller_tuning_restores_rf_center_not_cw_reference(tmp_path):
    from kiwi_client.client_app import ClientController, ClientState
    b = browser(tmp_path / 'memory.json')
    controller = ClientController(state=ClientState(frequency_khz=378.375, mode='cw', low_cut_hz=825, high_cut_hz=875))
    model = WaterfallGuiModel()
    model.session = controller.paired_session
    model.action_dispatch = controller.dispatch_session_action
    b.store_tuning(model.session.state)
    controller.execute('tune 390; filter 600 1000')
    tune_rna_component(b, model, controller)
    assert passband_center_khz(model.session.state) == pytest.approx(378.425)
    assert controller.state.high_cut_hz - controller.state.low_cut_hz == 50
    assert b.selected.station.carrier_khz == 378


def test_memory_write_failure_preserves_choice_and_file(tmp_path, monkeypatch):
    b = browser(tmp_path / 'memory.json')
    b.cycle_component()
    before = b.memory.path.read_bytes()
    import kiwi_client.station_memory as module
    def fail(*args):
        raise OSError('replace failed')
    monkeypatch.setattr(module.os, 'replace', fail)
    with pytest.raises(OSError):
        b.cycle_component()
    assert b.component.kind == 'carrier'
    assert b.memory.path.read_bytes() == before
    assert len(list(tmp_path.iterdir())) == 1


def test_invalid_memory_is_not_overwritten(tmp_path):
    path = tmp_path / 'bad.json'
    path.write_text('{"schema": 9, "stations": {}}')
    before = path.read_bytes()
    with pytest.raises(ValueError):
        StationMemory(path)
    assert path.read_bytes() == before
