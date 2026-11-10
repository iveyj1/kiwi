# Archived live-phase task log

Historical snapshot of TODO.md before the 2026-11-10 cleanup. Test counts and
"current slice" labels below describe earlier milestones, not current instructions.
See [current TODO](../../TODO.md) for active work.

## Current slice — live-phase merge preparation (analysis retained separately)

Goal: audit all 16 analysis-only commits for reusable fixes without merging
recorded/analysis workflows. Port only independently useful fixes with regressions;
validate this live/RNA phase, document launch/data migration and leave main and
../kiwi unchanged pending merge approval. Safety refs created for all three tips.
Baseline: 776 offline tests passed. Candidate ports: bounded raster padding cache,
auto-level cadence reset, shutdown cleanup, and guarded interactive tuning errors.
Done: audited commit dispositions, failing-then-passing regressions, full suite,
portable CLI/browser smoke checks and a committed merge-readiness report.

## Shading visibility follow-up

Goal: raise guide background from RGB 24 to 56 after operator feedback that it
was barely visible. Done: pixel/layering regressions pass; geometry unchanged.

## Current slice — common NDB frequency-region shading

Goal: slightly lighten only the tuning-bar background at integer-kHz ±100 Hz
and integer-kHz ±400 Hz ±50 Hz, when RNA browsing is enabled. Keep markers on top,
waterfall history unchanged, and suppress unresolved shading when zoomed out.
Done: synthetic boundary/pixel regressions, full offline suite, user docs and commit.
No receiver access or personal data changes.
Completed: dark-gray background guides behind existing markers, RNA-only, with
boundary/native-size/layering tests. Full offline suite: 776 passed.

## Current slice — receiver popup and blank-view diagnosis

Goal: a lower-text-area receiver popup with stable geometry, scrolling, explicit
selection/cancellation and unchanged receiver-switch lifecycle. Investigate blank
waterfall after edge tuning without weakening stale-frame rejection. Done criteria:
offline popup/input/layout regressions, actionable waiting-view diagnostics, full
suite and docs. No personal log changes.
Completed: lower-text popup and diagnostic regressions; reproduced and fixed the
blank view caused by advertised acquisition zoom cap z11 versus requested z12.
773 offline tests pass. Two short local receiver-1 tests (reproduction, then
verification after regressions passed) are recorded in docs/kiwi-protocol.md.

## Current slice — inline reception entry and centered catalogue stepping

Goal: w/W open a one-line main-page log editor (update latest / new hearing).
Enter saves the displayed status and comment; Tab toggles confirmed/tentative;
Esc cancels. New hearings default confirmed; updates retain status and original
hearing/tuning evidence. Guard selection/tuning consistency and consume typing
before radio shortcuts. Keep detailed editing available separately. Audio and
waterfall presentation continue. n/N immediately tune and center the selected
frequency, including selections already inside the viewport. Done: synthetic
input/layout/persistence/centering regressions, full offline suite, docs and commit;
no receiver access or personal log changes.
Completed: inline draft/save/status flow, B/F2 advanced editor, Unicode-safe active
line, and unconditional n/N recenter via existing view actions. 752 offline tests
pass; a real-curses offline PTY saved a tentative note while graphics continued.
Current synthetic layout: docs/ui-inline-log-174.txt; older editable mockups retained.

## Requested follow-up work

- [x] Improve the logging flow with one-line entry directly on the main screen
  (w/W, Enter save, Tab confirmed/tentative, Esc cancel; B/F2 for details).
- [ ] Collect evidence when adding a log entry: audio recording plus a snapshot
  of the waterfall, frequency/tuning settings and displayed text, linked to the
  reception record.
- [ ] Further improve the text layout.
- [ ] Investigate waterfall smoothness when connected to an 8-channel KiwiSDR;
  the user currently observes jumpy updates. Diagnose timing/buffering/rendering
  with harness coverage before targeted local-receiver testing.

## Current slice — explicit logbook quit controls

