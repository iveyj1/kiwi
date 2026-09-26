from dataclasses import replace
import json
from pathlib import Path

import pytest

from kiwi_client.client_app import ClientController, ClientState
from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.integrated_terminal import step_console_cw_bandwidth, tune_rna_component
from kiwi_client.ndb_logbook import reception_draft
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser
from kiwi_client.station_memory import passband_center_khz

FIXTURES = Path(__file__).parents[1] / 'fixtures'


def test_narrow_command_fixture_preserves_rf_center():
    fixture = json.loads((FIXTURES / 'kiwi/cw-narrow-commands.json').read_text())
    controller = ClientController(state=ClientState(mode='cw', frequency_khz=378, low_cut_hz=795,
                                                    high_cut_hz=805, frequency_command_decimals=4))
    model = WaterfallGuiModel()
    model.session = controller.paired_session
    model.action_dispatch = controller.dispatch_session_action
    for expected in fixture['commands']:
        step_console_cw_bandwidth(model, -1, controller)
        assert controller._modulation_command() == expected['command']
        assert controller.state.high_cut_hz - controller.state.low_cut_hz == expected['bandwidth_hz']
        assert passband_center_khz(model.session.state) == pytest.approx(378)


def test_coarse_precision_skips_five_but_allows_two():
    model = WaterfallGuiModel()
    model.session.state = replace(model.session.state, mode='cw', frequency_khz=378, selected_khz=378,
                                  low_cut_hz=795, high_cut_hz=805, frequency_decimals=3)
    message = step_console_cw_bandwidth(model, -1)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 2
    assert 'skipped' in message
    assert passband_center_khz(model.session.state) == pytest.approx(378)
    step_console_cw_bandwidth(model, 1)
    assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == 10


@pytest.mark.parametrize('midpoint', [800, 850, -800])
def test_repeated_parity_changes_no_drift_and_catalogue_log_association(midpoint):
    browser = RnaBrowser(load_catalogue(FIXTURES / 'rna/catalogue.csv'))
    browser.set_receiver('fixture', 378)
    model = WaterfallGuiModel()
    model.session.state = replace(model.session.state, mode='cw', low_cut_hz=midpoint-5,
                                  high_cut_hz=midpoint+5, frequency_decimals=4)
    tune_rna_component(browser, model)
    original = passband_center_khz(model.session.state)
    for _ in range(5):
        for direction, expected_width in [(-1, 5), (-1, 2), (1, 5), (1, 10)]:
            step_console_cw_bandwidth(model, direction)
            assert model.session.state.high_cut_hz - model.session.state.low_cut_hz == expected_width
            assert passband_center_khz(model.session.state) == pytest.approx(original)
            tune_rna_component(browser, model)  # Retune must not undo half-Hz compensation.
            assert passband_center_khz(model.session.state) == pytest.approx(original)
            record = reception_draft(browser, model.session.state, receiver='fixture', source_kind='fixture', event=None)
            assert record['bandwidth_hz'] == expected_width
            assert record['rf_center_khz'] == pytest.approx(original)
