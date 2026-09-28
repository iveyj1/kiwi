import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from kiwi_client.log_browser import cells, create_window, main, save_views
from kiwi_client.log_browser_data import BrowserFilter, LogWorkspace, NativeLogSource, StagedLogSource
from kiwi_client.wwsu_history import build_stage, coordinate, report_rows, write_stage

FIXTURES = Path(__file__).parents[1] / 'fixtures/wwsu'


def native(path):
    payload = dict(heard_utc='2024-01-01T01:00:31+00:00', ident='AAA', carrier_khz=200,
                   receiver='fixture receiver', status='confirmed', source_kind='fixture', event='TEST',
                   notes='original note', distance_km=111.5,
                   catalogue_fields={'ITU': 'CAN', 'SP': 'ON', "'Name' and Location": 'Example'},
                   future_field={'preserve': True})
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA user_version=1')
    connection.execute('CREATE TABLE receptions (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
    connection.execute('INSERT INTO receptions VALUES (?,?)', (17, json.dumps(payload)))
    connection.commit()
    connection.close()
    return payload


def staged(tmp_path):
    root = tmp_path / 'archive'
    root.mkdir()
    fixture = json.loads((FIXTURES / 'history.json').read_text())
    for filename in ('ndbdata2024_Jan_01_1200.wbs', 'ndbdata2024_Jan_02_1200.wbs'):
        (root / filename).write_text(filename)
    shutil.copyfile(FIXTURES / 'SessionReport_example.csv', root / 'SessionReport_example.csv')
    def read_table(path, table):
        tables = dict(NDBInformation=fixture['stations'], NewBeacons=fixture['personal'], ListeningLocation=fixture['sites'])
        tables['NDBLog'] = fixture['older' if '_01_' in path.name else 'newer']
        return copy.deepcopy(tables[table])
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    data = build_stage(root, read_table)
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    path = tmp_path / 'stage.json'
    write_stage(path, data)
    return path, data


def test_native_readonly_reference_and_revision(tmp_path):
    path = tmp_path / 'log ? space.sqlite'
    payload = native(path)
    before = path.read_bytes()
    source = NativeLogSource(path)
    record = source.load()[0]
    assert path.read_bytes() == before
    assert record.reference.key == '17'
    assert record.heard_utc == '2024-01-01T01:00:31Z'
    assert json.loads(record.evidence_json)['future_field'] == {'preserve': True}
    assert record.reference.revision == hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    # A future editor can identify the same record while detecting an intervening edit.
    payload['notes'] = 'external edit'
    with sqlite3.connect(path) as db:
        db.execute('UPDATE receptions SET payload=? WHERE id=17', (json.dumps(payload),))
    updated = source.load()[0]
    assert updated.id == record.id
    assert updated.reference.revision != record.reference.revision


def test_missing_native_never_created_and_reload_retains_snapshot(tmp_path):
    path = tmp_path / 'log.sqlite'
    workspace = LogWorkspace([NativeLogSource(path)])
    workspace.reload()
    assert workspace.errors and not path.exists()
    native(path)
    workspace.reload()
    assert not workspace.errors and len(workspace.records) == 1
    with sqlite3.connect(path) as db: db.execute('UPDATE receptions SET payload=?', ('broken',))
    workspace.reload()
    assert workspace.errors and len(workspace.records) == 1
    assert 'previous snapshot' in workspace.errors[0]


def test_source_reordering_cannot_substitute_an_unrelated_cached_log(tmp_path):
    a, b = tmp_path / 'a.sqlite', tmp_path / 'b.sqlite'
    native(a)
    native(b)
    workspace = LogWorkspace([NativeLogSource(a), NativeLogSource(b)])
    workspace.reload()
    workspace.sources.pop(0)
    b.unlink()
    workspace.reload()
    assert workspace.errors
    assert len(workspace.records) == 1
    assert workspace.records[0].reference.path == str(b)


def test_read_committed_wal_data(tmp_path):
    path = tmp_path / 'live.sqlite'
    payload = native(path)
    with sqlite3.connect(path) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        payload['notes'] = 'committed WAL entry'
        writer.execute('UPDATE receptions SET payload=?', (json.dumps(payload),))
        writer.commit()
        assert NativeLogSource(path).load()[0].notes == 'committed WAL entry'
        writer.execute('UPDATE receptions SET payload=?', ('not yet committed',))
        assert NativeLogSource(path).load()[0].notes == 'committed WAL entry'
        writer.rollback()


def test_stage_preserves_versions_duplicates_deleted_and_personal(tmp_path):
    path, data = staged(tmp_path)
    records = StagedLogSource(path).load()
    assert len(records) == 7  # four latest, one older-only, two report review items
    assert len({r.id for r in records}) == len(records)
    older = next(r for r in records if r.ident == 'BBB')
    assert older.status == 'review' and older.source == 'WWSU older-only'
    assert any('Absent' in flag for flag in older.flags)
    duplicates = [r for r in records if r.heard_utc.endswith('01:02:00Z') and r.source == 'WWSU database']
    assert len(duplicates) == 2
    assert all(any('same-minute' in flag for flag in r.flags) for r in duplicates)
    changed = next(r for r in records if r.notes == 'new')
    evidence = json.loads(changed.evidence_json)
    assert len(evidence['backup_versions']) == 2
    assert evidence['report_evidence'][0]['notes'] == 'Sending YY'
    assert any('differ' in flag for flag in changed.flags)
    personal = next(r for r in records if r.ident == 'UUU')
    assert personal.distance_km is None
    assert json.loads(personal.evidence_json)['station']['GenNotes'] == 'uncertain identity'
    assert all(r.status != 'confirmed' and not r.event for r in records)
    assert len(data['sources']) == 3
    with pytest.raises(FileExistsError): write_stage(path, data)
    assert len(StagedLogSource(path).load()) == 7


def test_report_comment_miles_and_minute_precision(tmp_path):
    path, _ = staged(tmp_path)
    report = next(r for r in StagedLogSource(path).load() if r.ident == 'ZZZ')
    assert report.distance_km == pytest.approx(16.09344)
    assert report.notes == 'Sending YY'
    assert cells(report)[0] == '2024-02-01 04:10'
    assert report.status == 'review'


def test_text_report_with_missing_distance_and_comment(tmp_path):
    path = tmp_path / 'SessionReport_text.txt'
    path.write_text('Listening Location: Fixture Beverage\n'
        'YYYY-MM-DD UTC   kHz      Call       mi    Cmt  New Grid   Location\n'
        '2024-01-02 02:34 336      MET                    Y  JJ00aa Unknown, XUN\n')
    row = list(report_rows(path))[0]
    assert row[1:5] == ('MET', 336.0, 'XUN', '')
    assert row[6] is None


def test_stage_rejects_promoted_status(tmp_path):
    path, data = staged(tmp_path)
    data['records'][0]['status'] = 'confirmed'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='confirmation'): StagedLogSource(path).load()


