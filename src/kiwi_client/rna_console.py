"""Catalogue browsing state, independent of curses and receiver transport."""
from __future__ import annotations

import argparse
import math
import shlex
from dataclasses import replace
from pathlib import Path
import tomllib

from kiwi_client.ndb_logbook import cle332_eligible
from kiwi_client.rna_catalogue import Catalogue, CatalogueFilter, Component, ReceiverSite, load_catalogue, select_stations
from kiwi_client.station_memory import StationMemory, passband_center_khz
from kiwi_client.waterfall_scale import FrequencyAnnotation


def load_sites(path: Path | None) -> dict[str, ReceiverSite]:
    if path is None:
        return {}
    with path.open('rb') as source:
        data = tomllib.load(source)
    sites = {}
    for receiver, item in data.get('sites', {}).items():
        try:
            sites[receiver] = ReceiverSite(item.get('name', receiver), float(item['latitude']),
                                           float(item['longitude']), item['timezone'])
        except (KeyError, TypeError) as exc:
            raise ValueError(f'incomplete site for {receiver}: latitude, longitude, timezone required') from exc
    return sites


class RnaBrowser:
    def __init__(self, catalogue: Catalogue, *, filters: CatalogueFilter = CatalogueFilter(),
                 sites: dict[str, ReceiverSite] | None = None, cle332_only: bool = False,
                 memory: StationMemory | None = None, near_radius_hz: float = 200):
        if not math.isfinite(near_radius_hz) or near_radius_hz < 0:
            raise ValueError('nearby radius must be finite and nonnegative Hz')
        self.near_radius_hz = near_radius_hz
        self._near_anchor = None
        self._near_expected = None
        self._near_pool = ()
        self.memory = memory if memory is not None else StationMemory()
        self.cle332_only = cle332_only
        self.catalogue = catalogue
        self.filters = filters
        self.sites = dict(sites or {})
        self.receiver = None
        self.matches = ()
        self.index = 0
        self.error = ''

    def set_receiver(self, receiver: str, frequency_khz: float) -> None:
        if receiver != self.receiver:
            self.receiver = receiver
            self.refresh(frequency_khz)

    def refresh(self, frequency_khz: float) -> None:
        self._near_anchor = self._near_expected = None
        old_key = self.selected.station.key if self.selected is not None else None
        try:
            self.matches = select_stations(self.catalogue, site=self.sites.get(self.receiver), filters=self.filters)
            if self.cle332_only:
                self.matches = tuple(match for match in self.matches
                                     if cle332_eligible(match.station.carrier_khz, match.station.ident))
            self.error = ''
        except ValueError as exc:
            # Never apply the old receiver's distance filter at a new/unknown site.
            self.matches = ()
            self.error = str(exc)
        self.index = 0
        if self.matches:
            self.index = min(range(len(self.matches)), key=lambda i: (
                self.matches[i].station.key != old_key,
                abs(self.matches[i].station.carrier_khz - frequency_khz), i))

    @property
    def selected(self):
        return self.matches[self.index] if self.matches else None

    @property
    def components(self):
        if self.selected is None:
            return ()
        station = self.selected.station
        components = station.components
        stored = self.memory.records.get(station.key, {}).get('stored')
        if stored is not None:
            components += (Component('stored', station.carrier_khz + stored['offset_hz'] / 1000),)
        return components

    @property
    def component(self):
        if self.selected is None:
            return None
        default = 'usb' if self.selected.station.usb_hz is not None else 'carrier'
        choice = self.memory.records.get(self.selected.station.key, {}).get('choice', default)
        return next((c for c in self.components if c.kind == choice), self.components[0])

    def store_tuning(self, state) -> str:
        if self.selected is None or state.mode != 'cw':
            raise ValueError('select a station and use CW before storing tuning')
        station = self.selected.station
        self.memory.update(station.key, dict(choice='stored', stored=dict(
            carrier_khz=station.carrier_khz, offset_hz=(passband_center_khz(state) - station.carrier_khz) * 1000,
            bandwidth_hz=state.high_cut_hz - state.low_cut_hz)))
        self._near_anchor = self._near_expected = None
        return f'Stored {station.ident}: center {self.component.frequency_khz:.6f} kHz, BW {state.high_cut_hz - state.low_cut_hz:g} Hz'

    def forget_tuning(self) -> str:
        if self.selected is None:
            raise ValueError('no station selected')
        station = self.selected.station
        self.memory.update(station.key, dict(choice='usb' if station.usb_hz is not None else 'carrier'))
        self._near_anchor = self._near_expected = None
        return f'Forgot personal tuning for {station.ident}'

    def move(self, direction: int) -> None:
        if self.matches:
            self.index = (self.index + direction) % len(self.matches)

    def cycle_component(self) -> None:
        if self.selected is not None:
            components = self.components
            component = components[(components.index(self.component) + 1) % len(components)]
            record = dict(self.memory.records.get(self.selected.station.key, {}), choice=component.kind)
            self.memory.update(self.selected.station.key, record)

    def cycle_activity(self, frequency_khz: float) -> None:
        choices = ('active-unknown', 'active', 'all')
        self.filters = replace(self.filters, activity=choices[(choices.index(self.filters.activity) + 1) % len(choices)])
        self.refresh(frequency_khz)

    def nearby_components(self, center_khz: float):
        """One closest known component per shortlisted station, in RF-distance order."""
        hits = []
        for match in self.matches:
            components = match.station.components
            stored = self.memory.records.get(match.station.key, {}).get('stored')
            if stored is not None:
                components += (Component('stored', match.station.carrier_khz + stored['offset_hz'] / 1000),)
            component = min(components, key=lambda c: abs(c.frequency_khz - center_khz))
            if abs(component.frequency_khz - center_khz) * 1000 <= self.near_radius_hz + 1e-6:
                hits.append((match, component))
        return tuple(sorted(hits, key=lambda hit: (abs(hit[1].frequency_khz - center_khz),
                                                   hit[0].station.carrier_khz, hit[0].station.ident, hit[0].station.key)))

    def cycle_nearby(self, center_khz: float, direction: int) -> str:
        if direction not in (-1, 1) or not math.isfinite(center_khz):
            raise ValueError('invalid nearby direction/center')
        if self._near_anchor is None or self._near_expected is None or not math.isclose(
                center_khz, self._near_expected, abs_tol=1e-6, rel_tol=0):
            self._near_anchor = center_khz
            self._near_pool = self.nearby_components(center_khz)
        if not self._near_pool:
            raise ValueError(f'no nearby stations within ±{self.near_radius_hz:g} Hz; current RNA filters apply')
        current_key = self.selected.station.key if self.selected is not None else None
        current = next((i for i, hit in enumerate(self._near_pool) if hit[0].station.key == current_key), None)
        index = (0 if direction > 0 else len(self._near_pool) - 1) if current is None else (current + direction) % len(self._near_pool)
        match, component = self._near_pool[index]
        self.memory.update(match.station.key, dict(self.memory.records.get(match.station.key, {}), choice=component.kind))
        self.index = next(i for i, row in enumerate(self.matches) if row.station.key == match.station.key)
        return (f'NEAR {index + 1}/{len(self._near_pool)} anchor {self._near_anchor:.6f} kHz ±{self.near_radius_hz:g} Hz; '
                f'{match.station.ident} {component.kind} {component.frequency_khz:.6f}; RNA filters apply')

    def nearby_tuned(self, center_khz: float) -> None:
        self._near_expected = center_khz

    def filter_summary(self) -> str:
        f = self.filters
        return (f'CLE332={"on" if self.cle332_only else "off"} activity={f.activity} '
                f'range<={f.max_distance_km if f.max_distance_km is not None else "off"}km '
                f'power>={f.min_power_w if f.min_power_w is not None else "off"}W sort={f.sort}')

    def command(self, text: str, frequency_khz: float) -> str:
        parts = shlex.split(text)
        if parts == ['rna']:
            return self.filter_summary()
        if len(parts) == 3 and parts[:2] == ['rna', 'near']:
            radius = float(parts[2])
            if not math.isfinite(radius) or radius < 0:
                raise ValueError('nearby radius must be finite and nonnegative Hz')
            self.near_radius_hz = radius
            self._near_anchor = self._near_expected = None
            return f'Nearby radius ±{radius:g} Hz; , previous / . next; current RNA filters apply'
        filters, sites, cle = self.filters, dict(self.sites), self.cle332_only
        if len(parts) == 3 and parts[0] == 'rna':
            name, value = parts[1:]
            if name == 'range':
                filters = replace(filters, max_distance_km=None if value == 'off' else float(value),
                                  include_unknown_distance=value == 'off')
            elif name == 'power':
                filters = replace(filters, min_power_w=None if value == 'off' else float(value))
            elif name == 'sort':
                filters = replace(filters, sort=value)
            elif name == 'activity':
                filters = replace(filters, activity=value)
            elif name == 'search':
                filters = replace(filters, search='' if value == 'off' else value)
            elif name == 'cle' and value in {'on', 'off'}:
                cle = value == 'on'
            else:
                raise ValueError('rna range KM|off; power W|off; sort distance|frequency; cle on|off; activity active|active-unknown|all; search TEXT|off')
        elif len(parts) == 5 and parts[:2] == ['rna', 'site']:
            sites[self.receiver] = ReceiverSite(self.receiver, float(parts[2]), float(parts[3]), parts[4])
        else:
            raise ValueError('usage: rna range|power|sort|cle|activity|search VALUE; rna site LAT LON TIMEZONE')
        # Validate before changing anything, including when a receiver site is missing.
        if sites.get(self.receiver) is None and (filters.max_distance_km is not None or filters.sort == 'distance'):
            raise ValueError('requires a receiver site; use :rna site LAT LON TIMEZONE or --rna-sites FILE')
        select_stations(self.catalogue, site=sites.get(self.receiver), filters=filters)
        self.filters, self.sites, self.cle332_only = filters, sites, cle
        self.refresh(frequency_khz)
        return self.filter_summary() + f' | {len(self.matches)} stations'

    def search_callsigns(self, term: str):
        all_rows = select_stations(self.catalogue, site=self.sites.get(self.receiver),
                                   filters=CatalogueFilter(activity='all', sort=self.filters.sort
                                                           if self.sites.get(self.receiver) else 'frequency'))
        term = term.strip().casefold()
        hits = [row for row in all_rows if term in row.station.ident.casefold()]
        return tuple(sorted(hits, key=lambda row: row.station.ident.casefold() != term))

    def exclusion_reason(self, match) -> str:
        station, f = match.station, self.filters
        reasons = []
        if self.cle332_only and not cle332_eligible(station.carrier_khz, station.ident):
            reasons.append('CLE332 nominal channel/ID')
        if f.activity != 'all' and (station.activity == 'inactive' or f.activity == 'active' and station.activity != 'active'):
            reasons.append('activity')
        if (f.min_khz is not None and station.carrier_khz < f.min_khz or
                f.max_khz is not None and station.carrier_khz > f.max_khz):
            reasons.append('nominal range')
        if f.min_power_w is not None and (station.power_w is None or station.power_w < f.min_power_w):
            reasons.append('power unknown/below minimum')
        if match.distance_km is None and (not f.include_unknown_distance or f.max_distance_km is not None and self.receiver not in self.sites):
            reasons.append('distance/site unknown')
        elif f.max_distance_km is not None and match.distance_km is not None and match.distance_km > f.max_distance_km:
            reasons.append('distance exceeds maximum')
        if f.search and f.search.casefold() not in ' '.join([station.ident, station.location,
                station.raw_fields.get('SP', ''), station.raw_fields.get('ITU', '')]).casefold():
            reasons.append('text filter')
        if self.error:
            reasons.append(self.error)
        return '; '.join(reasons)

    def select_hit(self, match) -> None:
        reason = self.exclusion_reason(match)
        if reason:
            raise ValueError('Hidden: ' + reason + '; change :rna filters first')
        for index, row in enumerate(self.matches):
            if row.station.key == match.station.key:
                self.index = index
                return
        raise ValueError('station is not in the current shortlist')

    def annotations(self, start_khz: float, end_khz: float) -> tuple[FrequencyAnnotation, ...]:
        result = []
        for match in self.matches:
            components = match.station.components
            stored = self.memory.records.get(match.station.key, {}).get('stored')
            if stored is not None:
                components += (Component('stored', match.station.carrier_khz + stored['offset_hz'] / 1000),)
            for component in components:
                if start_khz <= component.frequency_khz <= end_khz:
                    suffix = {'carrier': 'C', 'lsb': 'L', 'usb': 'U', 'stored': 'S'}[component.kind]
                    result.append(FrequencyAnnotation(component.frequency_khz, f'{match.station.ident}:{suffix}',
                                                      component.kind, match == self.selected and component == self.component))
        return tuple(result)

    def status(self) -> str:
        if not self.matches:
            return 'RNA: ' + (self.error or 'no matching stations')
        match = self.selected
        station = match.station
        distance = '?' if match.distance_km is None else f'{match.distance_km:.0f}km'
        return (f'RNA {self.index + 1}/{len(self.matches)} {station.ident} {station.carrier_khz:g} '
                f'{station.location} {station.raw_fields.get("SP", "")} {station.raw_fields.get("ITU", "")} '
                f'{distance} {station.power_w if station.power_w is not None else "?"}W {station.activity} | {self.component.kind.upper()} {self.component.frequency_khz:.3f}')

    def details(self) -> str:
        if self.selected is None:
            return f'RNA activity={self.filters.activity}; catalogue warnings={len(self.catalogue.warnings)}'
        station = self.selected.station
        offsets = f'LSB={station.lsb_hz if station.lsb_hz is not None else "?"} USB={station.usb_hz if station.usb_hz is not None else "?"} Hz'
        return (f'{offsets} | period={station.period_s if station.period_s is not None else "?"}s '
                f'{station.raw_fields.get("Fmt", "")} | last={station.raw_fields.get("Last Logged", "?")} '
                f'| filter={self.filters.activity} | catalogue, NOT a heard ID')


