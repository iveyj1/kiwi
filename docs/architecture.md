# Architecture

## Main design

```text
Desktop UI
    |
Controller / Application State
    |
Receiver Client API
    |
+----------------------+----------------------+------------------+
| Kiwi Transport       | Protocol Parser      | Command Encoder  |
+----------------------+----------------------+------------------+
           |
           +--> Audio Pipeline --> Audio Output / Recorder / Detector
           |
           +--> Waterfall Pipeline --> Waterfall Model --> Renderer
           |
           +--> Status / S-meter / Metadata
```

## Rule

Protocol handling must be usable without the desktop UI.

Interactive receiver/playback lifecycle policy belongs in the controller layer, not in the TUI. See [Radio session state](radio-session-state.md) for the desired explicit session-state model around receiver switching, background playback, stale errors, and future bumpless transfer work. The staged extraction and frontend direction are defined in [Shared session and UI integration plan](ui-integration-plan.md).

Live transport startup follows the current Kiwi browser bootstrap: fetch `/VER` once, use its server-issued `ts` for `/ws/kiwi/<ts>/SND`, wait for `MSG badp=0`, then open `/ws/kiwi/<ts>/W/F`. Both streams therefore share one authenticated receiver session. HTTP bootstrap and URI construction are isolated in `session_bootstrap.py`; stream parsers remain network-independent.

Waterfall decoding and rendering should follow the same separation rule: W/F protocol parsing and the display model must be testable without UI or network access. See [Waterfall display specification](waterfall-spec.md). The standalone combined viewer coordinates separate W/F and SND tasks through exact selected-frequency state and command queues; it does not merge their transport lifecycles or parsers. `WaterfallSnapshotPublisher` provides bounded immutable numeric history snapshots, preserving each row's original frequency mapping while coalescing slow consumers onto the latest generation.

## Live RNA reception assistant

`rna_catalogue.py` loads immutable NDB records and source provenance, computes RF
components and site distances, and applies catalogue filters without UI/network
access. `rna_console.py` owns browsing/selection and receiver-to-site association;
selection never changes reception evidence. `rna_preferences.py` separately loads
and atomically saves filter/CLE/near/site preferences. Explicit CLI values override
saved defaults; runtime commands persist before publishing their changed state.
The interactive shell saves effective startup settings, whereas dry runs only read.
Catalogue, site TOML, station memories and reception records remain independent.
The integrated shell passes generic
frequency annotations to `waterfall_scale.py` and uses the existing controller
for explicit CW tuning, including search acceptance and next/previous selection.
Annotations distinguish the selected station from its active component. The pure
scale compositor uses that metadata for a horizontal station bracket below the
frequency scale and dotted C/L/U connectors confined to the footer. Its ID is drawn
once at the left; marker labels use three decimals and only the carrier has a c tag.
The selected station is excluded from the general catalogue annotation row. This
formatting does not round RF coordinates or modify component/tuning state. Offscreen
selected endpoints are retained to clip the span, but never create false edge
connectors. No marker ink enters the history region; source samples/rasters remain
unchanged. For the integrated console, `terminal_geometry.py` reads cell pixels via
TIOCGWINSZ (stable 8×16 estimate when unavailable). The compositor reserves footer
space, resamples only history to the remaining native pane dimensions, then draws
labels/markers at final pixel resolution. Kitty's cell placement therefore does not
stretch the already-composed text when measured cell dimensions are available.
Small panes reduce font size or report insufficient space rather than deforming
labels. Presenter cache keys include image pixel dimensions as well as cell geometry
and generation, so pixel/font-size changes repaint even without a new W/F frame.
It neither queries the catalogue/logbook nor infers missing sidebands.
`station_memory.py` maintains atomic personal JSON component choices and RF-center
plus bandwidth settings keyed by station identity, independently of immutable RNA
records. Stored-center recall converts RF passband center back to the existing CW
UI reference before dispatching ordinary tuning/filter commands. Transport and
protocol behavior are unchanged.

`ndb_logbook.py` stores explicit human decisions in SQLite with immutable catalogue
snapshots and revision history. The console freezes a draft before confirmation;
only committed writes report success. `reception_ui.py` reads existing logbooks
without creating/upgrading them, indexes station/receiver/event/source scope and
supplies main/search/form status. `console_panels.py` is the network-independent,
cell-width-aware Unicode renderer for the full-width main station spreadsheet and
B split logging page, with separately ruled FILTERS/KEYS/MESSAGE bands on the main
page. Compact windows keep keys/messages separate when space permits; the shortest
fallback retains identity/status/input. `reception_ui.station_spreadsheet` builds only a small window
of the filtered shortlist, joining read-only scoped log status without database
writes. Personal UTC status and RNA's last-logged date remain separate fields.
It clips within fixed columns and adapts to narrow/short terminals. Full-screen
forms clear only the Kitty placement, leaving source workers running, and trigger
a full console repaint on return. `w` revises the latest scoped hearing, while `W`
explicitly creates a repeat. Form edits retain frozen evidence; optimistic checks
reject stale edits when another writer has changed the record. Offline report generation independently
validates event/source/time/channel/receiver constraints. Fixture receptions retain
their provenance and cannot become live CLE evidence. There is no DSP, automatic
station identification, database download, or email submission in this branch.

## Suggested modules

```text
kiwi_transport
    WebSocket/session handling.

kiwi_protocol
    Frame parsing, command encoding, message types, units.

receiver_model
    Current frequency, mode, filter, status, S-meter, stream state.

audio
    Sample conversion, buffering, playback, recording.

waterfall
    Frame conversion, scaling, rendering model.

detectors
    MF/LF beacon detection and later long-integration analysis.

harness
    Fixture replay, synthetic frame generation, fake receiver server.

app
    Desktop UI shell.
```

## Dependency direction

```text
app -> receiver_model -> kiwi_protocol -> kiwi_transport
app -> audio
app -> waterfall
detectors -> audio/recording data
tests -> harness -> protocol/audio/waterfall/detectors
```

Avoid dependencies in the reverse direction.

## Non-goals for early milestones

- Large plugin framework
- Multi-user server architecture
- Public receiver crawling
- Complex database schema
- Automated unattended live-radio testing
