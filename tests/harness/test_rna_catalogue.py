import hashlib
import json
from pathlib import Path

import pytest

from kiwi_client.rna_catalogue import (
    CatalogueFilter, ReceiverSite, distance_km, load_catalogue, main, select_stations,
)

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def test_import_preserves_provenance_fields_and_asymmetric_components():
    catalogue = load_catalogue(FIXTURE)
    assert len(catalogue.stations) == 6
    assert catalogue.sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert catalogue.loaded_utc.endswith('+00:00')
    rj = catalogue.stations[0]
    assert rj.raw_fields['Notes'] == 'Asymmetric offsets'
    assert rj.activity == 'active'
    assert [(c.kind, c.frequency_khz) for c in rj.components] == [
        ('carrier', 378), ('lsb', 377.590), ('usb', 378.405),
    ]
    with pytest.raises(TypeError):
        rj.raw_fields['ID'] = 'changed'
    assert rj.period_s == 10.3
    assert rj.location == 'Roberval'


def test_unknown_is_not_zero_and_invalid_optional_fields_have_diagnostics():
    catalogue = load_catalogue(FIXTURE)
    unknown = catalogue.stations[2]
    assert unknown.activity == 'unknown'
    assert len(unknown.components) == 1
    zero_offset = catalogue.stations[3]
    assert zero_offset.usb_hz == 0
    assert len(zero_offset.components) == 2
    invalid = catalogue.stations[-1]
    assert invalid.latitude is None and invalid.longitude is None
    assert invalid.lsb_hz is None and invalid.usb_hz is None
    assert invalid.period_s is None
    assert len(catalogue.warnings) >= 5


def test_station_identity_distinguishes_sites_but_survives_activity_update(tmp_path):
    catalogue = load_catalogue(FIXTURE)
    assert catalogue.stations[3].key != catalogue.stations[4].key
    path = tmp_path / 'updated.csv'
    path.write_text(FIXTURE.read_text().replace('378,RJ,NDB,Y', '378,RJ,NDB,N'))
    updated = load_catalogue(path)
    assert updated.stations[0].key == catalogue.stations[0].key
    assert updated.sha256 != catalogue.sha256


def test_bom_headers_and_invalid_required_fields(tmp_path):
    path = tmp_path / 'bom.csv'
    path.write_text('\ufeffKHz,ID,Type\n300,A,NDB\n')
    assert len(load_catalogue(path).stations) == 1
    path.write_text('KHz,ID\n300,A\n')
    with pytest.raises(ValueError, match='Type'):
        load_catalogue(path)
    path.write_text('KHz,ID,Type,ID\n300,A,NDB,B\n')
    with pytest.raises(ValueError, match='duplicate'):
        load_catalogue(path)


def test_distance_zero_dateline_and_antipodes():
    assert distance_km(0, 0, 0, 0) == 0
    assert distance_km(0, 179.9, 0, -179.9) == pytest.approx(22.239, abs=.001)
    assert distance_km(90, 0, -90, 0) == pytest.approx(20015.114, abs=.01)


def test_filters_activity_search_and_nominal_range():
    catalogue = load_catalogue(FIXTURE)
    default = select_stations(catalogue)
    assert {r.station.ident for r in default} == {'RJ', 'UNK', 'DUP', 'BAD'}
    active = select_stations(catalogue, filters=CatalogueFilter(activity='active'))
    assert 'UNK' not in {r.station.ident for r in active}
    all_rows = select_stations(catalogue, filters=CatalogueFilter(activity='all'))
    assert len(all_rows) == 6
    matches = select_stations(catalogue, filters=CatalogueFilter(
        min_khz=378, max_khz=378, search='roberval'))
    assert [r.station.ident for r in matches] == ['RJ']
    # Range means nominal channel, not a component that happens to lie inside it.
    assert not select_stations(catalogue, filters=CatalogueFilter(min_khz=378.4, max_khz=378.41))


def test_distance_filter_requires_site_and_handles_unknown_explicitly():
    catalogue = load_catalogue(FIXTURE)
    filters = CatalogueFilter(max_distance_km=30, sort='distance')
    with pytest.raises(ValueError, match='receiver site'):
        select_stations(catalogue, filters=filters)
    east = ReceiverSite('east', 0, 179.9, 'UTC')
    matches = select_stations(catalogue, site=east, filters=filters)
    assert [r.station.location for r in matches[:2]] == ['East site', 'West site']
    assert matches[-1].distance_km is None
    strict = CatalogueFilter(max_distance_km=30, include_unknown_distance=False)
    assert len(select_stations(catalogue, site=east, filters=strict)) == 2
    west = ReceiverSite('west', 0, -179.9, 'UTC')
    assert select_stations(catalogue, site=west, filters=filters)[0].station.location == 'West site'


@pytest.mark.parametrize('kwargs', [
    {'max_distance_km': -1}, {'max_distance_km': float('nan')},
    {'min_khz': 400, 'max_khz': 300}, {'activity': 'bad'}, {'sort': 'bad'},
    {'min_khz': float('inf')},
])
def test_invalid_filters(kwargs):
    with pytest.raises(ValueError):
        CatalogueFilter(**kwargs)


@pytest.mark.parametrize('lat,lon,zone', [(91, 0, 'UTC'), (0, 181, 'UTC'), (float('nan'), 0, 'UTC'), (0, 0, 'No/Such_Zone')])
def test_invalid_sites(lat, lon, zone):
    with pytest.raises(ValueError):
        ReceiverSite('test', lat, lon, zone)


def test_offline_cli(capsys):
    assert main([str(FIXTURE), '--activity', 'active', '--search', 'RJ']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['network'] is False
    assert result['stations'][0]['carrier_khz'] == 378
    assert result['stations'][0]['distance_km'] is None
    with pytest.raises(SystemExit):
        main([str(FIXTURE), '--latitude', '45'])
