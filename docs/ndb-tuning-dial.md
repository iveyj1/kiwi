# NDB Tuning Dial Proposal

## Purpose

Use `rna-signals.csv` as a local beacon database to add an LF/MF NDB-aware tuning aid to the TUI. The feature should show nearby beacon carriers and Morse sidebands on a linear horizontal frequency dial around the current tuned frequency, plus a sortable/filterable station table.

This is proposed functionality, not yet implemented.

## CSV source

File: `rna-signals.csv`

Observed columns:

```text
KHz, ID, Type, Active, LSB, USB, Sec, Fmt, 'Name' and Location,
SP, ITU, Region, GSQ, Lat, Lon, Pwr, Notes, Heard In, Logs,
First Logged, Last Logged
```

Useful fields for the first feature:

- `KHz`: carrier frequency in kHz.
- `ID`: Morse beacon identifier.
- `Type`: use `NDB` initially; later optionally include `DGPS`/`Other`.
- `Active`: `Y`/`N`.
- `LSB`, `USB`: nominal sideband offsets in Hz.
- `Sec`: repetition period in seconds.
- `Fmt`: identifier format notes such as `DAID`, `Cont. ID`, etc.
- `'Name' and Location`: display name/location.
- `SP`, `ITU`: state/province and country.
- `Lat`, `Lon`: for distance/bearing.
- `Pwr`: transmitter power where known.
- `Last Logged`: recency indicator.

Sideband frequency convention:

```text
carrier_khz = KHz
lsb_khz = KHz - LSB / 1000       when LSB is present
usb_khz = KHz + USB / 1000       when USB is present
```

Store sideband offsets as signed display values too, e.g. `-1027 Hz` and `+1029 Hz`.

## TUI display concept

Add an optional `NDB` pane beneath or near the existing radio dashboard.

Example shape:

```text
NDB dial  214.900 .. 216.100 kHz    filters: active=yes dist<1000km SP=MI,OH,ON order=distance

                           |YTR-l      |YTR       |YTR-u
   |GR                               |GR-u
   |215|   |   |   |   |   |   |   |   |216|   |   |   |   |   |   |   |   |
                                         __|__  tuned 215.995 kHz

Selected / nearest beacons
ID   Carrier   LSB Hz   USB Hz   Name / location        SP  ITU  Dist    Brg  Active  Sec    Last logged
GR   263.000   -1027    +1029    'Knobs' Grand Rapids   MI  USA  100 km  270  Y       5.964  ...
YTR  215.000   -1045    +1008    Trenton                ON  CAN  ...     ...  Y       8.60   2026-05-23
```

The dial is linear in RF frequency. It should include:

- major frequency labels at integer kHz or configured spacing,
- minor tick marks between majors,
- beacon carrier markers,
- optional sideband markers,
- current tuned-frequency cursor,
- selected beacon emphasis.

## Range model

Initial dial range options:

1. Auto range around current frequency:
   - default +/- 1.5 kHz or enough to show sidebands for nearby carriers.
2. Fixed span command:
   - `:ndb span 3khz`
   - `:ndb span 10khz`
3. Center follows radio tuning by default:
   - current tuned frequency is the dial center unless an NDB is selected.

For NDB listening in CW/USB/LSB, the carrier can be outside the audible passband while the sideband tone is audible. The dial should therefore show both RF carrier and sideband frequencies.

## Commands

Primary command namespace: `ndb`.

Aliases:

- `ndb`
- `nd`

### Selection

```text
:ndb select gr
:ndb sel gr
:nd sel gr
```

Behavior:

- Match ID case-insensitively.
- If multiple beacons share an ID, choose according to current display order/filter, or show a disambiguation list.
- Optional exact selector later:
  - `:ndb select gr 263`
  - `:ndb select gr mi`

### Filters

```text
:ndb filter active yes
:ndb filter active no
:ndb filter active any

:ndb filter dist 500
:ndb filter distance 1000

:ndb filter sp MI,OH,ON
:ndb filter state MI,OH,ON
:ndb filter province MI,OH,ON

:ndb filter country USA,CAN
:ndb filter type NDB

:ndb filter clear
```

Short alias examples:

```text
:nd fi di 500
:nd fi sp MI,OH,ON
:nd fi ac yes
```

Abbreviation resolution should use the existing TUI command-hint style where practical, but ambiguous abbreviations should be rejected with a helpful message.

### Display order

```text
:ndb order distance
:ndb order freq
:ndb order id
:ndb order active
:ndb order last-logged
```

Short examples:

```text
:nd ord dist
:nd ord freq
```

### Dial controls

```text
:ndb show on|off
:ndb sidebands on|off
:ndb span 3khz
:ndb span 10khz
:ndb rows 5
:ndb next
:ndb prev
:ndb tune carrier
:ndb tune usb
:ndb tune lsb
```

Suggested key bindings later:

- `n` / `N`: next/previous displayed beacon.
- `Enter` on selected NDB row: tune selected sideband or carrier.
- Configurable default tune target: `carrier`, `usb`, `lsb`.

## Distance and bearing

Need a receiver/listener location. Suggested source order:

1. `[location] lat`, `[location] lon` in `config.toml`.
2. Current receiver metadata if reliable and exposed.
3. Optional command-set location.
4. Unknown; distance filters disabled with clear status.

