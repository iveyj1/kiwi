from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from kiwi_client.kiwi_label_history import build_label_stage, note_dates
from kiwi_client.log_browser import cells, create_window, reception_summary
from kiwi_client.log_browser_data import BrowserFilter, LogWorkspace, StagedLogSource
from kiwi_client.wwsu_history import write_stage

FIXTURE = Path(__file__).parents[1] / 'fixtures/kiwi/label-history.json'


def stage(tmp_path):
    data = build_label_stage(FIXTURE)
    path = tmp_path / 'labels.json'
    write_stage(path, data)
    return path, data, StagedLogSource(path).load()


def test_label_stage_counts_and_lossless_source(tmp_path):
    original = FIXTURE.read_bytes()
    path, data, rows = stage(tmp_path)
    assert data['summary']['selected_labels'] == 11
    assert len(rows) == 15
    assert data['summary']['row_kinds'] == {'reception': 9, 'label': 6}
    assert len(data['excluded']) == 5
    assert data['original_archive'] == json.loads(original)
    assert FIXTURE.read_bytes() == original
    assert all(r.reference.revision == hashlib.sha256(original).hexdigest() for r in rows)
    assert all(r.frequency_basis == 'label' and r.source == 'Kiwi labels' and not r.event for r in rows)
    assert all(r.status != 'confirmed' and r.distance_km is None for r in rows)
    assert len({r.id for r in rows}) == len(rows)
    assert data['records'] == build_label_stage(FIXTURE)['records']
    with pytest.raises(FileExistsError): write_stage(path, data)


def test_multiple_times_segments_and_utc_policy(tmp_path):
    _, _, rows = stage(tmp_path)
    ytl = [r for r in rows if r.ident == 'YTL']
    assert [r.heard_utc for r in ytl] == ['2022-12-18T04:52:00Z', '2023-10-28T01:46:00Z']
    assert 'LOG40' not in ytl[0].notes and 'LOG40' in ytl[1].notes
    assert json.loads(ytl[0].evidence_json)['note_token']['timezone_basis'].startswith('UTC assumed')
    explicit = next(r for r in rows if r.ident == 'AAA')
    assert explicit.location == '"Example"'
    assert json.loads(explicit.evidence_json)['original_row'][2] == 'AAA %22Example%22'
    assert json.loads(explicit.evidence_json)['note_token']['timezone_basis'] == 'explicit Z'
    assert 'Wellbrook' in explicit.notes


@pytest.mark.parametrize('token', ['2022-02-09-10T0446', '2022-11-18T132Z', '2022-12-180222',
                                  '2022-11-19T04017', '2022-02-30T0330', '2022-11-19T2561'])
def test_malformed_timestamp_never_salvages_partial_date(token):
    parsed = note_dates(token)
    assert len(parsed) == 1
    assert parsed[0]['heard_utc'] == '' and parsed[0]['precision'] == 'unknown'
    assert parsed[0]['issue'] and parsed[0]['token'] == token


def test_undated_and_date_only_are_not_invented_instants(tmp_path):
    _, _, rows = stage(tmp_path)
    blank = next(r for r in rows if r.ident == 'HHH')
    assert blank.status == 'reference' and blank.row_kind == 'label' and blank.heard_utc == ''
    assert cells(blank)[0] == '—'
    assert 'not a reception' in reception_summary(blank)
    assert not BrowserFilter(date_to='2024-01-01').matches(blank)
    assert BrowserFilter().matches(blank)
    partial = next(r for r in rows if r.ident == 'BBB' and r.precision == 'day')
    assert partial.heard_utc == '2022-10-30' and cells(partial)[0] == '2022-10-30'
    assert partial.status == 'review'
    assert BrowserFilter(date_from='2022-10-30', date_to='2022-10-30').matches(partial)
    early = next(r for r in rows if r.ident == 'GGG')
    assert early.heard_utc.startswith('2011-') and early.status == 'review'


