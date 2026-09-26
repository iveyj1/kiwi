"""Local RNA catalogue and receiving-site filters; no DSP or network access."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Component:
    kind: str
    frequency_khz: float


@dataclass(frozen=True)
class Station:
    key: str
    ident: str
    carrier_khz: float
    activity: str
    lsb_hz: float | None
    usb_hz: float | None
    period_s: float | None
    latitude: float | None
    longitude: float | None
    raw_fields: Mapping[str, str]

    @property
    def location(self) -> str:
        return self.raw_fields.get("'Name' and Location", '')

    @property
    def power_w(self) -> float | None:
        try:
            value = float(self.raw_fields.get('Pwr', ''))
            return value if math.isfinite(value) and value >= 0 else None
        except ValueError:
            return None

    @property
    def components(self) -> tuple[Component, ...]:
        result = [Component('carrier', self.carrier_khz)]
        for kind, offset, sign in [('lsb', self.lsb_hz, -1), ('usb', self.usb_hz, 1)]:
            if offset is not None:
                result.append(Component(kind, self.carrier_khz + sign * offset / 1000))
        return tuple(result)


@dataclass(frozen=True)
class Catalogue:
    source: str
    sha256: str
    loaded_utc: str
    stations: tuple[Station, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ReceiverSite:
    name: str
    latitude: float
    longitude: float
    timezone: str = 'UTC'

    def __post_init__(self):
        _validate_coordinates(self.latitude, self.longitude)
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f'unknown receiver timezone: {self.timezone}') from exc


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError('latitude must be finite and within -90..90 degrees')
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError('longitude must be finite and within -180..180 degrees')


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on the mean-radius Earth (not a propagation model)."""
    _validate_coordinates(lat1, lon1)
    _validate_coordinates(lat2, lon2)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(max(0, min(1, a))))


def load_catalogue(path: str | Path) -> Catalogue:
    """Load NDB rows, reporting malformed values without inventing defaults.

    Bad carriers skip the row. Bad optional values become explicit unknowns.
    Source bytes are hashed before decoding; raw fields remain immutable.
    """
    path = Path(path)
    content = path.read_bytes()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''))
    headers = reader.fieldnames or []
    missing = {'KHz', 'ID', 'Type'} - set(headers)
    if missing:
        raise ValueError('catalogue requires columns: ' + ', '.join(sorted(missing)))
    if len(headers) != len(set(headers)):
        raise ValueError('catalogue has duplicate column names')
    stations = []
    warnings = []
    for row in reader:
        line = reader.line_num
        if None in row:
            warnings.append(f'line {line}: extra CSV fields; row skipped')
            continue
        raw = {key: value if value is not None else '' for key, value in row.items()}
        if raw['Type'].strip().upper() != 'NDB':
            continue

        def number(field, *, minimum=None, maximum=None):
            text = raw.get(field, '').strip()
            if not text:
                return None
            try:
                value = float(text)
                if (not math.isfinite(value) or
                        (minimum is not None and value < minimum) or
                        (maximum is not None and value > maximum)):
                    raise ValueError()
                return value
            except ValueError:
                warnings.append(f'line {line}: invalid {field}={text!r}; treated as unknown')
                return None

        carrier = number('KHz', minimum=0)
        if carrier is None or carrier <= 0:
            warnings.append(f'line {line}: missing/invalid carrier; row skipped')
            continue
        latitude = number('Lat', minimum=-90, maximum=90)
        longitude = number('Lon', minimum=-180, maximum=180)
        if latitude is None or longitude is None:
            latitude = longitude = None
        activity_text = raw.get('Active', '').strip().upper()
        activity = ('active' if activity_text in {'Y', 'YES', 'TRUE', '1', 'ACTIVE'} else
                    'inactive' if activity_text in {'N', 'NO', 'FALSE', '0', 'INACTIVE'} else 'unknown')
        # RNA exports lack a stable row ID. Mutable status/notes/log dates are not identity.
        identity = [carrier, raw['ID'].strip(), *[
            raw.get(field, '').strip() for field in ("'Name' and Location", 'SP', 'ITU', 'GSQ', 'Lat', 'Lon')]]
        key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
        lsb = number('LSB', minimum=0, maximum=carrier * 1000)
        usb = number('USB', minimum=0)
        period = number('Sec', minimum=0)
        if period == 0:
            warnings.append(f'line {line}: zero Sec; treated as unknown')
            period = None
        stations.append(Station(key, raw['ID'].strip(), carrier, activity, lsb, usb,
                                period, latitude, longitude, MappingProxyType(raw)))
    return Catalogue(str(path.resolve()), hashlib.sha256(content).hexdigest(),
                     datetime.now(timezone.utc).isoformat(), tuple(stations), tuple(warnings))