class CallsignSearchPage:
    """All-catalogue ID hits; highlighting/selection never tunes or logs."""
    def __init__(self, browser: RnaBrowser, term: str, log_status=None):
        self.log_status = log_status
        self.browser, self.term = browser, term
        self.hits = browser.search_callsigns(term)
        self.index = 0

    def move(self, amount: int) -> None:
        self.index = max(0, min(max(0, len(self.hits) - 1), self.index + amount))

    def select(self) -> None:
        if not self.hits:
            raise ValueError('no callsign matches')
        self.browser.select_hit(self.hits[self.index])

    def rows(self, height: int) -> list[str]:
        capacity = max(1, height - 5)
        start = self.index // capacity * capacity
        rows = [f'CALLSIGN /{self.term} — {len(self.hits)} hits (all catalogue records)',
                self.browser.filter_summary(),
                '   ID       kHz       km       W  Log / visibility / location']
        for index in range(start, min(len(self.hits), start + capacity)):
            hit = self.hits[index]
            s = hit.station
            distance = '?' if hit.distance_km is None else f'{hit.distance_km:.0f}'
            power = '?' if s.power_w is None else f'{s.power_w:g}'
            reason = self.browser.exclusion_reason(hit)
            history = '' if self.log_status is None else self.log_status(s.key) + ' | '
            rows.append(f'{">" if index == self.index else " "} {s.ident:8} {s.carrier_khz:8g} {distance:>8} {power:>7} '
                        f'{history}{"HIDDEN: " + reason if reason else "visible"} | {s.location} {s.raw_fields.get("ITU", "")}')
        rows.append('↑/↓ j/k browse PgUp/PgDn page Enter select+tune / search : filters Esc close')
        return rows


