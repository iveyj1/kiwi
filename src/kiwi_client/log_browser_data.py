"""Read-only logbook sources and projections, independent of Qt and radio code.

RecordRef addresses the original record, not its sorted table position. Future edit
commands can compare its revision fingerprint before applying an audited revision.
Historical staging is never treated as newly confirmed live reception evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
from html import unescape
import json
import math
from pathlib import Path
import sqlite3
from typing import Protocol


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def utc_timestamp(value: str) -> str:
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('reception time lacks timezone')
    return stamp.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def station_identity(ident: str, frequency: float, country: str, region: str) -> str:
    # Conservative cross-source grouping; unknown country/region are not wildcards.
    region = region.strip().upper()
    return json.dumps([ident.strip().upper(), frequency, country.strip().upper(), '' if region == 'XX' else region])


@dataclass(frozen=True)
class RecordRef:
    source_kind: str
    path: str
    key: str
    revision: str


@dataclass(frozen=True)
class BrowserRecord:
    id: str
    reference: RecordRef
    heard_utc: str
    ident: str
    frequency_khz: float
    country: str
    region: str
    location: str
    distance_km: float | None
    receiver: str
    status: str
    notes: str
    source: str
    event: str = ''
    precision: str = 'second'
    flags: tuple[str, ...] = ()
    # Immutable serialization preserves all source fields, including unknown ones.
    evidence_json: str = '{}'
    frequency_basis: str = 'nominal'
    row_kind: str = 'reception'

    def __post_init__(self):
        for name in ('id', 'heard_utc', 'ident', 'country', 'region', 'location', 'receiver',
                     'status', 'notes', 'source', 'event', 'precision', 'evidence_json'):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f'invalid text field {name}')
        if not all(isinstance(flag, str) for flag in self.flags):
            raise ValueError('invalid review flags')
        if not isinstance(json.loads(self.evidence_json), dict):
            raise ValueError('source evidence must be an object')
        if self.frequency_basis not in ('nominal', 'label') or self.row_kind not in ('reception', 'label'):
            raise ValueError('invalid frequency basis or row kind')
        if self.precision == 'unknown':
            if self.heard_utc or self.row_kind != 'label':
                raise ValueError('unknown time must be an undated label, not a reception')
        elif self.precision == 'day':
            if date.fromisoformat(self.heard_utc).isoformat() != self.heard_utc:
                raise ValueError('invalid date-only evidence')
        elif self.precision in ('minute', 'second'):
            utc_timestamp(self.heard_utc)
        else:
            raise ValueError('unsupported time precision')
        if not math.isfinite(self.frequency_khz) or self.frequency_khz < 0:
            raise ValueError('invalid frequency')
        if self.distance_km is not None and (not isinstance(self.distance_km, (int, float))
                or not math.isfinite(self.distance_km) or self.distance_km < 0):
            raise ValueError('invalid distance')

    @property
    def station_key(self) -> str:
        if self.ident in ('', '?') or not self.frequency_khz:
            return 'unresolved:' + self.id
        if self.frequency_basis == 'label':
            # No inferred carrier/channel or fuzzy cross-source station association.
            return 'label:' + station_identity(f'{self.ident} {self.location}'.strip(),
                                               self.frequency_khz, self.country, self.region)
        return station_identity(self.ident, self.frequency_khz, self.country, self.region)

    def details(self) -> str:
        fields = asdict(self)
        fields.pop('evidence_json')
        fields['evidence'] = json.loads(self.evidence_json)
        return json.dumps(fields, ensure_ascii=False, indent=2, default=str)


class LogSource(Protocol):
    path: Path
    def load(self) -> list[BrowserRecord]: ...


@dataclass
class NativeLogSource:
    path: Path

    def load(self) -> list[BrowserRecord]:
        path = self.path.expanduser().resolve()
        # mode=ro observes committed WAL data; do not use immutable=1 on a live log.
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
        try:
            connection.execute('PRAGMA query_only=ON')
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version != 1:
                raise ValueError(f'unsupported native log schema {version}')
            rows = connection.execute('SELECT id, payload FROM receptions ORDER BY id').fetchall()
        finally:
            connection.close()
        records = []
        for key, payload in rows:
            try:
                entry = json.loads(payload)
                fields = entry.get('catalogue_fields', {})
                records.append(BrowserRecord(
                    id=f'native:{path}:{key}',
                    reference=RecordRef('native-sqlite', str(path), str(key), fingerprint(payload)),
                    heard_utc=utc_timestamp(entry['heard_utc']), ident=entry['ident'],
                    frequency_khz=float(entry['carrier_khz']), country=fields.get('ITU', ''),
                    region=fields.get('SP', ''), location=unescape(fields.get("'Name' and Location", '')),
                    distance_km=entry.get('distance_km'), receiver=entry['receiver'],
                    status=entry['status'], notes=entry.get('notes', ''), event=entry.get('event') or '',
                    source='Native ' + entry['source_kind'], evidence_json=payload))
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f'native record #{key}: {exc}') from exc
        return records


@dataclass
class StagedLogSource:
    path: Path

    def load(self) -> list[BrowserRecord]:
        data = json.loads(self.path.expanduser().read_text(encoding='utf-8'))
        kinds = {'wwsu-review-stage': ('wwsu-access', 'wwsu-report'),
                 'kiwi-label-review-stage': ('kiwi-label-json',)}
        if data.get('schema') != 1 or data.get('kind') not in kinds:
            raise ValueError('not a supported history review stage')
        is_labels = data['kind'] == 'kiwi-label-review-stage'
        records = []
        for row in data['records']:
            fields = dict(row)
            fields['reference'] = RecordRef(**fields['reference'])
            fields['flags'] = tuple(fields.get('flags', ()))
            if not is_labels or fields.get('precision', 'second') in ('minute', 'second'):
                fields['heard_utc'] = utc_timestamp(fields['heard_utc'])
            record = BrowserRecord(**fields)
            if record.reference.source_kind not in kinds[data['kind']]:
                raise ValueError('staged history cannot address a writable native source')
            statuses = ('historical', 'review', 'reference') if is_labels else ('historical', 'review')
            if record.event or record.status not in statuses:
                raise ValueError('staged history must not claim live confirmation/event membership')
            if is_labels:
                if record.frequency_basis != 'label':
                    raise ValueError('label frequency must not be promoted to a nominal channel')
                if (record.row_kind == 'label' and (record.heard_utc or record.status == 'historical')
                        or record.row_kind == 'reception' and record.status == 'reference'):
                    raise ValueError('label/reception classification contradicts date evidence')
            records.append(record)
        if len({r.id for r in records}) != len(records):
            raise ValueError('duplicate staged record IDs')
        return records


class LogWorkspace:
    """Source boundary for a browser and, later, audited edit commands.

