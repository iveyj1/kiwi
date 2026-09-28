"""Offline review staging of Kiwi DX label notes; never connects to a receiver."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import unquote

from kiwi_client.log_browser_data import BrowserRecord, RecordRef
from kiwi_client.history_staging import write_stage

# Match whole date-like tokens first: never salvage a valid-looking prefix from a
# malformed time/date. These exports use compact ISO-like times and optional Z.
DATE_TOKEN = re.compile(r'(?<!\w)\d{4}-\d{2}-[^\s,;]+')
STAMP = re.compile(r'(\d{4}-\d{2}-\d{2})[Tt](\d{2})(\d{2})([Zz]?)')
NON_NDB = re.compile(r'\b(?:FSK|NAVTEX|NOTAMS|WSPR)\b', re.IGNORECASE)


def note_dates(notes: str):
    matches = list(DATE_TOKEN.finditer(notes))
    results = []
    for index, match in enumerate(matches):
        token = match[0]
        precision, stamp, issue = 'unknown', '', ''
        parsed = STAMP.fullmatch(token)
        try:
            if parsed:
                value = datetime.strptime(''.join(parsed.groups()[:3]), '%Y-%m-%d%H%M')
                stamp = value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
                precision = 'minute'
            elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', token):
                stamp = datetime.strptime(token, '%Y-%m-%d').date().isoformat()
                precision = 'day'
                issue = 'Date only; hearing time not recorded'
            else:
                issue = 'Malformed date/time; original text retained: ' + token
        except ValueError:
            issue = 'Invalid calendar date/time; original text retained: ' + token
        end = matches[index + 1].start() if index + 1 < len(matches) else len(notes)
        results.append(dict(token=token, start=match.start(), end=match.end(), heard_utc=stamp,
                            precision=precision, issue=issue,
                            segment=notes[match.start():end].strip(),
                            timezone_basis='explicit Z' if parsed and parsed[4] else 'UTC assumed by user instruction'))
    return results


def build_label_stage(path: Path, *, minimum_khz=190.0, maximum_khz=530.0,
                      review_before_year=2020) -> dict:
    if not (math.isfinite(minimum_khz) and math.isfinite(maximum_khz) and 0 <= minimum_khz <= maximum_khz):
        raise ValueError('invalid label frequency range')
    path = path.expanduser().resolve()
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    archive = json.loads(raw)
    if not isinstance(archive, dict) or not isinstance(archive.get('dx'), list):
        raise ValueError('expected a Kiwi label object with a dx array')
    records, excluded = [], []
    selected = 0
    for index, row in enumerate(archive['dx']):
        if (not isinstance(row, list) or len(row) < 4 or
                not isinstance(row[0], (int, float)) or isinstance(row[0], bool) or
                not math.isfinite(row[0]) or not all(isinstance(v, str) for v in row[1:4])):
            raise ValueError(f'dx[{index}]: malformed label row')
        frequency, mode = float(row[0]), row[1].upper()
        label, notes = unquote(row[2]), unquote(row[3])
        reason = ''
        if not minimum_khz <= frequency <= maximum_khz:
            reason = 'outside selected NDB frequency range'
        elif (mode not in ('CW', 'CWN', 'IQ') or NON_NDB.search(label + ' ' + notes)
              or any(isinstance(options, dict) and str(options.get('p', '')).lower() in ('fsk', 'navtex', 'wspr')
                     for options in row[4:])):
            reason = 'obvious non-NDB mode/service'
        if reason:
            excluded.append(dict(index=index, reason=reason))
            continue
        selected += 1
        split = label.strip().split(maxsplit=1)
        ident = split[0] if split else '?'
        location = split[1] if len(split) == 2 else ''
        tokens = note_dates(notes)
        if not tokens:
            tokens = [dict(token='', start=None, end=None, heard_utc='', precision='unknown',
                           issue='No dated hearing in label notes; not reception evidence',
                           segment=notes, timezone_basis='not recorded')]
        prefix = notes[:tokens[0]['start']].strip() if tokens[0]['start'] is not None else ''
        for occurrence, token in enumerate(tokens):
            flags = ['Label frequency is not a nominal channel; station association unreviewed']
            if token['issue']:
                flags.append(token['issue'])
            if token['heard_utc'] and int(token['heard_utc'][:4]) < review_before_year:
                flags.append(f'Early date before {review_before_year}; preserved without correction')
            if token['heard_utc']:
                kind = 'reception'
                status = 'review' if token['issue'] or len(flags) > 1 else 'historical'
            else:
                kind = 'label'
                status = 'review' if token['token'] else 'reference'
            evidence = dict(original_row=row, label_index=index, decoded_label=label,
                            decoded_notes=notes, note_token=token, original_note_prefix=prefix,
                            label_frequency_khz=frequency, mode=mode,
                            receiver_basis='Archive origin is not proof of historical receiving equipment',
                            distance_basis='not recorded or inferred',
                            import_policy='UTC assumed for unzoned times; no nominal frequency or station inference')
            records.append(BrowserRecord(
                id=f'kiwi-label:{digest}:{index}:{occurrence}',
                reference=RecordRef('kiwi-label-json', str(path), f'dx[{index}]/note[{occurrence}]', digest),
                heard_utc=token['heard_utc'], ident=ident, frequency_khz=frequency,
                country='', region='', location=location, distance_km=None,
                receiver='Not recorded (label archive)', status=status,
                notes=' '.join(part for part in (prefix, token['segment']) if part),
                source='Kiwi labels', precision=token['precision'], flags=tuple(flags),
                evidence_json=json.dumps(evidence, ensure_ascii=False, allow_nan=False),
                frequency_basis='label', row_kind=kind))
    return dict(schema=1, kind='kiwi-label-review-stage', sources=[dict(path=str(path), sha256=digest)],
                created_utc=datetime.now(timezone.utc).isoformat(),
                options=dict(minimum_khz=minimum_khz, maximum_khz=maximum_khz,
                             review_before_year=review_before_year, unzoned_times='assume UTC'),
                # Preserve the complete original JSON, including unknown fields/excluded labels.
                original_archive=archive, excluded=excluded,
                summary=dict(selected_labels=selected, excluded_labels=len(excluded),
                             rows=len(records), row_kinds=dict(Counter(r.row_kind for r in records)),
                             precisions=dict(Counter(r.precision for r in records))),
                records=[asdict(record) for record in records])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Stage NDB label history separately; unzoned note times assumed UTC')
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--minimum-khz', type=float, default=190)
    parser.add_argument('--maximum-khz', type=float, default=530)
    parser.add_argument('--review-before-year', type=int, default=2020)
    args = parser.parse_args(argv)
    try:
        data = build_label_stage(args.input, minimum_khz=args.minimum_khz,
                                 maximum_khz=args.maximum_khz, review_before_year=args.review_before_year)
        write_stage(args.output, data)
        print(json.dumps(data['summary'], indent=2))
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