Goal: add visible Quit and window-scoped Ctrl+Q, using normal window close rather
than forced process termination. Done: offscreen keyboard/button regressions with
child-widget focus, unchanged source/preferences checks, full suite and docs. Do
not attribute the reported Alt+F4 failure to Kitty without evidence.
Completed: shared Quit action/button and Ctrl+Q call normal window close. Six
regressions cover child focus, button activation, unchanged source/preferences and
subprocess event-loop exit; full offline suite passes (725 tests). No live access.

## Current slice — Kiwi label history

Goal: stage the supplied label JSON alongside existing sources, read-only. Use
190–530 kHz and exclude obvious non-NDB services. User authorizes UTC for unzoned
note times. Preserve separate hearings, original label frequencies (not nominal
channels), raw fields and source references; retain undated/malformed/date-only
notes explicitly without invented times. Do not merge/deduplicate other sources.
Done criteria: synthetic parser/model/UI regressions, actual-file staging/hash
checks, full offline suite, docs and tested commit. No receiver access.
Completed: 538 selected labels -> 289 timed + one date-only candidate and 278
undated reference/review rows. Separate default stage, explicit label-frequency
basis, no fabricated timestamps or station association. 719 offline tests and
actual-data Qt/hash checks pass; 1,250 combined rows. Restart browser for new source.

## Current slice — standalone historical log browser

Goal: separate read-only desktop browser for native SQLite receptions and staged
WWSU history. Sort/search/filter, station history, provenance/raw details and saved
views. Source adapters own stable record references and revision fingerprints;
Qt is only a projection, leaving room for audited/conflict-checked edit commands.
Stage overlapping WWSU backups/reports without merging into receptions.sqlite or
promoting historical entries to confirmed/CLE records. Preserve same-minute rows,
flag older-only/conflicting records, and keep original files untouched. Done:
synthetic import/read-only/filter/UI harnesses, actual-data staging and offscreen
GUI smoke check, docs and full offline suite. No radio access.
Completed: standalone desktop browser and source adapters, lossless-source review
stager, isolated preferences and edit-ready record references. Local combined view:
682 rows (61 native + 621 WWSU review rows); no permanent merge. Synthetic/offscreen
harnesses and actual-data read-only smoke pass; 704 offline tests pass. Original
WWSU inputs and native database unchanged. Physical desktop inspection pending.

## Current slice — export layout and latest confirmed reception

Goal: apply the requested report edits to future exports: aligned UTC/frequency/ID/
distance-km columns, no automatic center/offset/BW comments, receiver description
without internal address suffix. Use latest eligible confirmed reception per station,
not earliest. Keep handwritten notes and frozen evidence. Set local equipment label
to KiwiSDR 2 without committing personal files. Done: golden/ordering/alignment tests,
full offline suite and docs; no receiver access or existing-report overwrite.
Completed: new export template, local KiwiSDR 2 profile label, latest-hearing
selection with record-ID tie break. 689 offline tests pass; compileall/diff checks
pass. Existing reports and reception records unchanged.

## Current slice — report cleanup, station flags and fresh waterfall views

Goals: edit the requested local CLE report (not commit it); persistent Space-toggle
station marker visible in the spreadsheet and frozen as * in new reception notes;
reject queued old-view W/F rows after live recenter/zoom; place selected station ID
beside its carrier label when room permits; receiver mismatch warning and explicit
export confirmation without relabeling evidence. Done: regression fixtures/tests,
full offline suite, docs; no live radio. Report cleanup completed and checked against
57 frozen reception distances; other notes retained.
Completed: persistent flag/new-note inheritance, old-view frame gate with fresh
raster rebuild and pending-target updates, inline ID placement and confirmed mismatch
review export. 688 offline tests, compileall and diff checks passed. No live radio;
same-header receiver FFT settling remains unverified. Personal files are not committed.

## Current slice — focus recovery and slow-render input starvation

Goal: consume terminal focus reports instead of interpreting them as keys; pause
presentation while unfocused, redraw latest history on return, and leave an input
service interval after slow rendering. Audio/acquisition must continue unchanged.
Done: synthetic focus/fragment/escape and slow-render regressions, full offline
suite and docs. No live receiver testing; user reproduction remains necessary.
Completed: raw/terminfo focus handling, presentation pause/latest redraw and slow
render input gaps. 674 offline tests and fixture-only PTY checks passed; compileall
and diff checks passed. Physical terminal behavior still needs user confirmation.

