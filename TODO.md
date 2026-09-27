# TODO

## Current slice — persistent RNA filters and separated footer bands

Goal: restore RNA filter/CLE/sort/search/near state across starts, with explicit CLI
values overriding saved settings and runtime site support retained separately from
read-only site TOML. Atomic saves before applying changes; opt-out/reset, corrupt-file
and failed-write coverage. Add independent KEYS and MESSAGE rules without overflowing
small terminals. Completed: restart/precedence/rollback/corruption/read-only and
startup-save harnesses, separate-band layout coverage and updated docs/mockup.
607 tests pass; compileall/diff checks pass. Offline two-invocation PTY restored
activity/CLE/near settings and showed separate bands at 174 columns. No live radio
or real user-data writes; explicit CLI flags override restored preferences.

## Current slice — station bracket and full-width station spreadsheet

Goal: leave waterfall pixels untouched; draw a horizontal station span below the
frequency scale, with dotted LSB/carrier/USB connectors ending at its bottom edge.
Replace the main station/log split with a compact full-width scrolling shortlist:
ID, nominal kHz, scoped Logged status/time, location, distance, plain period, Last
(RNA last-logged date). Target 174 columns; retain compact/narrow terminals and
logging dialogs. Completed: geometry/viewport tests, scoped table/window/alignment
checks (including 174 columns), updated editable example and docs. 580 tests pass;
compileall/diff checks pass. Offline 174-column PTY navigation/log open/cancel passed;
synthetic bracket preview inspected. No radio access or user-data writes.

## Current slice — selected-station carrier/sideband markers

Goal: make the selected station's nominal carrier, known RNA LSB/USB and personal
stored center unambiguous on the waterfall and tuning scale, distinct from other
catalogue stations and the CW receiver reference. Dedicated selected-station label
row, RF-aligned dashed guides, no invented offsets or offscreen edge markers.
Completed: dedicated selected-station RF label row and dashed C/L/U/S guides;
active component white, others color-coded, missing/offscreen components omitted.
Fixed-raster regressions cover geometry, collisions, unknown offsets, stored sub-Hz
centers, station/component changes and immutable source pixels. 559 tests passed;
compileall/diff checks passed. No live-radio access or changes to user state.

## Current slice — 2/5 Hz CW bandwidth requests

Goal: extend bandwidth ladder with 2 and 5 Hz, preserving RF passband center despite
integer-Hz filter cuts. Odd/even transitions need a 0.5 Hz reference compensation;
skip unrepresentable steps when command frequency precision is below four decimals.
Completed: 2/5 Hz requested widths, RF-center compensation without parity drift,
coarse-precision skipping, and consistent catalogue tuning/log association. Synthetic
command fixture and regression coverage; 554 tests pass; compileall/diff checks pass.
Shipped config uses four command decimals. No live radio used: command
representability is not proof of the receiver's effective filter response.

## Current slice — not-heard/delete, nearby stations and editable screen examples

Goal: log review can mark not-heard or explicitly confirm deletion (audit retained),
cycle nearby catalogue components with ,/. around a fixed RF-center anchor, and
provide a current-renderer text example file for user edits. Nearby radius is in Hz,
current shortlist filters remain explicit; tuning must not walk the search anchor.
Completed: audited deletion/conflict/rollback and non-reused IDs, not-heard report
exclusion, nearby/component/fixed-anchor and shell regressions, CLI confirmation,
current-renderer editable examples and overwrite protection. 549 tests passed;
compileall/diff checks passed. No live radio or actual user reception/site edits.
Nearby cycle defaults ±200 Hz and honors the current RNA shortlist filters.

## Current slice — boxed A main page and B logging page

Goal: implement the chosen compact A main page with fixed station/reception columns,
and B full-screen editable/frozen-evidence logging view, using Unicode box drawing.
Preserve all radio/logging actions, resize safety and explicit save/cancel behavior.
Completed: pure layout/cell-width and updated shell regressions; offline Kitty/curses
pseudo-terminal smoke exercised A main, B new/edit, confirm/cancel and waterfall
return. Full suite 539 passed; compileall/diff checks passed. Guide/workshop updated.
No live-radio access or user-data changes. Existing timestamp | notes input remains;
Tab-based field navigation and older-entry picking are separate future features.

