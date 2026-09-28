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

## Standalone logbook application

The standalone browser deliberately does not depend on the receiver controller:

```text
log_browser (Qt views, filters, selection by record ID)
    -> LogWorkspace / BrowserRecord / RecordRef (log_browser_data)
        -> NativeLogSource (SQLite mode=ro, committed current records)
        -> StagedLogSource (immutable WWSU review bundle)
wwsu_history (offline MDBTools/report adapter) -> separate review bundle
```

`BrowserRecord` is a frozen display projection, **not the authoritative editable
record**. Its immutable evidence serialization retains original/unknown fields.
`RecordRef` carries source kind, path, original key and revision fingerprint.
Native keys are SQLite reception IDs; their payload fingerprints change on edits,
not when sorting/filtering. WWSU display IDs use archive namespace + logical event
key + same-minute occurrence; raw source row references are tied to hashed backup
files. Report candidates retain source line references. Moving an archive changes
its staging namespace; a stage is not yet a durable imported database identity.

This split is intentional preparation for editing, not a read-only storage design:

- Future commands receive the selected record reference and expected original
  snapshot, never a table row number or reconstructed display cells.
- A native write adapter should use the existing audited `Logbook.revise/delete`
  paths and optimistic expected-record checks, then reload the projection. The
  read adapter must not instantiate `Logbook`, whose constructor initializes schema.
- Historical acceptance/editing needs an audited historical store or overlay with
  durable IDs and links back to immutable source evidence. Do not write to Access
  backups/stages, route staged references to native write commands, fabricate missing
  RF evidence, or force legacy data through the live-reception validator.
- Commands must validate source capabilities and current revisions before writes;
  import reconciliation is explicit. Frozen display objects do not preclude edits:
  a successful command produces a new projection while preserving prior revisions.

Qt owns no SQL connections or protocol state. Loaders and filters are testable without
Qt. Failed source refreshes retain the previous source snapshot with visible errors.
UTC precision, computed versus recorded distance, backup versions and ambiguous
report matches remain distinct; the combined view is not a permanent database merge.
See [user guide](user-guide.md#standalone-logbook-browser) for operation and limitations.

## Rule

Protocol handling must be usable without the desktop UI.

Interactive receiver/playback lifecycle policy belongs in the controller layer, not in the TUI. See [Radio session state](radio-session-state.md) for the desired explicit session-state model around receiver switching, background playback, stale errors, and future bumpless transfer work. The staged extraction and frontend direction are defined in [Shared session and UI integration plan](ui-integration-plan.md).

Live transport startup follows the current Kiwi browser bootstrap: fetch `/VER` once, use its server-issued `ts` for `/ws/kiwi/<ts>/SND`, wait for `MSG badp=0`, then open `/ws/kiwi/<ts>/W/F`. Both streams therefore share one authenticated receiver session. HTTP bootstrap and URI construction are isolated in `session_bootstrap.py`; stream parsers remain network-independent.

Waterfall decoding and rendering should follow the same separation rule: W/F protocol parsing and the display model must be testable without UI or network access. See [Waterfall display specification](waterfall-spec.md). The standalone combined viewer coordinates separate W/F and SND tasks through exact selected-frequency state and command queues; it does not merge their transport lifecycles or parsers. `WaterfallSnapshotPublisher` provides bounded immutable numeric history snapshots, preserving each row's original frequency mapping while coalescing slow consumers onto the latest generation.

## Live viewport freshness and personal station flags

Before a live W/F view command is queued, `ClientController` sets the requested view
on `WaterfallSnapshotPublisher`. This clears history and advances generation so
incremental raster caches rebuild. The publisher compares each incoming contextualized
frame's start/zoom with the requested geometry, rejecting old or unmapped rows even
after matching rows begin. Normal frequency changes that do not move W/F are unaffected;
fixture remapping remains available. Pending-view retunes supersede the target.

Station memory accepts an optional boolean `marked`, toggled atomically by Space.
The spreadsheet displays it separately from selection and reception status. New
reception drafts freeze its `*` as editable notes; existing logs are not modified.
Store/forget/component actions preserve the marker.

CLE export remains a pure validation/formatting function. Receiver identity mismatch
raises a specific exception unless the caller explicitly acknowledges it. The CLI
warns/prompts on stderr, defaults to cancellation, and includes the warning in an
acknowledged review draft. Neither acceptance nor formatting changes frozen evidence.

## Integrated-console focus and render pacing

`terminal_input.py` recognizes raw xterm CSI I/O focus reports and ncurses extended
`kxIN`/`kxOUT` key names (numeric codes vary by terminfo). A bounded prefix decoder
preserves ordinary keys and times out a standalone Escape. The Kitty presenter owns
DECSET/DECRST 1004 reporting lifetime. Focus loss suppresses presentation only;
source polling, audio and bounded history remain active. Focus gain invalidates the
image cache and forces a full text redraw from the current snapshot.

Render deadlines retain normal fast-frame cadence but reserve keyboard service time
after completion. Late frames wait another frame period instead of immediately
rendering again with only one input poll between slow writes. Terminal writes remain
synchronous; a single blocked write cannot be interrupted by this policy.

## Integrated-console radio-state checkpoints

`console_state.py` checkpoints zoom, per-mode passbands, step-pair indices and display
scale (dB endpoints plus automatic/manual mode) into the existing
`[startup].state_file`. `state_store.py` writes atomically and retains the optional
nested `last_state.waterfall_zoom` and validated `last_state.waterfall_scale` during
legacy TUI state saves. Scale fields restore independently and explicit CLI flags
win. Automatic level adaptation is excluded from change detection to avoid periodic
telemetry-driven disk writes; final levels are saved on exit. Startup mode `last`
restores it (old files fall back to configured zoom); default/preset startup remains
explicit. Integrated startup retains restored step indices unless step flags are
explicitly supplied; the GUI model and dry-run report use the effective pair.
Step-pair values remain config-owned. The live shell checkpoints changed settings and orderly exit without
writing presets on every change. Failed writes retain the old file, report an error,
and are not retried every frame. Fixture/dry-run paths do not enable checkpoints.
Legacy sub-10 Hz CW startup/recall requests widen to 10 Hz while preserving modeled
RF center; archived receptions and stored-memory files remain unchanged.

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