def add_rna_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--rna-near-hz', type=float, default=200, help='nearby component cycling radius in Hz (default 200)')
    parser.add_argument('--rna-memory', type=Path, default=Path('rna-stations.json'), help='personal component choices and stored center/bandwidth, separate from RNA')
    parser.add_argument('--rna', type=Path, help='local RNA CSV; enable station markers and browsing')
    parser.add_argument('--rna-cle332', action='store_true', help='show only identified NDB catalogue rows on even nominal channels 190..530 kHz')
    parser.add_argument('--rna-sites', type=Path, help='TOML receiving sites keyed by host:port')
    parser.add_argument('--rna-activity', choices=['active', 'active-unknown', 'all'], default='active-unknown')
    parser.add_argument('--rna-min-power-w', type=float, help='minimum catalogue power in watts; unknown power excluded')
    parser.add_argument('--rna-distance-km', type=float, help='maximum distance; requires matching receiver site')
    parser.add_argument('--rna-exclude-unknown-distance', action='store_true')
    parser.add_argument('--rna-min-khz', type=float)
    parser.add_argument('--rna-max-khz', type=float)
    parser.add_argument('--rna-search', default='')
    parser.add_argument('--rna-sort', choices=['frequency', 'distance'], default='frequency')


def browser_from_args(args) -> RnaBrowser | None:
    if args.rna is None:
        return None
    return RnaBrowser(load_catalogue(args.rna), near_radius_hz=args.rna_near_hz, memory=StationMemory(args.rna_memory), sites=load_sites(args.rna_sites), cle332_only=args.rna_cle332, filters=CatalogueFilter(
        args.rna_activity, args.rna_min_khz, args.rna_max_khz, args.rna_distance_km,
        not args.rna_exclude_unknown_distance, args.rna_search, args.rna_sort, args.rna_min_power_w))