def test_coordinates_and_filter_grouping(tmp_path):
    assert coordinate('422445N') == pytest.approx(42 + 24 / 60 + 45 / 3600)
    assert coordinate('W080000050') == pytest.approx(-80 - .5 / 3600)
    assert coordinate('N42600000') is None
    assert coordinate('900001N') is None
    assert coordinate('garbage422445N') is None
    path = tmp_path / 'log.sqlite'
    native(path)
    record = NativeLogSource(path).load()[0]
    assert BrowserFilter(search='aaa original', date_from='2024-01-01', date_to='2024-01-01',
                         minimum_khz=200, maximum_khz=200).matches(record)
    assert BrowserFilter(search='id:AAA original').matches(record)
    assert not BrowserFilter(search='id:AA').matches(record)
    assert not BrowserFilter(source='WWSU database').matches(record)
    assert not BrowserFilter(status='tentative').matches(record)
    assert not BrowserFilter(event='CLE332').matches(record)
    assert not BrowserFilter(review_only=True).matches(record)
    assert not BrowserFilter(date_to='2023-12-31').matches(record)
    assert not BrowserFilter(minimum_khz=201).matches(record)
    assert record.station_key == replace(record, id='other', source='WWSU database').station_key
    assert record.station_key != replace(record, region='QC').station_key
    assert replace(record, region='XX').station_key == replace(record, region='').station_key


def test_dry_run_does_not_modify_sources_or_create_settings(tmp_path, capsys):
    path = tmp_path / 'log.sqlite'
    native(path)
    stage, _ = staged(tmp_path)
    before = [p.read_bytes() for p in (path, stage)]
    settings = tmp_path / 'views.json'
    assert main(['--logbook', str(path), '--stage', str(stage), '--dry-run', '--settings', str(settings)]) == 0
    assert json.loads(capsys.readouterr().out)['records'] == 8
    assert before == [p.read_bytes() for p in (path, stage)]
    assert not settings.exists()


def test_offscreen_browser_filter_history_sort_reload(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6 import QtCore, QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = tmp_path / 'log.sqlite'
    native(path)
    stage, _ = staged(tmp_path)
    workspace = LogWorkspace([NativeLogSource(path), StagedLogSource(stage)])
    before = [p.read_bytes() for p in (path, stage)]
    window = create_window(workspace)
    window.show()
    app.processEvents()
    assert window.proxy.rowCount() == 8
    window.search.setText('ZZZ')
    assert window.proxy.rowCount() == 1
    assert window.selected().ident == 'ZZZ'
    window.clear_filters()
    window.source.setCurrentIndex(window.source.findData('Native fixture'))
    assert window.proxy.rowCount() == 1
    window.show_history()
    assert window.proxy.rowCount() == 5  # native, three database rows, ambiguous report
    window.back()
    assert window.proxy.rowCount() == 1
    reference = window.selected().reference
    window.reload()
    assert window.selected().reference == reference
    assert not window.model.flags(window.model.index(0, 0)) & QtCore.Qt.ItemFlag.ItemIsEditable
    window.clear_filters()
    window.table.sortByColumn(2, QtCore.Qt.SortOrder.AscendingOrder)
    assert window.proxy.index(0, 2).data() == '200'
    window.restore_filter(dict(source='Not loaded'))
    assert window.proxy.rowCount() == 0  # saved missing sources must not broaden to All
    window.date_from.setText('invalid')
    assert 'Filter not applied' in window.notice.text()
    window.close()
    assert before == [p.read_bytes() for p in (path, stage)]


def test_view_preferences_are_separate_atomic_json(tmp_path):
    path = tmp_path / 'prefs/views.json'
    views = {'Example': asdict(BrowserFilter(search='AAA', source='WWSU database'))}
    save_views(path, views)
    assert json.loads(path.read_text()) == dict(schema=1, views=views)
    assert list(path.parent.iterdir()) == [path]
