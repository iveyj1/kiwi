"""Regressions for retiring experimental 2/5 Hz console widths."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from kiwi_client.commands import encode_modulation
from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.integrated_terminal import step_console_cw_bandwidth, tune_rna_component
from kiwi_client.ndb_logbook import reception_draft
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.station_memory import passband_center_khz

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def test_historical_narrow_fixture_is_encoding_evidence_not_supported_ladder():
    fixture = json.loads((FIXTURES / 'kiwi/cw-narrow-commands.json').read_text())
    for item, cuts, frequency in zip(fixture['commands'], [(798, 803), (799, 801)], [377.1995, 377.2000]):
        assert encode_modulation('cw', *cuts, frequency, frequency_decimals=4) == item['command']


@pytest.mark.parametrize('cuts', [(799, 801), (798, 803)])
@pytest.mark.parametrize('direction', [-1, 1])
def test_old_narrow_width_steps_to_ten_and_keeps_rf_center(cuts, direction):
    model = WaterfallGuiModel()
    model.session.state = replace(model.session.state, mode='cw', frequency_khz=378, selected_khz=378,
                                  low_cut_hz=cuts[0], high_cut_hz=cuts[1], frequency_decimals=4)
    center = passband_center_khz(model.session.state)
    step_console_cw_bandwidth(model, direction)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 10
    assert passband_center_khz(model.session.state) == pytest.approx(center)


def test_old_stored_five_hz_memory_recalls_ten_without_rewriting_memory():
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    browser.set_receiver('fixture', 378)
    key = browser.selected.station.key
    browser.memory.update(key, dict(choice='stored', stored=dict(carrier_khz=378, offset_hz=405.5, bandwidth_hz=5)))
    model = WaterfallGuiModel()
    model.session.state = replace(model.session.state, mode='cw', low_cut_hz=795, high_cut_hz=805, frequency_decimals=4)
    tune_rna_component(browser, model)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 10
    assert passband_center_khz(model.session.state) == pytest.approx(378.4055)
    assert browser.memory.records[key]['stored']['bandwidth_hz'] == 5
    draft = reception_draft(browser, model.session.state, receiver='fixture', source_kind='fixture', event=None)
    assert draft['bandwidth_hz'] == 10 and draft['rf_center_khz'] == pytest.approx(378.4055)
