"""Atomic personal RNA browsing preferences, separate from catalogue and memories."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import tempfile

from kiwi_client.rna_catalogue import CatalogueFilter, ReceiverSite


class RnaPreferences:
    def __init__(self, path: Path | None = None, *, reset=False):
        self.path = path
        self.filters = CatalogueFilter()
        self.cle332_only = False
        self.near_radius_hz = 200
        self.sites = {}
        if path is not None and path.exists() and not reset:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                self.filters, self.cle332_only, self.near_radius_hz, self.sites = self.decode(data)
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f'invalid RNA state {path}: {exc}; use --rna-reset-state or --no-rna-state') from exc

    @staticmethod
    def decode(data):
        if not isinstance(data, dict) or data.get('schema') != 1:
            raise ValueError('unsupported RNA state schema')
        filters = CatalogueFilter(**data['filters'])
        if not isinstance(filters.search, str) or type(filters.include_unknown_distance) is not bool:
            raise ValueError('invalid search or unknown-distance policy')
        for value in (filters.min_khz, filters.max_khz, filters.max_distance_km, filters.min_power_w):
            if isinstance(value, bool):
                raise ValueError('filter limits must be numbers, not booleans')
        cle, near = data['cle332_only'], data['near_radius_hz']
        if type(cle) is not bool or isinstance(near, bool) or not isinstance(near, (int, float)) or not math.isfinite(near) or near < 0:
            raise ValueError('invalid CLE/nearby preference')
        if not isinstance(data['sites'], dict):
            raise ValueError('sites must be an object')
        sites = {}
        for receiver, site in data['sites'].items():
            if not isinstance(site, dict) or any(isinstance(site.get(key), bool) for key in ('latitude', 'longitude')):
                raise ValueError('invalid receiving site')
            sites[receiver] = ReceiverSite(**site)
        return filters, cle, near, sites

    def save(self, filters, cle332_only, near_radius_hz, sites):
        if self.path is None:
            return
        data = dict(schema=1, filters=asdict(filters), cle332_only=cle332_only,
                    near_radius_hz=near_radius_hz, sites={key: asdict(site) for key, site in sites.items()})
        self.decode(data)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix=self.path.name + '.', delete=False) as output:
                name = output.name
                json.dump(data, output, allow_nan=False, indent=2)
                output.flush()
                os.fsync(output.fileno())
            os.replace(name, self.path)
        finally:
            if name is not None and os.path.exists(name):
                os.unlink(name)