## Current slice — visible log history, edit-on-w and layout workshop

Goal: show selected station's scoped logging status/date in main, search and log
views; w edits the latest existing reception rather than duplicating it, W explicitly
creates a repeat. Preserve original receiver/tuning/catalogue evidence on edits.
Create a text workshop with several aligned, grouped main/log layouts; do not impose
a full redesign before review. Completed: read-only indexed history/error handling, edit/cancel/repeat and scope
regressions, stale-edit protection, three sample main/log layouts with verified
94-column rows/aligned separators. 495 tests pass; compileall/diff checks pass.
Full boxed redesign and older-entry picker remain proposals for review.
No live radio or changes to user log/config files.

## Current slice — automatic station tuning and personal station memories

Goal: search acceptance/n/N/v tune immediately, remember component per station,
first choice USB (carrier if unknown). Add explicit :rna store / forget for a
personal center-offset/full-bandwidth memory in a separate atomic JSON file;
include stored component in v cycle. Logs snapshot actual RF passband center,
nominal-carrier offset and width and export them as comments alongside notes.
Completed: atomic personal memory/restart/error tests, actual RF-center/CW midpoint
mapping, immediate navigation/search/component tuning regressions and report
snapshots. 488 tests passed, compileall/diff checks passed. No radio access;
local rna-sites.toml and RNA catalogue unchanged. :rna store / forget is explicit;
station choices/memories persist in rna-stations.json (--rna-memory override).

## Current slice — callsign search and runtime catalogue filters

Goal: /callsign opens a keyboard-selectable hits page, including excluded catalogue
rows with reasons; Enter selects without tuning. Add :rna range (<= km), power
(>= W), sort distance/frequency, cle on/off and site configuration commands.
Completed: inclusive thresholds/unknown handling, ID-only case-insensitive search,
atomic invalid commands, hidden MT209/CLE regression, fixture/live-editor shell input
coverage, updated docs. 479 tests pass; compileall/diff checks pass. No live radio
tests; running user session is untouched. Runtime filters/sites are session-only;
CLI and sites TOML remain startup configuration.

## Current slice — console bandwidth keys and section dividers

Goal: j/k decrease/increase CW full bandwidth through 10,20,30,50,100,500 Hz,
keeping the current passband midpoint fixed; h/l small steps and H/L large steps.
Separate general, database and help panels with horizontal dividers.
Completed: fixture/controller and shell-key/layout regressions, updated help/docs,
and 466 passing tests. j/k is CW-only and no longer changes volume. Command/prefix
input keeps priority; contextual hints remain, conflicting standalone key hints do
not. BW appears in status. Full widths preserve midpoint; unsupported half-Hz centers
are rejected explicitly. Compileall/diff checks pass. No live receiver access.

## Current slice — RNA live reception and logging

Branch/worktree: `feature/rna-live-logging`, `/home/user/kiwi-rna`, based on
`05698f6` (pre-analysis application). Preserve the analysis branch and main.

Goal: independent RNA catalogue, receiver-site distance/activity filters, then
live tuning-line markers and assisted human-confirmed logging. No offline DSP.

Milestones and done criteria:
- [x] Catalogue: immutable parsed records, raw-field/provenance retention, independent
  carrier/LSB/USB frequencies, explicit unknowns, receiver-site distances, validated
  filters and fixture-backed tests; offline inspection command.
- [x] UI: RNA scale markers, station selection/details and explicit component tuning;
  preserve nominal carrier and apply existing CW offset once; harness coverage.
- [x] Logbook: durable confirmed/tentative entries, editable hearing time, site/settings
  snapshots and duplicate warnings; persistence/recovery tests.
- [x] CLE332 report: reviewed final announcement, event-specific channel rules and
  configurable receiving-site timezone/metadata, plain-text preview and export tests.
  Never submit automatically. Other CLE rule sets remain a future extension.

Validation: 455 tests pass; compileall/diff checks pass; offline pseudo-terminal
smoke exercised markers, tuning, explicit confirmation and SQLite persistence.
No live-radio test or user listening verification. Before actual event export,
configure the true receiver/site/timezone/locator/equipment/aerial, listen and
confirm real receptions, then review the generated report. General-purpose event
profiles, in-session filter editing, station table and mouse picking remain later
refinements, not prerequisites for the implemented keyboard workflow.

