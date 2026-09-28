"""Transactional human reception log and offline CLE332 plain-text export.

No receiver connection, station identification, or email submission occurs here.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import tomllib
from zoneinfo import ZoneInfo

from kiwi_client.station_memory import passband_center_khz, catalogue_reference_khz


def utc_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('hearing time must include Z or an explicit UTC offset')
    return result.astimezone(timezone.utc)


def clean_text(value) -> str:
    return ' '.join(str(value).split())


def reception_draft(browser, state, *, receiver: str, source_kind: str, event: str | None,
                    heard_utc: str | None = None) -> dict:
    match = browser.selected
    component = browser.component
    if match is None or component is None:
        raise ValueError('select an RNA station first')
    actual_frequency = passband_center_khz(state) if component.kind == 'stored' else state.frequency_khz
    expected_frequency = (component.frequency_khz if component.kind == 'stored' else
                          catalogue_reference_khz(state, component.frequency_khz))
    if not math.isclose(actual_frequency, expected_frequency, abs_tol=.000001, rel_tol=0):
        raise ValueError('tune the selected RNA component with y before logging')
    site = browser.sites.get(receiver)
    return dict(schema=1, event=event, status='tentative', source_kind=source_kind,
                heard_utc=heard_utc or datetime.now(timezone.utc).isoformat(timespec='seconds'),
                receiver=receiver, site=None if site is None else asdict(site),
                station_key=match.station.key, ident=match.station.ident,
                carrier_khz=match.station.carrier_khz, component=component.kind,
                component_khz=component.frequency_khz, tuned_khz=state.frequency_khz,
                rf_center_khz=passband_center_khz(state),
                carrier_offset_hz=(passband_center_khz(state) - match.station.carrier_khz) * 1000,
                bandwidth_hz=state.high_cut_hz - state.low_cut_hz,
                mode=state.mode, low_cut_hz=state.low_cut_hz, high_cut_hz=state.high_cut_hz,
                cw_offset_hz=state.cw_offset_hz, distance_km=match.distance_km,
                catalogue_sha256=browser.catalogue.sha256,
                catalogue_fields=dict(match.station.raw_fields),
                notes='*' if browser.memory.records.get(match.station.key, {}).get('marked', False) else '')


def validate_reception(record: dict) -> None:
    if record.get('schema') != 1:
        raise ValueError('unsupported reception schema')
    if record.get('status') not in {'tentative', 'confirmed', 'rejected', 'not-heard'}:
        raise ValueError('status must be tentative, confirmed, rejected or not-heard')
    if record.get('source_kind') not in {'live', 'fixture'}:
        raise ValueError('source must be live or fixture')
    utc_time(record['heard_utc'])
    for field in ('receiver', 'station_key', 'ident', 'catalogue_sha256'):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f'{field} is required')
    for field in ('carrier_khz', 'component_khz', 'tuned_khz'):
        value = record.get(field)
        if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{field} must be a positive finite frequency')


class Logbook:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(path)
        try:
            version = self.connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f'unsupported logbook version {version}')
            with self.connection:
                self.connection.execute('CREATE TABLE IF NOT EXISTS receptions (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
                self.connection.execute('CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY, reception_id INTEGER NOT NULL, changed_utc TEXT NOT NULL, payload TEXT NOT NULL)')
                self.connection.execute('PRAGMA user_version=1')
        except Exception:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def entries(self) -> list[dict]:
        return [dict(json.loads(payload), log_id=key) for key, payload in
                self.connection.execute('SELECT id, payload FROM receptions ORDER BY id')]

    def save(self, record: dict) -> tuple[int, int]:
        validate_reception(record)
        # Round-trip isolates callers and rejects non-JSON/nonfinite metadata.
        payload = json.dumps(record, allow_nan=False, sort_keys=True)
        duplicates = sum(entry['station_key'] == record['station_key'] and
                         entry['receiver'] == record['receiver'] and entry.get('event') == record.get('event') and
                         entry['status'] not in {'rejected', 'not-heard'} for entry in self.entries())
        with self.connection:
            # Deletions must not reuse an audited reception ID (including old schemas).
            cursor = self.connection.execute('''INSERT INTO receptions(id, payload)
                SELECT max(coalesce((SELECT max(id) FROM receptions), 0),
                           coalesce((SELECT max(reception_id) FROM revisions), 0)) + 1, ?''', (payload,))
            key = cursor.lastrowid
            self._audit(key, payload)
        return key, duplicates

    def revise(self, key: int, *, status=None, heard_utc=None, notes=None, expected: dict | None = None) -> None:
        with self.connection:
            row = self.connection.execute('SELECT payload FROM receptions WHERE id=?', (key,)).fetchone()
            if row is None:
                raise ValueError(f'unknown log entry {key}')
            record = json.loads(row[0])
            if expected is not None and dict(record, log_id=key) != expected:
                raise ValueError('entry changed since the form opened; cancel and reopen with w')
            for field, value in [('status', status), ('heard_utc', heard_utc), ('notes', notes)]:
                if value is not None:
                    record[field] = value
            validate_reception(record)
            payload = json.dumps(record, allow_nan=False, sort_keys=True)
            cursor = self.connection.execute('UPDATE receptions SET payload=? WHERE id=? AND payload=?', (payload, key, row[0]))
            if cursor.rowcount != 1:
                raise ValueError('entry changed concurrently; reopen before editing')
            self._audit(key, payload)

    def delete(self, key: int, *, expected: dict | None = None) -> None:
        """Remove from current receptions while preserving a deletion audit record."""
        with self.connection:
            row = self.connection.execute('SELECT payload FROM receptions WHERE id=?', (key,)).fetchone()
            if row is None:
                raise ValueError(f'unknown log entry {key}')
            record = json.loads(row[0])
            if expected is not None and dict(record, log_id=key) != expected:
                raise ValueError('entry changed since the form opened; cancel and reopen with w')
            cursor = self.connection.execute('DELETE FROM receptions WHERE id=? AND payload=?', (key, row[0]))
            if cursor.rowcount != 1:
                raise ValueError('entry changed concurrently; reopen before deleting')
            self._audit(key, json.dumps(dict(record, deleted_utc=datetime.now(timezone.utc).isoformat()),
                                       allow_nan=False, sort_keys=True))

    def _audit(self, key, payload):
        self.connection.execute('INSERT INTO revisions(reception_id, changed_utc, payload) VALUES (?, ?, ?)',
                                (key, datetime.now(timezone.utc).isoformat(), payload))


def cle332_eligible(carrier_khz: float, ident: str) -> bool:
    return (190 <= carrier_khz <= 530 and carrier_khz % 2 == 0 and
            ident.strip().upper() not in {'', '?', '--', 'UNID', 'UNKNOWN', 'NONE'})


class ReceiverMismatch(ValueError):
    """Export requires an explicit human decision about receiver identity."""


def cle332_report(entries: list[dict], profile: dict, *, allow_receiver_mismatch: bool = False) -> tuple[str, tuple[str, ...]]:
    """Produce a draft; mismatched receiver identities require explicit consent."""
    required = ('listener', 'receiver', 'timezone', 'locator', 'location', 'equipment', 'aerial')
    for field in required:
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            raise ValueError(f'report profile requires {field}')
        if 'EXAMPLE' in profile[field].upper():
            raise ValueError(f'replace example report metadata: {field}')
    if not re.fullmatch(r'[A-Ra-r]{2}[0-9]{2}[A-Xa-x]{2}', profile['locator']):
        raise ValueError('report requires a six-character Maidenhead locator')
    zone = ZoneInfo(profile['timezone'])
    if not isinstance(profile.get('remote'), bool) or not isinstance(profile.get('public'), bool):
        raise ValueError('profile requires explicit remote and public booleans')
    if profile['public'] and profile['remote'] and not re.match(r'https?://\S+$', profile.get('web_address', '')):
        raise ValueError('a publicly available remote receiver requires its web address')
    event_rows = [e for e in entries if e.get('event') == 'CLE332' and e['status'] == 'confirmed']
    # Do not silently omit other receivers to make a noncompliant event log appear valid.
    live_receivers = {e['receiver'] for e in event_rows if e['source_kind'] == 'live'}
    receiver_warning = None
    if live_receivers - {profile['receiver']}:
        receiver_warning = ('Receiver mismatch: CLE332 contains confirmed event entries from another receiver. '
                            f'Profile: {profile["receiver"]}; logged: {", ".join(sorted(live_receivers))}. '
                            'CLE332 permits only one receiver; an address change may refer to the same physical receiver. '
                            'Continuing does not establish compliance or change the saved evidence.')
        if not allow_receiver_mismatch:
            raise ReceiverMismatch(receiver_warning)
    start = datetime(2026, 9, 25, 12, tzinfo=zone).astimezone(timezone.utc)
    end = datetime(2026, 9, 28, 12, tzinfo=zone).astimezone(timezone.utc)
    warnings = [receiver_warning] if receiver_warning else []
    accepted = []
    for entry in event_rows:
        label = f'entry {entry.get("log_id", "?")} {entry["ident"]}'
        if entry['source_kind'] != 'live':
            warnings.append(f'{label}: fixture/practice excluded')
            continue
        site = entry.get('site')
        if site and site['timezone'] != profile['timezone']:
            raise ValueError(f'{label}: logged site timezone differs from report profile')
        when = utc_time(entry['heard_utc'])
        if not start <= when < end:
            warnings.append(f'{label}: outside receiver-local event window')
            continue
        if not cle332_eligible(entry['carrier_khz'], entry['ident']):
            warnings.append(f'{label}: ineligible nominal channel or unidentified station')
            continue
        accepted.append((when, entry))
    latest = {}
    for when, entry in sorted(accepted, key=lambda item: (item[0], item[1].get('log_id', 0)), reverse=True):
        if entry['station_key'] in latest:
            warnings.append(f'entry {entry.get("log_id", "?")}: older repeat reception omitted from report')
            continue
        latest[entry['station_key']] = (when, entry)
    rows = []
    for when, entry in sorted(latest.values(), key=lambda item: (item[0], item[1]['carrier_khz'], item[1]['ident'])):
        fields = entry['catalogue_fields']
        optional = clean_text(' '.join([fields.get("'Name' and Location", ''), fields.get('SP', ''), fields.get('ITU', '')]))
        notes = clean_text(entry.get('notes', ''))
        if notes:
            optional += ' ; ' + notes
        distance = entry.get('distance_km')
        rows.append((f'{when:%Y-%m-%d}', f'{when:%H:%M}', f'{entry["carrier_khz"]:g}',
                     clean_text(entry['ident']), '?' if distance is None else f'{distance:.0f}', optional.strip()))
    if not rows:
        raise ValueError('no eligible confirmed live receptions for CLE332')
    headings = ('Date (UTC)', 'UTC', 'kHz', 'ID', 'Distance (km)', 'Location')
    widths = (10, 5, max(5, *(len(row[2]) for row in rows)),
              max(3, *(len(row[3]) for row in rows)),
              max(len(headings[4]), *(len(row[4]) for row in rows)))
    def report_line(row):
        columns = [value.rjust(width) if i in (2, 4) else value.ljust(width)
                   for i, (value, width) in enumerate(zip(row, widths))]
        return ('  '.join([*columns, row[5]])).rstrip()
    lines = [report_line(row) for row in rows]
    header = ['Subject: CLE332 FINAL', '', clean_text(profile['listener']),
              f'Listening location: {clean_text(profile["location"])} ({profile["locator"].upper()})',
              f'Receiver: {clean_text(profile["equipment"])}',
              f'Aerial: {clean_text(profile["aerial"])}']
    if profile['remote']:
        header.append('Remote receiver: ' + clean_text(profile.get('web_address') or profile['receiver']))
    if receiver_warning:
        header.append('REVIEW REQUIRED — ' + clean_text(receiver_warning))
    header.extend(['', report_line(headings), *lines, '', f'{len(lines)} NDBs', ''])
    return '\n'.join(header), tuple(warnings)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Inspect/revise a local logbook or preview CLE332 plain-text email')
    parser.add_argument('--logbook', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    edit = sub.add_parser('edit')
    edit.add_argument('id', type=int)
    edit.add_argument('--status', choices=['tentative', 'confirmed', 'rejected', 'not-heard'])
    edit.add_argument('--heard-utc')
    edit.add_argument('--notes')
    delete = sub.add_parser('delete')
    delete.add_argument('id', type=int)
    delete.add_argument('--yes', action='store_true', help='confirm removal from current receptions; audit retained')
    export = sub.add_parser('export-cle332')
    export.add_argument('--profile', type=Path, required=True)
    export.add_argument('--output', type=Path, help='new file only; omitted means stdout preview')
    args = parser.parse_args(argv)
    try:
        if not args.logbook.is_file():
            raise ValueError('logbook does not exist; refusing to create an empty review/export database')
        with Logbook(args.logbook) as book:
            if args.command == 'list':
                print(json.dumps(book.entries(), indent=2))
            elif args.command == 'edit':
                book.revise(args.id, status=args.status, heard_utc=args.heard_utc, notes=args.notes)
            elif args.command == 'delete':
                if not args.yes:
                    raise ValueError('delete requires --yes confirmation')
                book.delete(args.id)
            else:
                with args.profile.open('rb') as source:
                    profile = tomllib.load(source)
                entries = book.entries()
                try:
                    text, warnings = cle332_report(entries, profile)
                except ReceiverMismatch as exc:
                    import sys
                    print(f'WARNING: {exc}', file=sys.stderr)
                    print('Generate a review draft with these receiver identities? [y/N] ', end='', file=sys.stderr, flush=True)
                    if sys.stdin.readline().strip().lower() not in {'y', 'yes'}:
                        raise ValueError('report cancelled: receiver mismatch not confirmed')
                    text, warnings = cle332_report(entries, profile, allow_receiver_mismatch=True)
                if args.output:
                    with args.output.open('x', encoding='utf-8') as destination:
                        destination.write(text)
                else:
                    print(text, end='')
                import sys
                for warning in warnings:
                    print(('WARNING: ' if warning.startswith('Receiver mismatch:') else 'Excluded: ') + warning, file=sys.stderr)
                print('Draft only; review and submit manually by 2026-09-30 08:00 UTC.', file=sys.stderr)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
