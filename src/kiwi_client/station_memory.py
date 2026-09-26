"""Personal station choices and tuning memories, never modifications to RNA."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile


def passband_center_khz(state) -> float:
    reference = state.frequency_khz + (state.cw_offset_hz / 1000 if state.mode == 'cw' else 0)
    return reference + (state.low_cut_hz + state.high_cut_hz) / 2000


class StationMemory:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.records = {}
        if path is not None and path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('stations'), dict):
                raise ValueError('invalid station-memory file')
            for key, record in data['stations'].items():
                self._validate(record)
            self.records = data['stations']

    @staticmethod
    def _validate(record):
        if not isinstance(record, dict) or record.get('choice') not in {'carrier', 'lsb', 'usb', 'stored'}:
            raise ValueError('invalid station-memory choice')
        if 'stored' in record:
            stored = record['stored']
            if not isinstance(stored, dict):
                raise ValueError('invalid stored tuning')
            for field in ('offset_hz', 'bandwidth_hz', 'carrier_khz'):
                value = stored.get(field)
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f'invalid stored {field}')
            if not float(stored['bandwidth_hz']).is_integer():
                raise ValueError('stored bandwidth must be integer Hz')
            if stored['bandwidth_hz'] <= 0 or stored['carrier_khz'] <= 0:
                raise ValueError('stored bandwidth/carrier must be positive')
            if stored['carrier_khz'] + stored['offset_hz'] / 1000 <= 0:
                raise ValueError('stored center must be positive')
        elif record['choice'] == 'stored':
            raise ValueError('stored choice without tuning memory')

    def update(self, key: str, record: dict) -> None:
        self._validate(record)
        records = dict(self.records, **{key: record})
        if self.path is not None:
            # Write/replace before publishing in memory; failed writes preserve old state.
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix=self.path.name + '.', delete=False) as out:
                    name = out.name
                    json.dump(dict(schema=1, stations=records), out, allow_nan=False, indent=2)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(name, self.path)
            finally:
                if name is not None and os.path.exists(name):
                    os.unlink(name)
        self.records = records
