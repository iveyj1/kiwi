"""Read WWSU backups/reports into a separate, provenance-preserving review stage.

Never executes WWSU, writes Access databases, or imports into the live logbook.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from kiwi_client.log_browser_data import BrowserRecord, RecordRef, fingerprint, utc_timestamp
from kiwi_client.rna_catalogue import distance_km

MONTHS = {name: i + 1 for i, name in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}


def backup_order(path: Path):
    match = re.fullmatch(r'ndbdata(\d{4})_([A-Za-z]{3})_(\d{2})_(\d{4})\.wbs', path.name)
    if not match or match[2] not in MONTHS:
        raise ValueError(f'unrecognized backup name: {path.name}')
    return int(match[1]), MONTHS[match[2]], int(match[3]), match[4]


def find_mdb_export(explicit: str | None = None) -> str:
    candidate = explicit or shutil.which('mdb-export')
    if not candidate:
        local = Path.home() / '.local/share/kiwi-client/mdbtools/bin/mdb-export'
        if local.is_file():
            candidate = str(local)
    if not candidate:
        raise ValueError('mdb-export is required to stage Access backups; install mdbtools or use --mdb-export PATH')
    return candidate


def mdb_table(executable: str, path: Path, table: str) -> list[dict]:
    result = subprocess.run([executable, str(path), table], capture_output=True, text=True,
                            encoding='utf-8', timeout=60, check=True)
    if result.stderr.strip():
        raise ValueError(f'{path.name}/{table}: reader warning: {result.stderr.strip()}')
    return list(csv.DictReader(io.StringIO(result.stdout)))


def coordinate(value: str) -> float | None:
    value = value.strip().upper()
    if not re.fullmatch(r'(?:[NSEW]\d+|\d+[NSEW])', value):
        return None
    hemi = next((c for c in value if c in 'NSEW'), '')
    digits = ''.join(c for c in value if c.isdigit())
    degree_digits = 2 if hemi in ('N', 'S') else 3
    if not hemi or len(digits) < degree_digits + 4:
        return None
    degrees = int(digits[:degree_digits])
    minutes = int(digits[degree_digits:degree_digits + 2])
    tail = digits[degree_digits + 2:]
    seconds = int(tail) / 10 ** (len(tail) - 2)
    if minutes >= 60 or seconds >= 60 or degrees > (90 if degree_digits == 2 else 180):
        return None
    result = degrees + minutes / 60 + seconds / 3600
    if result > (90 if degree_digits == 2 else 180):
        return None
    return -result if hemi in ('S', 'W') else result


def site_distance(station: dict, site: dict) -> float | None:
    values = [coordinate(row.get(field, '')) for row in (site, station) for field in ('Latitude', 'Longitude')]
    if None in values or values[:2] == [0, 0] or values[2:] == [0, 0]:
        return None
    return distance_km(*values)


def log_key(row: dict) -> tuple:
    return tuple(row.get(k, '').strip() for k in ('Beacon_ID', 'LoggedLocation', 'ReceptionDate', 'ReceptionTime'))


def canonical(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def report_rows(path: Path):
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    context = [line for line in text.splitlines() if not re.match(r'^\s*\d{4}-\d\d-\d\d', line)]
    comments = {key: value.strip() for key, value in re.findall(r'^\s*(\d+)\s+-\s+(.+)$', text, re.MULTILINE)}
    receiver = next((line.split(':', 1)[1].strip() for line in text.splitlines()
                     if line.strip().startswith('Listening Location:')), 'Unknown report setup')
    header = next((line.strip() for line in text.splitlines() if line.strip().startswith('YYYY-MM-DD')), '')
    if 'UTC' not in header:
        raise ValueError(f'{path.name}: report does not label its times UTC')
    units = re.search(r'\b(mi|km)\b', header)
    if not units:
        raise ValueError(f'{path.name}: unrecognized report distance units')
    distance_factor = 1.609344 if units[1] == 'mi' else 1
    for number, line in enumerate(text.splitlines(), 1):
        if not re.match(r'^\s*\d{4}-\d\d-\d\d', line):
            continue
        if path.suffix.lower() == '.csv':
            fields = [s.strip() for s in next(csv.reader([line]))]
            if len(fields) < 11:
                raise ValueError(f'{path.name}:{number}: incomplete CSV report row')
            day, clock, frequency, ident, miles, comment, new, grid = fields[:8]
            location, region, country = ', '.join(fields[8:-2]), fields[-2], fields[-1]
        else:
            match = re.match(r'^\s*(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d)\s+([\d.]+)\s+(\S+)\s+(.*)$', line)
            if not match:
                raise ValueError(f'{path.name}:{number}: unrecognized text report row')
            day, clock, frequency, ident, rest = match.groups()
            grid_match = re.search(r'\b[A-Ra-r]{2}\d{2}[A-Xa-x]{2}\b', rest)
            grid = grid_match[0] if grid_match else ''
            prefix = rest[:grid_match.start()] if grid_match else rest
            miles_match = re.match(r'\s*([\d,]+)\s+', prefix)
            miles = miles_match[1] if miles_match else ''
            comment = line[header.index('Cmt'):header.index('New')].strip() if 'Cmt' in header else ''
            new = line[header.index('New'):header.index('Grid')].strip() if 'New' in header else ''
            location = rest[grid_match.end():].strip() if grid_match else re.sub(r'^\s*\d+\s+', '', rest)
            parts = [s.strip() for s in location.rsplit(',', 2)]
            country = parts[-1] if len(parts) > 1 else ''
            region = parts[-2] if len(parts) > 2 else ''
            if len(country) != 3: country = ''
            if len(region) != 2: region = ''
            if country:
                location = ', '.join(parts[:-2] if region else parts[:-1])
        stamp = utc_timestamp(f'{day}T{clock}:00Z')
        notes = comments.get(comment, '') if comment else ''
        flags = ['Report-only reception; review before import']
        if comment and not notes:
            flags.append('Unresolved report comment reference: ' + comment)
        details = dict(line_number=number, raw_line=line, report_context=context, grid=grid, new_flag=new,
                       comment_reference=comment, report_comments=comments,
                       distance_basis='report miles converted to km' if distance_factor != 1 else 'report km')
        yield stamp, ident, float(frequency), country, region, location, (
            float(miles.replace(',', '')) * distance_factor if miles else None), notes, receiver, flags, details


def build_stage(root: Path, read_table) -> dict:
    root = root.expanduser().resolve()
    backups = sorted(root.glob('ndbdata*.wbs'), key=backup_order)
    if not backups:
        raise ValueError('no ndbdata*.wbs backups found')
    manifest = []
    observations = defaultdict(list)
    latest_keys = set()
    family = fingerprint(str(root))[:16]
    for path in backups:
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append(dict(path=str(path), sha256=sha, kind='Access backup'))
        logs = read_table(path, 'NDBLog')
        wanted = {r['Beacon_ID'] for r in logs}
        stations = {r['Beacon_ID']: r for r in read_table(path, 'NDBInformation') if r['Beacon_ID'] in wanted}
        personal = {str(100000 + int(r['NewBeacon_ID'])): r for r in read_table(path, 'NewBeacons')}
        stations.update(personal)
        sites = {r['ID']: r for r in read_table(path, 'ListeningLocation')}
        counts = Counter(log_key(row) for row in logs)
        latest_keys = set(counts)
        grouped = defaultdict(list)
        for ordinal, row in enumerate(logs):
            key = log_key(row)
            grouped[key].append(dict(row=row, ordinal=ordinal, station=stations.get(row['Beacon_ID'], {}),
                                     site=sites.get(row['LoggedLocation'], {})))
        for key, group in grouped.items():
            observations[key].append(dict(file=str(path), sha256=sha, rows=group))
    records = []
    for key, versions in observations.items():
        final = versions[-1]
        older_only = key not in latest_keys
        signatures = {canonical([item['row'] for item in version['rows']]) for version in versions}
        for occurrence, item in enumerate(final['rows']):
            row, station, site = item['row'], item['station'], item['site']
            flags = []
            if older_only: flags.append('Absent from newest backup; possible deletion or edited timestamp')
            if len(signatures) > 1: flags.append('Log values differ across backup versions')
            if len(final['rows']) > 1: flags.append('Multiple same-minute records; preserved separately')
            if not station: flags.append('Unresolved beacon reference ' + row['Beacon_ID'])
            if not site: flags.append('Unresolved listening-location reference ' + row['LoggedLocation'])
            if 'NewBeacon_ID' in station: flags.append('Personal beacon; 100000 + NewBeacon_ID linkage')
            raw_date, raw_time = row['ReceptionDate'].strip(), row['ReceptionTime'].strip().zfill(4)
            stamp = datetime.strptime(raw_date + raw_time, '%Y%m%d%H%M').replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            evidence = dict(log=row, station=station, listening_location=site, backup_versions=versions,
                            distance_basis='calculated from backup station/setup coordinates',
                            time_basis='WWSU date/time interpreted as UTC, consistent with exported report headers')
            region = station.get('State', '').strip()
            if region == 'XX': region = ''
            records.append(BrowserRecord(
                id=f'wwsu:{family}:{fingerprint(canonical(key))[:24]}:{occurrence}',
                reference=RecordRef('wwsu-access', final['file'], f'NDBLog:{item["ordinal"]}', final['sha256']),
                heard_utc=stamp, ident=station.get('Ident', '?').strip(),
                frequency_khz=float(station.get('Frequency') or 0), country=station.get('Country', '').strip(),
                region=region, location=station.get('City', '').strip(),
                distance_km=site_distance(station, site), receiver=site.get('LocationName', 'Unknown setup').strip(),
                status='review' if older_only or not station else 'historical', notes=row.get('ReceptionComments', '').strip(),
                source='WWSU older-only' if older_only else 'WWSU database', precision='minute',
                flags=tuple(flags), evidence_json=canonical(evidence)))
    by_event = defaultdict(list)
    for index, record in enumerate(records):
        by_event[(record.heard_utc, record.ident.upper(), record.frequency_khz)].append(index)
    by_time_ident = defaultdict(list)
    for index, record in enumerate(records):
        by_time_ident[(record.heard_utc, record.ident.upper())].append(index)
    report_only = {}
    for path in sorted([*root.glob('*Report*.txt'), *root.glob('*Report*.csv')]):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append(dict(path=str(path), sha256=sha, kind='report'))
        occurrences = Counter()
        matched_in_report = set()
        for stamp, ident, frequency, country, region, location, km, notes, receiver, flags, details in report_rows(path):
            evidence = dict(file=str(path), sha256=sha, receiver=receiver, notes=notes,
                            country=country, region=region, location=location, distance_km=km, **details)
            event = (stamp, ident.upper(), frequency)
            candidates = [i for i in by_event[event] if not country or records[i].country == country]
            if len(candidates) == 1 and candidates[0] not in matched_in_report:
                index = candidates[0]
                matched_in_report.add(index)
                old = records[index]
                raw = json.loads(old.evidence_json)
                raw.setdefault('report_evidence', []).append(evidence)
                extra = ()
                if notes and notes != old.notes:
                    extra = ('Report notes differ; original database notes retained',)
                records[index] = replace(old, evidence_json=canonical(raw), flags=tuple(dict.fromkeys(old.flags + extra)))
                continue
            # Only exact repeated report rows are coalesced; ambiguous matches remain review items.
            base = canonical([event, country, region, receiver, location, km, notes, details['grid'], details['new_flag']])
            signature = canonical([base, occurrences[base]])
            occurrences[base] += 1
            if signature in report_only:
                index = report_only[signature]
                old = records[index]
                raw = json.loads(old.evidence_json)
                raw['reports'].append(evidence)
                records[index] = replace(old, evidence_json=canonical(raw))
                continue
            if len(candidates) > 1: flags.append('Ambiguous match to multiple database receptions')
            elif candidates: flags.append('Repeated report row for the same database reception')
            alternatives = [i for i in by_time_ident[event[:2]]
                            if records[i].frequency_khz != frequency and
                            (not country or records[i].country == country)]
            if alternatives:
                flags.append('Same UTC/ID but different database frequency; possible catalogue change')
                evidence['possible_database_matches'] = [records[i].id for i in alternatives]
            record = BrowserRecord(
                id=f'wwsu-report:{family}:{fingerprint(signature)}',
                reference=RecordRef('wwsu-report', str(path), str(details['line_number']), sha),
                heard_utc=stamp, ident=ident, frequency_khz=frequency, country=country, region=region,
                location=location, distance_km=km, receiver=receiver, status='review', notes=notes,
                source='WWSU report-only', precision='minute', flags=tuple(flags),
                evidence_json=canonical(dict(reports=[evidence])))
            report_only[signature] = len(records)
            records.append(record)
    return dict(schema=1, kind='wwsu-review-stage', root=str(root), newest_backup=str(backups[-1]),
                created_utc=datetime.now(timezone.utc).isoformat(), sources=manifest,
                records=[asdict(record) for record in records])


def write_stage(path: Path, data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)  # Exclusive publication; never overwrite a reviewed stage.
    finally:
        if name and os.path.exists(name): os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Stage WWSU history for review; no live-log import or source modification')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='new JSON stage file, never overwritten')
    parser.add_argument('--mdb-export', help='path to the mdbtools reader')
    args = parser.parse_args(argv)
    try:
        executable = find_mdb_export(args.mdb_export)
        data = build_stage(args.directory, lambda path, table: mdb_table(executable, path, table))
        write_stage(args.output, data)
        counts = Counter(row['source'] for row in data['records'])
        print(json.dumps(dict(output=str(args.output), records=len(data['records']), by_source=counts), indent=2))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
