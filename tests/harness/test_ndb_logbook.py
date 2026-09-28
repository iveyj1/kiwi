from copy import deepcopy
from pathlib import Path

import pytest

from kiwi_client.gui_app import WaterfallGuiModel
from kiwi_client.ndb_logbook import Logbook, cle332_eligible, cle332_report, main, reception_draft
from kiwi_client.rna_catalogue import load_catalogue
from kiwi_client.rna_console import RnaBrowser

FIXTURE = Path(__file__).parents[1] / 'fixtures/rna/catalogue.csv'
PROFILE = dict(listener='Test Listener', receiver='10.0.0.43:8073', timezone='America/Toronto',
               locator='FN25aa', location='Test site', equipment='KiwiSDR', aerial='Loop', remote=True,
               public=False)


def draft():
    browser = RnaBrowser(load_catalogue(FIXTURE))
    browser.set_receiver(PROFILE['receiver'], 378)
    browser.cycle_component()  # Explicit carrier choice; first-time choice is now USB.
    state = WaterfallGuiModel(tuned_khz=378, selected_khz=378).session.state
    return reception_draft(browser, state, receiver=PROFILE['receiver'], source_kind='live',
                           event='CLE332', heard_utc='2026-09-25T16:00:00Z')


def confirmed(**kwargs):
    return dict(draft(), status='confirmed', **kwargs)


def test_save_reopen_duplicate_and_revision_history(tmp_path):
    path = tmp_path / 'log.sqlite'
    reception = draft()
    with Logbook(path) as book:
        assert book.save(reception) == (1, 0)
        assert book.save(reception) == (2, 1)
    reception['ident'] = 'MUTATED'
    with Logbook(path) as book:
        assert book.entries()[0]['ident'] == 'RJ'
        book.revise(1, status='confirmed', heard_utc='2026-09-25T17:02:00Z', notes='copied twice')
        assert book.entries()[0]['status'] == 'confirmed'
        assert book.connection.execute('SELECT count(*) FROM revisions').fetchone()[0] == 3
        with pytest.raises(ValueError):
            book.revise(1, status='invalid')
        assert book.entries()[0]['status'] == 'confirmed'
        assert book.connection.execute('SELECT count(*) FROM revisions').fetchone()[0] == 3
        with pytest.raises(ValueError, match='offset'):
            book.revise(1, heard_utc='2026-09-25T17:02:00')
        with pytest.raises(ValueError, match='unknown log'):
            book.revise(99, notes='missing')


def test_save_failure_rolls_back_reception_and_does_not_report_success(tmp_path, monkeypatch):
    with Logbook(tmp_path / 'log.sqlite') as book:
        def fail(*args):
            raise RuntimeError('simulated audit failure')
        monkeypatch.setattr(book, '_audit', fail)
        with pytest.raises(RuntimeError):
            book.save(draft())
        assert book.entries() == []


def test_logging_requires_current_component_and_freezes_catalogue():
    b = RnaBrowser(load_catalogue(FIXTURE))
    b.set_receiver(PROFILE['receiver'], 378)
    state = WaterfallGuiModel(tuned_khz=378, selected_khz=378).session.state
    with pytest.raises(ValueError, match='tune'):
        reception_draft(b, state, receiver=PROFILE['receiver'], source_kind='live', event=None)
    record = draft()
    assert record['carrier_khz'] == record['component_khz'] == 378
    assert record['catalogue_fields']['USB'] == '405'
    assert record['status'] == 'tentative'


@pytest.mark.parametrize('frequency,ident,eligible', [(190, 'A', True), (530, 'B', True),
    (378, 'RJ', True), (378.405, 'RJ', False), (315, 'AT', False), (312.5, 'X', False),
    (532, 'Z', False), (380, 'UNID', False)])
def test_eligibility_is_nominal_channel(frequency, ident, eligible):
    assert cle332_eligible(frequency, ident) is eligible


def test_golden_report_uses_utc_nominal_and_excludes_repeats():
    first = confirmed(component_khz=378.405, tuned_khz=378.405, component='usb',
                      rf_center_khz=378.405, carrier_offset_hz=405, bandwidth_hz=100)
    second = dict(first, heard_utc='2026-09-26T01:00:00Z')
    text, warnings = cle332_report([second, first], PROFILE)
    assert text == (Path(__file__).parents[1] / 'fixtures/rna/cle332-report.txt').read_text()
    assert '  378  RJ ' in text
    assert 'center 378.405000 kHz; offset +405.0 Hz; BW 100 Hz' in text
    assert len(warnings) == 1 and 'repeat' in warnings[0]


