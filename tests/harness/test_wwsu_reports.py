import json

import pytest

from kiwi_client.wwsu_history import build_stage, report_rows

HEADER = 'YYYY-MM-DD ,UTC ,kHz ,Call ,mi ,Cmt ,New ,Grid ,Location ,State ,Country\n'


def test_report_encoding_units_and_quoted_commas(tmp_path):
    path = tmp_path / 'SessionReport_example.csv'
    text = ('Listening Location: Fixture\n' + HEADER.replace('mi', 'km') +
            '2024-01-01,01:00,200,AAA,10,1,,EN00aa,"Place, extra",ON,CAN\n'
            'Session Comments:\n 1 - Café\n')
    path.write_bytes(text.replace('\n', '\r\n').encode('cp1252'))
    row = list(report_rows(path))[0]
    assert row[5] == 'Place, extra'
    assert row[6] == 10
    assert row[7] == 'Café'
    assert row[-1]['distance_basis'] == 'report km'
    assert row[-1]['report_context'][0] == 'Listening Location: Fixture'
    path.write_text(text.replace('UTC', 'Local'))
    with pytest.raises(ValueError, match='UTC'): list(report_rows(path))


def test_duplicate_reports_and_frequency_conflicts_are_reviewable(tmp_path):
    backup = tmp_path / 'ndbdata2024_Jan_01_1200.wbs'
    backup.write_bytes(b'synthetic MDB export fixture')
    tables = dict(
        NDBLog=[dict(Beacon_ID='1', LoggedLocation='1', ReceptionDate='20240101', ReceptionTime='0100',
                     ReceptionComments='', SignalStrength='S-2')],
        NDBInformation=[dict(Beacon_ID='1', Ident='AAA', Frequency='201', Country='CAN', State='ON', City='Example')],
        NewBeacons=[], ListeningLocation=[dict(ID='1', LocationName='Fixture')])
    row = '2024-01-01,01:00,200,AAA,10,,,EN00aa,Example,ON,CAN\n'
    # Preserve within-report multiplicity but not duplicate copies of that report.
    for name in ('SessionReport_first.csv', 'SessionReport_copy.csv'):
        (tmp_path / name).write_text('Listening Location: Fixture\n' + HEADER + row * 2)
    data = build_stage(tmp_path, lambda path, name: tables[name])
    records = data['records']
    assert len(records) == 3
    reports = [r for r in records if r['source'] == 'WWSU report-only']
    assert len(reports) == 2
    assert len({r['id'] for r in reports}) == 2
    for record in reports:
        assert any('different database frequency' in flag for flag in record['flags'])
        raw = json.loads(record['evidence_json'])
        assert len(raw['reports']) == 2
        assert raw['reports'][0]['possible_database_matches'] == [records[0]['id']]
    again = build_stage(tmp_path, lambda path, name: tables[name])
    assert [r['id'] for r in again['records']] == [r['id'] for r in records]


def test_duplicate_same_report_event_does_not_disappear_into_one_database_row(tmp_path):
    (tmp_path / 'ndbdata2024_Jan_01_1200.wbs').write_bytes(b'fixture')
    tables = dict(
        NDBLog=[dict(Beacon_ID='1', LoggedLocation='1', ReceptionDate='20240101', ReceptionTime='0100')],
        NDBInformation=[dict(Beacon_ID='1', Ident='AAA', Frequency='200', Country='CAN', State='ON')],
        NewBeacons=[], ListeningLocation=[dict(ID='1', LocationName='Fixture')])
    row = '2024-01-01,01:00,200,AAA,10,,,EN00aa,Example,ON,CAN\n'
    (tmp_path / 'SessionReport.csv').write_text('Listening Location: Fixture\n' + HEADER + row * 2)
    records = build_stage(tmp_path, lambda path, name: tables[name])['records']
    assert len(records) == 2
    assert any('Repeated report row' in flag for flag in records[1]['flags'])
