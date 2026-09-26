"""Read-only scoped reception history and small, testable console panels."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from kiwi_client.ndb_logbook import utc_time, validate_reception


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


def logging_panel_rows(draft: dict, *, prompt: str, message: str, history: str) -> list[str]:
    editing = draft.get('log_id')
    title = f"EDIT LOG #{editing}" if editing is not None else 'NEW RECEPTION'
    center = draft.get('rf_center_khz')
    if center is None:
        center = draft['tuned_khz'] + ((draft.get('cw_offset_hz', 0) if draft['mode'] == 'cw' else 0)
                                      + (draft['low_cut_hz'] + draft['high_cut_hz']) / 2) / 1000
    width = draft['high_cut_hz'] - draft['low_cut_hz']
    return [f"{title} | {draft['ident']} | nominal {draft['carrier_khz']:g} kHz | {draft['status'].upper()}",
            prompt, f'Message: {message}',
            f"HEARD {utc_time(draft['heard_utc']):%Y-%m-%d %H:%M:%SZ} | {history}",
            f"SOURCE {draft['source_kind']} | {draft['receiver']} | {draft.get('event') or 'general'}",
            f"SNAPSHOT center {center:.6f} kHz | offset {(center - draft['carrier_khz']) * 1000:+.1f} Hz | BW {width:g} Hz",
            'Editing changes time/status/notes only; receiver and tuning evidence stay unchanged.']
