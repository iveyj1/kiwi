from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.ndb_logbook import reception_draft
from kiwi_client.reception_ui import ReceptionIndex, station_spreadsheet
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.station_memory import StationMemory

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def test_marker_persists_survives_tuning_memory_edits_and_freezes_in_notes(tmp_path):
    memory = StationMemory(tmp_path / 'stations.json')
    browser = RnaBrowser(load_catalogue(FIXTURE), memory=memory)
    browser.set_receiver('fixture', 378)
    state = WaterfallGuiModel(tuned_khz=378.405, selected_khz=378.405).session.state
    state = replace(state, mode='cw', low_cut_hz=795, high_cut_hz=805)
    browser.toggle_marker()
    key = browser.selected.station.key
    assert StationMemory(memory.path).records[key]['marked'] is True
    rows = station_spreadsheet(browser, ReceptionIndex(None), 'fixture', None, 'fixture')
    assert any(row[0] == '>*RJ' for row in rows)
    draft = reception_draft(browser, state, receiver='fixture', source_kind='fixture', event=None)
    assert draft['notes'] == '*'
    browser.store_tuning(state)
    browser.forget_tuning()
    browser.cycle_component()
    assert memory.records[key]['marked'] is True
    browser.toggle_marker()
    assert StationMemory(memory.path).records[key]['marked'] is False
    assert draft['notes'] == '*'  # No retroactive editing of frozen receptions.


def test_marked_selection_remains_visible_in_a_short_spreadsheet():
    from kiwi_client.console_panels import station_table_lines
    rows = [(('>*' if i == 5 else '  ') + f'ID{i}', '300', 'NO', '', '', '', '') for i in range(8)]
    lines = station_table_lines(rows, 174, 3)
    assert any('>*ID5' in line for line in lines)


def test_invalid_marker_is_rejected(tmp_path):
    memory = StationMemory(tmp_path / 'stations.json')
    with pytest.raises(ValueError, match='marker'):
        memory.update('station', {'choice': 'carrier', 'marked': 'yes'})
    assert not memory.path.exists()


def test_marker_write_failure_does_not_change_active_flag(tmp_path, monkeypatch):
    memory = StationMemory(tmp_path / 'stations.json')
    browser = RnaBrowser(load_catalogue(FIXTURE), memory=memory)
    browser.set_receiver('fixture', 378)
    def fail(*args): raise OSError('disk full')
    monkeypatch.setattr(memory, 'update', fail)
    with pytest.raises(OSError): browser.toggle_marker()
    assert memory.records == {}
