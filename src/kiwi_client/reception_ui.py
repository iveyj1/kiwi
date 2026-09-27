"""Read-only scoped reception history and small, testable console panels."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from kiwi_client.ndb_logbook import utc_time, validate_reception
from kiwi_client.console_panels import log_panel_rows


def scope_key(station_key, receiver, event, source_kind):
    return station_key, receiver, event, source_kind


class ReceptionIndex:
    def __init__(self, path: Path | None):
        self.path = path
        self.error = ''
        self.groups = {}

    def refresh(self) -> None:
        self.error = ''
        self.groups = {}
        if self.path is None or not self.path.exists():
            return
        try:
            # A read must not create a file, change schema, or write SQLite pragmas.
            connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=0.05)
            try:
                if connection.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise ValueError('unsupported logbook version')
                groups = {}
                for log_id, payload in connection.execute('SELECT id, payload FROM receptions'):
                    record = json.loads(payload)
                    validate_reception(record)
                    record['log_id'] = log_id
                    key = scope_key(record['station_key'], record['receiver'], record.get('event'), record['source_kind'])
                    groups.setdefault(key, []).append(record)
                for records in groups.values():
                    records.sort(key=lambda r: (utc_time(r['heard_utc']), r['log_id']), reverse=True)
                self.groups = groups
            finally:
                connection.close()
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            self.error = f'log unavailable: {exc}'

    def matching(self, station_key, receiver, event, source_kind):
        return self.groups.get(scope_key(station_key, receiver, event, source_kind), ())

    def latest(self, station_key, receiver, event, source_kind):
        if self.error:
            raise ValueError(self.error)
        matches = self.matching(station_key, receiver, event, source_kind)
        return dict(matches[0]) if matches else None

    def status(self, station_key, receiver, event, source_kind) -> str:
        if self.path is None:
            return 'LOG disabled'
        if self.error:
            return self.error
        matches = self.matching(station_key, receiver, event, source_kind)
        if not matches:
            return 'NOT LOGGED (this receiver/event/source)'
        latest = matches[0]
        confirmed = next((r for r in matches if r['status'] == 'confirmed'), None)
        def stamp(record):
            return utc_time(record['heard_utc']).strftime('%Y-%m-%d %H:%M:%SZ')
        text = f"{latest['status'].upper()} {stamp(latest)} #{latest['log_id']} ({len(matches)} entries)"
        if confirmed is not None and latest['status'] != 'confirmed':
            text += f" | last CONFIRMED {stamp(confirmed)}"
        return text


def reception_panel_lines(index: ReceptionIndex, station_key, receiver, event, source_kind) -> list[str]:
    records = index.matching(station_key, receiver, event, source_kind)
    if not records or index.error:
        return [index.status(station_key, receiver, event, source_kind), f'{event or "general"} / {source_kind}', receiver]
    latest = records[0]
    lines = [f"{latest['status'].upper()} {utc_time(latest['heard_utc']):%Y-%m-%d %H:%M:%SZ}"]
    confirmed = next((r for r in records if r['status'] == 'confirmed'), None)
    if confirmed is not None and latest['status'] != 'confirmed':
        lines.append(f"CONFIRMED {utc_time(confirmed['heard_utc']):%Y-%m-%d %H:%M:%SZ}")
    lines.extend([f"#{latest['log_id']} / {len(records)} entries / {event or 'general'} / {source_kind}",
                  receiver, 'Note: ' + latest.get('notes', ''), 'w edit latest / W new reception'])
    return lines


def station_spreadsheet(browser, index: ReceptionIndex, receiver, event, source_kind, *, limit=6):
    """Small selected-centered shortlist window; Last is RNA, Logged is personal."""
    matches = browser.matches
    start = max(0, min(browser.index - limit // 2, len(matches) - limit))
    rows = []
    for match in matches[start:start + limit]:
        station = match.station
        records = index.matching(station.key, receiver, event, source_kind)
        if index.path is None:
            logged = 'OFF'
        elif index.error:
            logged = 'UNAVAILABLE'
        elif not records:
            logged = 'NO'
        else:
            latest = records[0]
            earlier_confirmed = latest['status'] != 'confirmed' and any(r['status'] == 'confirmed' for r in records)
            status = latest['status'].upper() + ('+' if earlier_confirmed else '')
            logged = f"{status} {utc_time(latest['heard_utc']):%Y-%m-%d %H:%M:%SZ}"
        rows.append((('> ' if match == browser.selected else '  ') + station.ident,
                     f'{station.carrier_khz:g}', logged,
                     ' '.join(filter(None, (station.location, station.raw_fields.get('SP', ''), station.raw_fields.get('ITU', '')))),
                     '?' if match.distance_km is None else f'{match.distance_km:.0f}',
                     '?' if station.period_s is None else f'{station.period_s:g}',
                     station.raw_fields.get('Last Logged', '') or '—'))
    return rows


def logging_panel_rows(draft: dict, *, prompt: str, message: str, history: str,
                       columns: int = 100, height: int = 24, entry: str | None = None) -> list[str]:
    editing = draft.get('log_id')
    title = f"EDIT LOG #{editing}" if editing is not None else 'NEW RECEPTION'
    center = draft.get('rf_center_khz')
    if center is None:
        center = draft['tuned_khz'] + ((draft.get('cw_offset_hz', 0) if draft['mode'] == 'cw' else 0)
                                      + (draft['low_cut_hz'] + draft['high_cut_hz']) / 2) / 1000
    width = draft['high_cut_hz'] - draft['low_cut_hz']
    timestamp, notes = draft['heard_utc'], draft.get('notes', '')
    if entry is not None:
        timestamp, _, notes = entry.partition('|')
    editable = [f'UTC    {timestamp.strip()}', f"Status {draft['status'].upper()}",
                'Notes  ' + notes.strip(), '', 'Edit UTC | notes in the input below.',
                'Enter reviews; y/t/n saves; d then D deletes.']
    evidence = [f"Station    {draft['ident']} / {draft['carrier_khz']:g} kHz",
                f"Receiver   {draft['receiver']}", f"Source     {draft['source_kind']} / {draft.get('event') or 'general'}",
                f'RF center  {center:.6f} kHz', f'Offset     {(center - draft["carrier_khz"]) * 1000:+.1f} Hz',
                f'Bandwidth  {width:g} Hz', 'Catalogue  snapshot retained']
    return log_panel_rows(columns=columns, height=height,
                          title=f"{title} / {draft['ident']} / {draft['carrier_khz']:g} kHz",
                          editable=editable, evidence=evidence, prompt=prompt,
                          message=message, history=history)