## Current slice — separate nearby browsing from tuning

Goal: comma/period show previous/next nearby candidates without tuning; angle
brackets show and tune previous/next candidates. Preserve fixed-anchor cycling,
filters and component selection. Done: mixed-key/no-tune regressions, help/docs,
full offline suite; no receiver access.
Completed: split keymaps, shown/tuned messages and help/docs. 668 offline tests,
compileall and diff checks passed. No live receiver or user-data changes.

## Current slice — remembered tuning steps and display scale

Goal: checkpoint per-mode main/fine step selection and restore it without implicit
CLI defaults overriding it. Explicit step flags still override; fixtures retain
1/0.1 kHz defaults. Done: offline restart, step-only checkpoint and override tests,
full suite, docs; no receiver access or real user-state writes.
Also restore scale dB endpoints and auto/manual mode; explicit CLI flags override.
Do not checkpoint each automatic adaptation. Validate saved scale and preserve it
through legacy TUI saves. Include scale-key, restore, override and invalid-state tests.
Completed: step and scale persistence/overrides with 663 offline tests passing;
compileall and diff checks passed. No radio connection or real user-state writes.

## Current slice — minimum pointer, remembered zoom/bandwidth, 10 Hz minimum

Goal: use a 9-pixel-wide, 7-pixel-tall tuning pointer only when the full passband
maps to one or two display columns. Keep its existing two-pixel bottom, normal
markers for wider bands, and accurate filter edges. Do not mistake viewport clipping
for a narrow band. Also checkpoint zoom and per-mode passbands in the configured
startup state file, restore with startup.mode=last, and retire 2/5 Hz ladder steps.
Migrate old sub-10 Hz CW startup/recall requests to 10 Hz without rewriting memories.
Done criteria: threshold/edge/geometry and restart/atomic-state tests, docs, full
suite; no live radio or real user-data writes.

Completed: atomic change/exit checkpoints and last-state restoration, read-only
startup planning, 10 Hz minimum/legacy recall handling, and collapsed-only 9×7
pointer. 653 offline tests, compileall and diff checks passed. No receiver access.

## Current slice — frequency marker head and hidden CW reference

Goal: widen current-frequency marker heads by two pixels total (one each side),
keeping tails/heights fixed. Hide the CW receiver-reference mark by default, with
an explicit display-only opt-in; do not change CW offsets or passband geometry.
Completed: pixel/edge/default/CLI regressions and docs. 635 tests pass;
compileall/diff checks pass. Both current and selection heads widen by two pixels;
CW reference is display-only opt-in via --show-cw-offset-marker. No live radio.

## Current slice — compact selected-station tape labels

Goal: show selected station ID once at the tape's left, mark only the carrier with
lowercase c, and format marker frequencies to three decimals. Keep precise RF marker
coordinates/stored tuning unchanged and suppress duplicate selected-station labels
in the catalogue row. Completed: collision/edge/precision/render regressions, docs,
and synthetic preview inspection. 630 tests pass; compileall/diff checks pass.
No live radio or user-state changes.

## Current slice — constant-proportion graphical scale fonts

Goal: size the graphics canvas from terminal cell pixels, resize waterfall history
before compositing labels, and render text/markers at final pixel dimensions. Keep
font proportions consistent at 80 and 174 columns; use a stable metric fallback
when ioctl supplies no pixels. Cover native/fallback geometry, resizing, small
panes, image-cache invalidation and RF marker alignment with offline harnesses.
Completed: native canvas composition, tty metrics/fallback, short-pane handling,
RF/glyph/resize/cache harnesses and docs. 628 tests pass; compileall/diff checks pass.
Offline PTY resize verified PNGs 800×400 / 1740×400 in matching 80×20 / 174×20 cell
placements. Bitmap and FreeType glyph crops are identical across widths/heights.
No radio access or modification of source waterfall samples/user state.

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