No mutation API exists in this milestone. Qt owns no database connection and cannot
write through a cell. Reload failures retain the previous source snapshot visibly.
"""
    def __init__(self, sources: list[LogSource]):
        self.sources = sources
        self._cache: dict[tuple[type, str], list[BrowserRecord]] = {}
        self.records: tuple[BrowserRecord, ...] = ()
        self.errors: tuple[str, ...] = ()

    @staticmethod
    def source_key(source: LogSource) -> tuple[type, str]:
        return type(source), str(source.path.expanduser().resolve())

    def reload(self) -> None:
        errors = []
        for source in self.sources:
            try:
                self._cache[self.source_key(source)] = source.load()
            except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
                errors.append(f'{source.path}: {exc}; previous snapshot retained if available')
        records = [record for source in self.sources for record in self._cache.get(self.source_key(source), ())]
        if len({record.id for record in records}) != len(records):
            errors.append('Repeated source/record IDs: duplicate source arguments were ignored')
            records = list({record.id: record for record in records}.values())
        self.records = tuple(records)
        self.errors = tuple(errors)


@dataclass(frozen=True)
class BrowserFilter:
    search: str = ''
    source: str = ''
    status: str = ''
    event: str = ''
    date_from: str = ''
    date_to: str = ''
    minimum_khz: float | None = None
    maximum_khz: float | None = None
    station_key: str = ''
    review_only: bool = False

    def __post_init__(self):
        for name in ('search', 'source', 'status', 'event', 'date_from', 'date_to', 'station_key'):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f'invalid filter field {name}')
        for value in (self.minimum_khz, self.maximum_khz):
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError('invalid frequency filter')
        if not isinstance(self.review_only, bool):
            raise ValueError('invalid review filter')

    def matches(self, record: BrowserRecord) -> bool:
        if self.station_key and record.station_key != self.station_key:
            return False
        if self.source and record.source != self.source or self.status and record.status != self.status:
            return False
        if self.event and record.event != self.event:
            return False
        day = record.heard_utc[:10]
        if not day and (self.date_from or self.date_to):
            return False
        if self.date_from and day < self.date_from or self.date_to and day > self.date_to:
            return False
        if self.minimum_khz is not None and record.frequency_khz < self.minimum_khz:
            return False
        if self.maximum_khz is not None and record.frequency_khz > self.maximum_khz:
            return False
        if self.review_only and not record.flags and record.status != 'review':
            return False
        text = ' '.join((record.ident, record.location, record.country, record.region, record.receiver,
                         record.notes, record.source, record.event, *record.flags)).casefold()
        return all(record.ident.strip().casefold() == term[3:] if term.startswith('id:') else term in text
                   for term in self.search.casefold().split())
