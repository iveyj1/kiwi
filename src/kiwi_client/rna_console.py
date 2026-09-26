"""Catalogue browsing state, independent of curses and receiver transport."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import tomllib

from kiwi_client.ndb_logbook import cle332_eligible
from kiwi_client.rna_catalogue import Catalogue, CatalogueFilter, ReceiverSite, load_catalogue, select_stations
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
                 sites: dict[str, ReceiverSite] | None = None, cle332_only: bool = False):
        self.cle332_only = cle332_only
        self.catalogue = catalogue
        self.filters = filters
        self.sites = dict(sites or {})
        self.receiver = None
        self.matches = ()
        self.index = 0
        self.component_index = 0
        self.error = ''

    def set_receiver(self, receiver: str, frequency_khz: float) -> None:
        if receiver != self.receiver:
            self.receiver = receiver
            self.refresh(frequency_khz)

    def refresh(self, frequency_khz: float) -> None:
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
        self.component_index = 0
        if self.matches:
            self.index = min(range(len(self.matches)), key=lambda i: (
                self.matches[i].station.key != old_key,
                abs(self.matches[i].station.carrier_khz - frequency_khz), i))

    @property
    def selected(self):
        return self.matches[self.index] if self.matches else None

    @property
    def component(self):
        return self.selected.station.components[self.component_index] if self.selected is not None else None

    def move(self, direction: int) -> None:
        if self.matches:
            self.index = (self.index + direction) % len(self.matches)
            self.component_index = 0

    def cycle_component(self) -> None:
        if self.selected is not None:
            self.component_index = (self.component_index + 1) % len(self.selected.station.components)

    def cycle_activity(self, frequency_khz: float) -> None:
        choices = ('active-unknown', 'active', 'all')
        self.filters = replace(self.filters, activity=choices[(choices.index(self.filters.activity) + 1) % len(choices)])
        self.refresh(frequency_khz)

    def annotations(self, start_khz: float, end_khz: float) -> tuple[FrequencyAnnotation, ...]:
        result = []
        for match in self.matches:
            for component in match.station.components:
                if start_khz <= component.frequency_khz <= end_khz:
                    suffix = {'carrier': 'C', 'lsb': 'L', 'usb': 'U'}[component.kind]
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
                f'{distance} {station.activity} | {self.component.kind.upper()} {self.component.frequency_khz:.3f}')

    def details(self) -> str:
        if self.selected is None:
            return f'RNA activity={self.filters.activity}; catalogue warnings={len(self.catalogue.warnings)}'
        station = self.selected.station
        offsets = f'LSB={station.lsb_hz if station.lsb_hz is not None else "?"} USB={station.usb_hz if station.usb_hz is not None else "?"} Hz'
        return (f'{offsets} | period={station.period_s if station.period_s is not None else "?"}s '
                f'{station.raw_fields.get("Fmt", "")} | last={station.raw_fields.get("Last Logged", "?")} '
                f'| filter={self.filters.activity} | catalogue, NOT a heard ID')


def add_rna_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument('--rna', type=Path, help='local RNA CSV; enable station markers and browsing')
    parser.add_argument('--rna-cle332', action='store_true', help='show only identified NDB catalogue rows on even nominal channels 190..530 kHz')
    parser.add_argument('--rna-sites', type=Path, help='TOML receiving sites keyed by host:port')
    parser.add_argument('--rna-activity', choices=['active', 'active-unknown', 'all'], default='active-unknown')
    parser.add_argument('--rna-distance-km', type=float, help='maximum distance; requires matching receiver site')
    parser.add_argument('--rna-exclude-unknown-distance', action='store_true')
    parser.add_argument('--rna-min-khz', type=float)
    parser.add_argument('--rna-max-khz', type=float)
    parser.add_argument('--rna-search', default='')
    parser.add_argument('--rna-sort', choices=['frequency', 'distance'], default='frequency')


def browser_from_args(args) -> RnaBrowser | None:
    if args.rna is None:
        return None
    return RnaBrowser(load_catalogue(args.rna), sites=load_sites(args.rna_sites), cle332_only=args.rna_cle332, filters=CatalogueFilter(
        args.rna_activity, args.rna_min_khz, args.rna_max_khz, args.rna_distance_km,
        not args.rna_exclude_unknown_distance, args.rna_search, args.rna_sort))