def test_frequencies_and_cross_source_identity_are_not_guessed(tmp_path):
    _, _, rows = stage(tmp_path)
    record = next(r for r in rows if r.ident == 'YTL')
    assert record.frequency_khz == 328.41
    assert cells(record)[2] == '328.41*'
    assert '(label frequency)' in reception_summary(record)
    assert record.station_key != replace(record, frequency_basis='nominal').station_key
    assert record.station_key != replace(record, location='Elsewhere').station_key
    repeated = [r for r in rows if r.ident == 'JJJ']
    assert len(repeated) == 2 and repeated[0].heard_utc == repeated[1].heard_utc
    assert repeated[0].id != repeated[1].id


def test_staged_labels_cannot_claim_nominal_or_live_status(tmp_path):
    path, data, _ = stage(tmp_path)
    data['records'][0]['frequency_basis'] = 'nominal'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='nominal'): StagedLogSource(path).load()
    data['records'][0]['frequency_basis'] = 'label'
    data['records'][0]['status'] = 'confirmed'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='confirmation'): StagedLogSource(path).load()


def test_range_and_bad_input_fail_closed(tmp_path):
    with pytest.raises(ValueError, match='range'): build_label_stage(FIXTURE, minimum_khz=531, maximum_khz=530)
    path = tmp_path / 'broken.json'
    path.write_text('{"dx": [[300, "CW", "AAA"]]}')
    with pytest.raises(ValueError, match='dx\\[0\\]'): build_label_stage(path)


def test_band_edges_and_service_plugin(tmp_path):
    path = tmp_path / 'edges.json'
    path.write_text(json.dumps({'dx': [
        [190, 'CW', 'AAA', '2022-11-17T0330'],
        [530, 'CWN', 'BBB', '2022-11-17T0330'],
        [189.99, 'CW', 'CCC', '2022-11-17T0330'],
        [530.01, 'CW', 'DDD', '2022-11-17T0330'],
        [300, 'IQ', 'EEE', '2022-11-17T0330', {'p': 'fsk'}],
    ]}))
    data = build_label_stage(path)
    assert [row['ident'] for row in data['records']] == ['AAA', 'BBB']
    assert len(data['excluded']) == 3


def test_label_history_offscreen(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    path, _, _ = stage(tmp_path)
    before = path.read_bytes()
    workspace = LogWorkspace([StagedLogSource(path)])
    views = tmp_path / 'views.json'
    views.write_text(json.dumps({'schema': 1, 'views': {'All records': {'search': 'id:YTL'}}}))
    window = create_window(workspace, settings_path=views)
    window.show()
    app.processEvents()
    assert window.proxy.rowCount() == 15
    assert '6 undated label references' in window.notice.text()
    window.view.setCurrentIndex(window.view.findText('All records (saved)'))
    window.choose_view()
    assert window.proxy.rowCount() == 2  # old saved names cannot collide with new builtins
    window.clear_filters()
    window.search.setText('id:YTL')
    assert window.proxy.rowCount() == 2
    window.show_history()
    assert window.proxy.rowCount() == 2
    assert 'label text/frequency' in window.context.text()
    window.back()
    window.search.setText('id:HHH')
    assert window.proxy.rowCount() == 1
    assert 'not a reception' in window.details.toPlainText()
    window.date_to.setText('2024-01-01')
    assert window.proxy.rowCount() == 0
    window.close()
    assert path.read_bytes() == before


def test_filter_selection_remains_visible(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    _, _, original = stage(tmp_path)
    base = next(r for r in original if r.ident == 'YTL')
    rows = [replace(base, id=f'row-{i:03}', source='A' if i % 2 else 'B') for i in range(100)]
    source = SimpleNamespace(path=tmp_path / 'synthetic-source', load=lambda: rows)
    window = create_window(LogWorkspace([source]))
    window.resize(1000, 500)
    window.show()
    app.processEvents()
    window.source.setCurrentIndex(window.source.findData('A'))
    app.processEvents()
    window.table.scrollToBottom()
    window.source.setCurrentIndex(window.source.findData('B'))
    app.processEvents()
    assert window.selected().source == 'B'
    assert window.table.visualRect(window.table.currentIndex()).intersects(window.table.viewport().rect())
    window.close()
