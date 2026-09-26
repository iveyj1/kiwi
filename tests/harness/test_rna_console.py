from pathlib import Path

import pytest

from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.integrated_terminal import main, tune_rna_component
from kiwi_client.rna_catalogue import CatalogueFilter, ReceiverSite, load_catalogue
from kiwi_client.rna_console import RnaBrowser, load_sites
from kiwi_client.waterfall_scale import compose_waterfall_scale
from kiwi_client.waterfall_raster import RasterImage

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def browser(**kwargs):
    result = RnaBrowser(load_catalogue(FIXTURE), **kwargs)
    result.set_receiver('fixture', 378)
    return result


def test_browsing_and_component_selection_do_not_tune():
    b = browser()
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    assert b.component.frequency_khz == 378.405
    assert model.session.state.frequency_khz == 378
    assert b.selected.station.carrier_khz == 378
    b.move(1)
    assert b.selected.station.ident == 'UNK'
    assert b.component.kind == 'carrier'
    b.move(-1)
    assert b.selected.station.ident == 'RJ'


def test_selected_usb_tunes_component_not_nominal_or_offset_frequency():
    b = browser()
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    tune_rna_component(b, model)
    state = model.session.state
    assert state.mode == 'cw'
    assert state.frequency_khz == 378.405
    assert state.frequency_khz + state.cw_offset_hz / 1000 == pytest.approx(377.605)
    assert b.selected.station.carrier_khz == 378


def test_controller_tuning_uses_existing_cw_command_path():
    from kiwi_client.client_app import ClientController, ClientState
    controller = ClientController(state=ClientState(frequency_khz=378))
    model = WaterfallGuiModel(tuned_khz=378, selected_khz=378)
    # Bind the same action boundary used by source.start, without opening a socket.
    model.session = controller.paired_session
    model.action_dispatch = controller.dispatch_session_action
    b = browser()
    tune_rna_component(b, model, controller)
    assert controller.state.mode == 'cw'
    assert controller.state.frequency_khz == 378.405
    assert controller.state.radio_frequency_khz == pytest.approx(377.605)


def test_site_switch_does_not_reuse_old_location():
    b = browser(filters=CatalogueFilter(max_distance_km=1), sites={
        'fixture': ReceiverSite('test', 48.5625, -72.2917)})
    assert any(m.station.ident == 'RJ' for m in b.matches)
    b.set_receiver('unconfigured:8073', 378)
    assert not b.matches
    assert 'receiver site' in b.status()
    b.set_receiver('fixture', 378)
    assert b.selected.station.ident == 'RJ'


def test_activity_cycle_and_visible_annotations():
    b = browser()
    assert {a.label for a in b.annotations(377.5, 378.5)} == {'RJ:C', 'RJ:L', 'RJ:U'}
    b.cycle_activity(378)
    assert b.filters.activity == 'active'
    b.cycle_activity(378)
    assert 'OLD:C' in {a.label for a in b.annotations(377.5, 378.5)}
    assert len([a for a in b.annotations(377.5, 378.5) if a.selected]) == 1


def test_marker_geometry_offscreen_and_collisions():
    b = browser()
    image = RasterImage(1001, 1, b'\0' * 3003)
    kwargs = dict(tuned_khz=378, selected_khz=378, low_cut_hz=600, high_cut_hz=1000,
                  presets={}, font_backend='bitmap', font_scale=1)
    plain = compose_waterfall_scale(image, 377.5, 378.5, **kwargs).image
    annotated = compose_waterfall_scale(image, 377.5, 378.5,
                                       annotations=b.annotations(377.5, 378.5), **kwargs).image
    assert annotated.height > plain.height
    def pixel(x, y):
        index = (y * annotated.width + x) * 3
        return tuple(annotated.rgb[index:index + 3])
    assert pixel(90, plain.height) == (100, 220, 180)
    assert pixel(500, plain.height) == (100, 220, 180)
    assert pixel(905, plain.height) == (255, 255, 255)
    assert pixel(905, plain.height + 4) == (0, 0, 0)
    # Tiny viewport, many coincident labels and offscreen annotations remain safe.
    result = compose_waterfall_scale(RasterImage(10, 1, b'\0' * 30), 378, 378.01,
                                    annotations=b.annotations(377, 379) * 4, **kwargs)
    assert len(result.image.rgb) == result.image.width * result.image.height * 3


def test_site_file(tmp_path):
    path = tmp_path / 'sites.toml'
    path.write_text('[sites."10.0.0.43:8073"]\nlatitude=45\nlongitude=-75\ntimezone="America/Toronto"\n')
    assert load_sites(path)['10.0.0.43:8073'].timezone == 'America/Toronto'
    path.write_text('[sites.test]\nlatitude=45\n')
    with pytest.raises(ValueError, match='incomplete'):
        load_sites(path)


def test_cle_filter_uses_nominal_frequency_not_components(tmp_path):
    path = tmp_path / 'event.csv'
    path.write_text('KHz,ID,Type,Active,USB\n378,RJ,NDB,Y,405\n379,ODD,NDB,Y,1000\n380,UNID,NDB,Y,400\n')
    b = RnaBrowser(load_catalogue(path), cle332_only=True)
    b.set_receiver('fixture', 378)
    assert [m.station.ident for m in b.matches] == ['RJ']
    assert {a.frequency_khz for a in b.annotations(377, 381)} == {378, 378.405}


def test_console_rna_dry_run_never_connects(capsys):
    import json
    assert main(['--allow-live', '--receiver', '10.0.0.43:8073', '--dry-run', '--rna', str(FIXTURE)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['network'] is False
    assert 'RNA' in result['rna']