Example config:

```toml
[location]
lat = 42.3300
lon = -83.7500
label = "local receiver"
```

Compute great-circle distance and initial bearing from listener to beacon using the CSV `Lat`/`Lon` fields.

Distance display can be rounded:

- `<100 km`: nearest km,
- `100..999 km`: nearest 10 km,
- `>=1000 km`: nearest 50 or 100 km.

## Filter semantics

Filters are **filter-in** rules: a station appears only if it matches every enabled filter. They are not hide/exclude rules.

Examples:

- `:ndb filter active yes` means display only active stations.
- `:ndb filter dist 500` means display only stations with known distance <= 500 km.
- `:ndb filter sp MI,OH,ON` means display only stations whose `SP` value is one of `MI`, `OH`, or `ON`.
- Multiple filters combine with AND: active=yes AND distance<=500 km AND SP in the selected list.
- Within a comma-separated value list, values combine with OR: `MI OR OH OR ON`.
- `:ndb filter clear` removes all filter-in constraints.

If a filter depends on missing data, e.g. distance when a beacon has no lat/lon or no listener location is configured, the station is not included unless that filter is disabled.

## Too many markers / density handling

A dial can become unreadable when many carriers/sidebands overlap. Use layered degradation:

1. Apply filter-in rules first:
   - active only,
   - distance cap,
   - state/province/country,
   - type.
2. Limit plotted rows/layers:
   - default 2 marker rows + 1 tick row.
   - overflow count shown: `+17 hidden; narrow filters or zoom in`.
3. Collision policy:
   - exact selected beacon always shown,
   - nearest-distance beacons shown before farther ones when ordered by distance,
   - active beacons shown before inactive when active filter is `any`,
   - sidebands can be hidden before carriers.
4. Aggregation marker:
   - if multiple markers map to the same cell, show `+` or `*` and list details in the table.
5. Zoom/span suggestions:
   - display hint: `too dense: :ndb span 1khz or :ndb filter dist 500`.

## Data model proposal

```text
BeaconRecord
  carrier_khz: float
  id: str
  type: str
  active: bool
  lsb_hz: int | None
  usb_hz: int | None
  period_sec: float | None
  format: str
  name_location: str
  state_prov: str
  country: str
  lat: float | None
  lon: float | None
  power_w: float | None
  notes: str
  last_logged: date | None

BeaconDerived
  lsb_khz: float | None
  usb_khz: float | None
  distance_km: float | None
  bearing_deg: float | None
```

Parser module should be independent from TUI:

```text
kiwi_client.beacons
  load_rna_csv(path) -> list[BeaconRecord]
  filter_beacons(records, filter_state, origin) -> list[BeaconView]
  dial_markers(records, center_khz, span_khz, show_sidebands) -> list[DialMarker]
```

Renderer module should be pure/testable:

```text
kiwi_client.ndb_dial_render
  render_dial(markers, center_khz, span_khz, width, selected_id) -> list[str]
  render_table(rows, width, max_rows) -> list[str]
```

## TUI integration

Keep responsibilities separated:

- CSV parsing/filtering in beacon module.
- Dial layout/rendering in pure renderer module.
- TUI only handles input state, command dispatch, and drawing returned strings.

TUI dashboard can include an `NDB` section when enabled:

- current filter summary,
- dial rows,
- selected/nearest station table,
- density warning if markers are hidden.

## Harness-first test plan

1. CSV parser fixture:
   - create a small fixture with a few active/inactive NDB records, duplicate IDs, sidebands, and missing fields.
2. Parser tests:
   - numeric conversion,
   - active conversion,
   - sideband frequency derivation,
   - missing sideband handling.
3. Distance tests:
   - known origin/beacon pair,
   - missing lat/lon gives no distance.
4. Filter tests:
   - active yes/no/any,
   - distance cap,
   - state/province list,
   - type.
5. Sort tests:
   - distance,
   - frequency,
   - ID,
   - last logged.
6. Dial renderer tests:
   - markers at expected columns,
   - sideband labels,
   - selected marker cursor,
   - collision/overflow behavior.
7. TUI command tests:
   - `ndb select`,
   - `ndb filter`,
   - abbreviations,
   - invalid ambiguous abbreviations,
   - dashboard section rendering.

No live radio is needed for the first implementation slice.

## Open questions

- Default listener location: receiver site, user home, or explicit config only?
- Should NDB selection retune RF immediately or only highlight until `ndb tune ...`?
- For CW mode, should `ndb tune usb/lsb` account for configured CW offset automatically?
- Should table default to only active NDBs, or active plus recently logged inactive beacons?
- How many marker rows fit comfortably in the existing TUI dashboard?
- Should `rna-signals.csv` be treated as bundled data, user-provided data, or both?

## Suggested first slice

Goal: offline NDB database and pure dial renderer.

Done criteria:

- Add a small CSV fixture under `tests/fixtures/ndb/`.
- Implement parser/filter/distance derivation without TUI dependencies.
- Implement pure text dial renderer for carrier + sidebands.
- Add tests for duplicate IDs and marker collisions.
- Add docs/user-guide notes for planned commands.
- No live radio testing.
