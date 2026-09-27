from dataclasses import replace
from pathlib import Path

import pytest

from kiwi_client.console_panels import cell_width, main_panel_rows, station_table_lines
from kiwi_client.reception_ui import ReceptionIndex, scope_key, station_spreadsheet
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'


def browser():
    result = RnaBrowser(load_catalogue(FIXTURE))
    result.set_receiver('fixture', 378)
    return result


def test_spreadsheet_fields_scoped_status_and_catalogue_last(tmp_path):
    b = browser()
    index = ReceptionIndex(tmp_path / 'does-not-exist.sqlite')
    key = scope_key(b.selected.station.key, 'fixture', 'CLE332', 'fixture')
    index.groups[key] = [dict(status='confirmed', heard_utc='2026-09-26T01:02:03Z')]
    row = station_spreadsheet(b, index, 'fixture', 'CLE332', 'fixture')[0]
    assert row == ('> RJ', '378', 'CONFIRMED 2026-09-26 01:02:03Z', 'Roberval QC CAN', '?', '10.3', '2026-04-13')
    for receiver, event, source in [('other', 'CLE332', 'fixture'), ('fixture', None, 'fixture'), ('fixture', 'CLE332', 'live')]:
        assert station_spreadsheet(b, index, receiver, event, source)[0][2] == 'NO'
    index.groups[key].insert(0, dict(status='not-heard', heard_utc='2026-09-26T02:02:03Z'))
    assert station_spreadsheet(b, index, 'fixture', 'CLE332', 'fixture')[0][2].startswith('NOT-HEARD+')
    index.groups[key].pop()
    assert station_spreadsheet(b, index, 'fixture', 'CLE332', 'fixture')[0][2].startswith('NOT-HEARD ')
    index.error = 'cannot read database'
    assert station_spreadsheet(b, index, 'fixture', 'CLE332', 'fixture')[0][2] == 'UNAVAILABLE'
    index.path = None
    assert station_spreadsheet(b, index, 'fixture', 'CLE332', 'fixture')[0][2] == 'OFF'
    assert not list(tmp_path.iterdir())


def test_unknown_values_duplicate_ids_and_window_follow_selection(tmp_path):
    b = browser()
    index = ReceptionIndex(tmp_path / 'no-write.sqlite')
    duplicates = [m for m in b.matches if m.station.ident == 'DUP']
    key = scope_key(duplicates[0].station.key, 'fixture', None, 'fixture')
    index.groups[key] = [dict(status='tentative', heard_utc='2026-09-26T01:02:03Z')]
    rows = station_spreadsheet(b, index, 'fixture', None, 'fixture')
    duplicates = [r for r in rows if r[0].strip('> ') == 'DUP']
    assert len(duplicates) == 2
    assert sorted(r[2] for r in duplicates) == ['NO', 'TENTATIVE 2026-09-26 01:02:03Z']
    unknown = next(r for r in rows if r[0].strip('> ') == 'UNK')
    assert unknown[4:] == ('?', '?', '—')
    for _ in range(len(b.matches) + 1):
        rows = station_spreadsheet(b, index, 'fixture', None, 'fixture', limit=2)
        assert len(rows) <= 2
        assert any(r[0] == '> ' + b.selected.station.ident for r in rows)
        b.move(1)


@pytest.mark.parametrize('columns', [40, 73, 100, 115, 174])
@pytest.mark.parametrize('height', [10, 15])
def test_spreadsheet_alignment_selected_visibility_and_plain_period(columns, height):
    values = [('  A', '300', 'NO', '東京 e\u0301' * 100, '1234', '8.197', '2026-01-01'),
              ('  B', '302', 'TENTATIVE', 'Example location', '?', '?', '—'),
              ('> C', '304', 'CONFIRMED 2026-09-26 01:02:03Z', 'Long name ' * 40, '1500', '10.3', '2026-04-13'),
              ('  D', '306', 'NOT-HEARD', 'Another location', '42', '5', '2025-03-01')]
    rows = main_panel_rows(columns=columns, height=height, radio='radio', station=['C'], reception=['confirmed'],
                           filters='all', help_rows=['n/N browse; w edit'], message='ready', table=values)
    assert len(rows) <= height and all(cell_width(r) == columns - 1 for r in rows)
    assert not any('STATION / CATALOGUE' in r or 'RECEPTION / LOG' in r for r in rows)
    grid = [r for r in rows if r.count('│') > 2]
    assert any('> C' in r for r in grid)
    boundaries = [[cell_width(r[:i]) for i, c in enumerate(r) if c == '│'] for r in grid]
    assert all(b == boundaries[0] for b in boundaries)
    if columns == 174:
        assert all(h in grid[0] for h in ['ID', 'Nominal kHz', 'Logged (UTC)', 'Location', 'Distance km', 'Period s', 'Last (RNA)'])
        selected = next(r for r in grid if '> C' in r)
        assert selected.split('│')[-3].strip() == '10.3'
        assert 'CONFIRMED 2026-09-26 01:02:03Z' in selected
        assert '2026-04-13' in selected