The final CLE332 announcement is supplied and reviewed; see
`docs/cle332-live-logging.md` for source hash and confirmed rules. Older event data
is reference only, not the current candidate list. A remote event log must use one
receiver only; never silently combine fallback receiver loggings.
No live receiver connections are needed for the initial milestones.

## Current slice — Waterfall presentation cadence

Goal: reduce visible multi-row stepping by removing the console's 5 Hz presentation bottleneck before introducing a playout buffer.

Done criteria: 20 Hz console default and demo launcher; explicit lower refresh rates remain supported; offline cadence comparison and full tests pass; no additional buffering latency or receiver connections. User visual evaluation determines whether burst smoothing needs a separate bounded buffer.

## Previous slice — Cleanup and main merge preparation

Goal: consolidate the tested interactive client and local-address migration for review and merge into `main`, without merging or modifying `main` yet.

Done criteria: current planning/handoff docs agree; receiver defaults and presets have offline regression coverage; full tests, compilation, and diff checks pass; feature branch changes are committed; ancestry/merge readiness is recorded.

## Completed baseline

- Shared controller-owned paired SND/W/F session and typed tuning/view actions.
- Primary integrated Kitty/curses `kiwi-console`; optional native GUI prototype.
- Browser-style `/VER` bootstrap and SND `badp=0` gate before W/F startup.
- Stalled SND stop-fade regression fixed; bounded cooperative primary teardown with cancellation fallback.
- Double-buffered Kitty presentation, graphical tuning scale, signed CW passband and distinct nominal/RX markers.
- Immediate tuning, offscreen frequency-entry recentering, and one-span Up/Down/Page tuning.
- Runtime audio toggle, volume, receive-mode prefix, presets, receiver switching, and saved state.
- Controls remain usable before the first waterfall frame.
- Public-directory parser/export and checked receiver browser links.
- Local receivers: `.41`, `.42`, `.43` on port 8073. `.41` remains the general default; `.43` is preferred for local NDB work in its user-reported 4-channel configuration.
- Historical capture addresses are preserved, including retired `.40`.

## Remaining reliability work

- First-message, first-frame, and stalled-stream deadlines with explicit diagnostics.
- Rapid-switch stress coverage including stalled authentication and WebSocket opening/closing. One user-reported hang after the stop-fade fix remains unconfirmed, not dismissed as operator error.
- Audit every frontend's paired bootstrap, network guard, and cancellation path; shared helpers alone do not prove identical lifecycle behavior.
- Verify preset/receiver persistence during ordinary use.
- Complete reference-tool comparisons only when they resolve a specific outstanding compatibility question. No unpaired two-allocation fallback or reconnect loops.

## Waterfall presentation — deferred, not a merge requirement

- Measure acquisition cadence separately from terminal presentation (the usual console command presents at 5 Hz).
- Evaluate 15–20 Hz presentation, then an optional bounded 150–250 ms playout buffer if needed. Reset on view/receiver changes, freeze on starvation, and drop backlog after terminal stalls.
- Do not synthesize signal measurements to smooth scrolling.
- Expect 8-channel public receivers. User reports reduced maximum zoom (approximately 11 versus 14) and slower W/F cadence; exact values depend on firmware/mode and need metadata-backed tests, not hardcoded assumptions.
- Audit `zoom_max` versus `zoom_cap` propagation through parser, controller, and frontend before claiming full mode-dependent limit support.

## NDB/analysis direction

- Use received SND/IQ data for closer signal analysis; W/F is a navigation/overview display, not the measurement pipeline.
- Prefer local `10.0.0.43:8073` for NDB development; do not require its 4-channel W/F capabilities for public operation.
- Next architectural step: one SND consumer fan-out for playback, recording, and detection.
- Build the first beacon detector against synthetic/captured fixtures before live testing; long-term integration/correlation remains planned.

## Validation

Cleanup validation: 401 tests passed; compileall and diff checks passed. Local `main` (`0daae2f`) is an ancestor of the feature branch, allowing fast-forward integration if unchanged. Remote refs were not refreshed; check them before the actual merge. No merge or live-radio testing was performed. See `docs/dev-log.md` and `docs/handoff.md`.