def test_event_window_is_receiver_local_start_inclusive_end_exclusive():
    outside = confirmed(heard_utc='2026-09-25T15:59:59Z')
    end = confirmed(heard_utc='2026-09-28T16:00:00Z')
    inside = confirmed(heard_utc='2026-09-26T00:01:00Z')
    text, warnings = cle332_report([outside, end, inside], PROFILE)
    assert '2026-09-26 00:01' in text
    assert len(warnings) == 2


def test_practice_tentative_general_and_ineligible_do_not_become_event_logs():
    fixture = confirmed(source_kind='fixture')
    general = confirmed(event=None)
    odd = confirmed(carrier_khz=379)
    text, warnings = cle332_report([fixture, general, odd, draft(), confirmed()], PROFILE)
    assert text.endswith('1 NDBs\n')
    assert len(warnings) == 2
    with pytest.raises(ValueError, match='no eligible'):
        cle332_report([fixture, general, odd, draft()], PROFILE)


def test_mixed_receivers_are_blocked_not_silently_filtered():
    other = confirmed(receiver='10.0.0.42:8073')
    with pytest.raises(ValueError, match='another receiver'):
        cle332_report([confirmed(), other], PROFILE)


@pytest.mark.parametrize('changes', [{'locator': 'FN25'}, {'timezone': ''}, {'remote': 'yes'},
                                   {'public': True}, {'equipment': ''}])
def test_report_requires_operator_site_and_public_receiver_metadata(changes):
    with pytest.raises(ValueError):
        cle332_report([confirmed()], dict(PROFILE, **changes))


def test_cli_export_and_no_overwrite(tmp_path, capsys):
    path = tmp_path / 'log.sqlite'
    with Logbook(path) as book:
        book.save(confirmed())
    profile = tmp_path / 'profile.toml'
    import json
    profile.write_text('\n'.join(f'{key} = {json.dumps(value)}' for key, value in PROFILE.items()))
    output = tmp_path / 'report.txt'
    args = ['--logbook', str(path), 'export-cle332', '--profile', str(profile), '--output', str(output)]
    assert main(args) == 0
    assert output.read_text().startswith('Subject: CLE332 FINAL')
    assert 'Draft only' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(args)


def test_legacy_report_reconstructs_actual_center_and_includes_notes():
    entry = confirmed(tuned_khz=378.375, mode='cw', low_cut_hz=825, high_cut_hz=875,
                      cw_offset_hz=-800, notes='Copied twice\nclear')
    for name in ('rf_center_khz', 'carrier_offset_hz', 'bandwidth_hz'):
        entry.pop(name)
    text, warnings = cle332_report([entry], PROFILE)
    assert 'center 378.425000 kHz; offset +425.0 Hz; BW 50 Hz; Copied twice clear' in text


@pytest.mark.parametrize('answer,allowed', [('yes\n', True), ('n\n', False), ('', False)])
def test_receiver_mismatch_prompts_on_stderr_and_never_silently_filters(tmp_path, capsys, monkeypatch, answer, allowed):
    import io
    import json
    import sys
    path = tmp_path / 'log.sqlite'
    entry = confirmed(receiver='10.0.0.42:8073', notes='*')
    with Logbook(path) as book:
        book.save(entry)
        original = book.entries()
    profile = tmp_path / 'profile.toml'
    profile.write_text('\n'.join(f'{key} = {json.dumps(value)}' for key, value in PROFILE.items()))
    output = tmp_path / 'report.txt'
    monkeypatch.setattr(sys, 'stdin', io.StringIO(answer))
    args = ['--logbook', str(path), 'export-cle332', '--profile', str(profile), '--output', str(output)]
    if allowed:
        assert main(args) == 0
        text = output.read_text()
        assert 'REVIEW REQUIRED' in text and '10.0.0.42:8073' in text
        assert '1 NDBs' in text and '; *' in text
    else:
        with pytest.raises(SystemExit): main(args)
        assert not output.exists()
    captured = capsys.readouterr()
    assert '[y/N]' in captured.err and not captured.out
    with Logbook(path) as book:
        assert book.entries() == original


def test_future_schema_not_modified(tmp_path):
    import sqlite3
    path = tmp_path / 'log.sqlite'
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError, match='unsupported'):
        Logbook(path)