@dataclass(frozen=True)
class CatalogueFilter:
    activity: str = 'active-unknown'
    min_khz: float | None = None
    max_khz: float | None = None
    max_distance_km: float | None = None
    include_unknown_distance: bool = True
    search: str = ''
    sort: str = 'frequency'
    min_power_w: float | None = None

    def __post_init__(self):
        if self.activity not in {'active', 'active-unknown', 'all'}:
            raise ValueError('activity must be active, active-unknown or all')
        if self.sort not in {'frequency', 'distance'}:
            raise ValueError('sort must be frequency or distance')
        for value in (self.min_khz, self.max_khz, self.max_distance_km, self.min_power_w):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError('filter limits must be finite and nonnegative')
        if self.min_khz is not None and self.max_khz is not None and self.min_khz > self.max_khz:
            raise ValueError('minimum frequency exceeds maximum frequency')


@dataclass(frozen=True)
class StationMatch:
    station: Station
    distance_km: float | None


def select_stations(catalogue: Catalogue, *, site: ReceiverSite | None = None,
                    filters: CatalogueFilter = CatalogueFilter()) -> tuple[StationMatch, ...]:
    if site is None and (filters.max_distance_km is not None or filters.sort == 'distance'):
        raise ValueError('distance filtering/sorting requires a receiver site')
    matches = []
    for station in catalogue.stations:
        if filters.activity == 'active' and station.activity != 'active':
            continue
        if filters.activity == 'active-unknown' and station.activity == 'inactive':
            continue
        if filters.min_khz is not None and station.carrier_khz < filters.min_khz:
            continue
        if filters.max_khz is not None and station.carrier_khz > filters.max_khz:
            continue
        if filters.min_power_w is not None and (station.power_w is None or station.power_w < filters.min_power_w):
            continue
        searchable = ' '.join([station.ident, station.location, station.raw_fields.get('SP', ''), station.raw_fields.get('ITU', '')])
        if filters.search.casefold() not in searchable.casefold():
            continue
        distance = None
        if site is not None and station.latitude is not None and station.longitude is not None:
            distance = distance_km(site.latitude, site.longitude, station.latitude, station.longitude)
        if distance is None and not filters.include_unknown_distance:
            continue
        if filters.max_distance_km is not None and distance is not None and distance > filters.max_distance_km:
            continue
        matches.append(StationMatch(station, distance))
    def sort_key(match):
        base = (match.station.carrier_khz, match.station.ident, match.station.key)
        if filters.sort == 'distance':
            return (math.inf if match.distance_km is None else match.distance_km, *base)
        return base
    return tuple(sorted(matches, key=sort_key))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Inspect/filter a local RNA catalogue without connecting to a receiver')
    parser.add_argument('catalogue', type=Path)
    parser.add_argument('--activity', choices=['active', 'active-unknown', 'all'], default='active-unknown')
    parser.add_argument('--latitude', type=float)
    parser.add_argument('--longitude', type=float)
    parser.add_argument('--timezone', default='UTC')
    parser.add_argument('--max-distance-km', type=float)
    parser.add_argument('--min-power-w', type=float)
    parser.add_argument('--exclude-unknown-distance', action='store_true')
    parser.add_argument('--min-khz', type=float)
    parser.add_argument('--max-khz', type=float)
    parser.add_argument('--search', default='')
    parser.add_argument('--sort', choices=['frequency', 'distance'], default='frequency')
    args = parser.parse_args(argv)
    try:
        if (args.latitude is None) != (args.longitude is None):
            raise ValueError('provide both latitude and longitude')
        site = None if args.latitude is None else ReceiverSite('CLI receiver', args.latitude, args.longitude, args.timezone)
        catalogue = load_catalogue(args.catalogue)
        filters = CatalogueFilter(args.activity, args.min_khz, args.max_khz, args.max_distance_km,
                                  not args.exclude_unknown_distance, args.search, args.sort, args.min_power_w)
        matches = select_stations(catalogue, site=site, filters=filters)
        print(json.dumps(dict(source=catalogue.source, sha256=catalogue.sha256,
                              loaded_utc=catalogue.loaded_utc, network=False, warnings=catalogue.warnings,
                              stations=[dict(key=m.station.key, ident=m.station.ident,
                                             carrier_khz=m.station.carrier_khz, activity=m.station.activity,
                                             distance_km=m.distance_km, fields=dict(m.station.raw_fields),
                                             components=[dict(kind=c.kind, frequency_khz=c.frequency_khz)
                                                         for c in m.station.components]) for m in matches]), indent=2))
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
