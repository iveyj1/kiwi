# Live/RNA phase merge review — 2026-11-10

**Update:** user-approved merge and migration completed later the same day; see
[execution record](#approved-merge-and-migration). The preparation findings below
are retained as the audit trail.

## Decision and scope

Prepare `feature/rna-live-logging` for `main`; retain
`feature/ndb-analysis-plan` separately. Do not merge experimental recorded playback,
DSP, ranked practice/review, or report-serving workflows into this phase. This
review did not merge main, switch ../kiwi, push/fetch remote refs, or access receivers.

At review start:

| Reference/worktree | Tip | Status |
|---|---|---|
| `feature/rna-live-logging` / `../kiwi-rna` | `9b0251b` | No tracked edits; personal untracked files |
| `feature/ndb-analysis-plan` / `../kiwi` | `9e1c96f` | No tracked edits; local cle/ and screenshot |
| local `main` | `1ab69bd` | Ancestor of live branch; fast-forward is possible |
| Common feature-branch ancestor | `05698f6` | 2026-09-21 pre-analysis baseline |

The analysis branch has 16 unique commits, all dated September 21; the live branch
started September 25 from the earlier baseline. These are mostly experiments
excluded deliberately, not later fixes that must all be integrated.

## Analysis-branch audit

Reviewed the unique-commit file changes and complete differences in all shared
runtime modules: gui_app, integrated_terminal, playback, recorder,
waterfall_levels and waterfall_snapshots. Additions confined to new analysis or
recorded modules were assessed for scope, not requalified as production DSP.
The parked branch's complete suite was not rerun.

| Commit | Work | Disposition |
|---|---|---|
| baef85e | Analysis/PSKOV checkpoint, reports, recorder sample/rate metrics | Keep separate. Recorder fields support analysis but do not correct existing live behavior. |
| 863d4a3 | Local report hub | Keep separate. |
| 50d28d2 | Early CLE rules/old seeklist exclusion | Historical planning; current live branch has later event-specific rules. |
| c7d49e6 | Recorded-receiver/acquisition plan | Keep separate. |
| 9a8d241 | Bounded offline USB receiver/DSP core | Keep separate. |
| 16ae867 | Recorded audio/waterfall UI | Keep separate. |
| 78a13b5 | Recorded geometry and shared display controls | Port generation-reset handling in automatic levels only. Recorded geometry and controller refactoring are not needed. |
| 50513cd | Recorded source-time spectra, buffered rows, sink underflow count | Keep separate. The source-time scheduling fix is recorded-specific; sink telemetry has no live consumer here. |
| fbd3b4d | Recorded device pacing/latency headroom | Keep separate. Live playback does not use that recorded pacing loop. |
| c0d66b1 | Candidate review/bookmarks/human decisions | Keep separate. |
| 20d1a9b | Candidate index/per-observation status | Keep separate. |
| fbfd98c | Keyboard candidate table | Keep separate; this branch has its own catalogue spreadsheet. |
| 69a4337 | Ranked RNA practice queues/frozen later checks | Keep separate. |
| 72053b8 | Inactive screening/original review-frequency restoration | Recorded-review-specific; live catalogue filtering already has separate coverage. |
| 2b50a81 | Opt-in shared recorded console and raster changes | Port bounded padding cache/geometry invalidation, guarded tuning actions and finally-protected presenter cleanup. Exclude recorded APIs, numeric reduction, missing-row semantics and image-state machinery. |
| 9e1c96f | Shared sectioned text panels | Do not import a competing panel system; live branch's boxed spreadsheet/editors/popup remain. |

No whole analysis commit was cherry-picked. The small independent ports are in
`d45591b`; no recorded/analysis entry points or dependencies were added.

## Independent fixes and evidence

Six regressions in `test_merge_review_fixes.py` failed against the original live
code, then passed after the ports:

1. Keep only the current raster padding size. Previously every size accumulated
   while history filled: worst-case roughly 234 MiB of padding alone at 1024×400.
2. Clear padding on a geometry rebuild, avoiding wrong-width RGB buffers.
3. Restart automatic-level cadence when a new publisher's generation drops below
   the previous update count. Do not wait for the old receiver's count to catch up.
4. Report invalid negative-frequency tuning in MESSAGE instead of exiting.
5. Report failed view actions without exiting the input loop.
6. Finish terminal presentation and checkpoint settings even if source stop raises.

The live branch's fresh-view gate, zoom-cap handling, native scale geometry,
current keymap and reception provenance remain intact. This is not a claim that
all timing, terminal or transport issues are solved.

## Cleanup

- Added README with installation, current general-listening controls and offline checks.
- Replaced stale handoff instructions (old branch, 5 Hz cadence, old keys).
- Condensed TODO to current release work and a distinct backlog. Original task and
  handoff notes are preserved under docs/archive/; editable layout mockups remain.
- Added narrowly scoped ignores for private sites, launchers, personal reports and
  screenshots. Ignoring a file does not delete or back it up.
- Declared the setuptools build backend explicitly. Initial no-build-isolation
  wheel attempt failed because the shared venv has no setuptools; a subsequent
  isolated build succeeded without installing anything into that shared venv.

## Validation

- Baseline: **776 passed**; after six regressions/fixes: **782 passed**.
- Fixture dry run from an isolated cwd: valid JSON, no reception database created.
- Real-curses offline PTY: catalogue search/tune, inline tentative general log,
  continuing Kitty graphics during entry, Enter save and clean q exit. Exactly one
  RJ/fixture/tentative record with no event tag, confined to a temporary database.
- Root logbook launcher from another cwd: reads that synthetic record, no errors.
- Built wheel using isolated setuptools; installed with `--no-index --no-deps`
  in a fresh temporary venv. Installed `kiwi-console` fixture dry run and
  `kiwi-logbook --native-only --dry-run` both passed with PYTHONPATH unset.
- Qt browser interaction/quit/read-only coverage is included in the full suite.
- Source compilation and diff checks passed; final full suite: **782 passed**.
- Rechecked local main/analysis tips: unchanged; main remains an ancestor of the
  prepared live branch. No tracked changes were made in ../kiwi.

Temporary evidence: `/tmp/kiwi-merge-smoke-wubmopb_`,
`/tmp/kiwi-live-phase-wheels`, `/tmp/kiwi-wheel-smoke-5YzwJA`.
No new live test was needed; prior bounded live zoom-cap verification remains in
[protocol notes](kiwi-protocol.md). The current validation environment uses the
absolute shared `/home/user/kiwi/.kiwi-venv/bin/python`; a Python 3.11 matrix was
not run, despite the package's declared minimum version.

## Safety copies

Git safety references (all created before preparation edits):

- `backup/live-phase-20261110` → `9b0251b`
- `backup/analysis-phase-20261110` → `9e1c96f`
- `backup/main-before-live-phase-20261110` → `1ab69bd`

Operational backup:
`~/.local/share/kiwi-client/backups/live-phase-20261110-kevr7vhg/manifest.json`.
It records 25 files with source paths, backup paths, hashes and copy methods.
SQLite files were copied through the online backup API and passed quick_check;
ordinary files were verified by source/destination SHA256. It includes local
operational settings/scripts/reports, native reception data, historical stages,
label source and the other worktree's cle material/screenshot where present.

This is **not** a full archive of recordings, artifacts, virtualenvs or external
WWSU backups. Those remain untouched in their original locations. The operational
backup is a point-in-time safety copy, not the source of truth for subsequent
listening; take a fresh backup before actual migration.

## Merge/migration checklist — executed after subsequent approval

1. Obtain explicit merge approval; confirm no new tracked edits or branch divergence.
   Remote refs have not been refreshed; review them before any push.
2. Stop relevant applications before reconciling operational state and make fresh
   SQLite/API and ordinary-file backups. Keep the analysis branch and safety refs.
3. Confirm `main` is still an ancestor of the prepared feature tip. Fast-forward
   main rather than merging the excluded analysis branch. Do not force/reset main
   if it has moved; review intervening changes instead.
4. Switch ../kiwi from the analysis branch to main only after checking its working
   tree and local-file collisions. Do not delete its untracked cle/ or screenshot.
5. Reconcile, **without blind overwrites**, the live worktree's operational files:
   receptions.sqlite, rna-sites.toml, rna-filters.json, rna-stations.json, state.json,
   local report profile, historical stage JSON and original label evidence.
   Compare ../kiwi's config.toml/presets.toml/state.json before choosing settings.
   Catalogue source and code are already tracked; do not merge historical sources
   into the native database or rewrite frozen evidence.
6. Review personal launchers: cle-listen hard-codes /home/user/kiwi-rna and still
   tags CLE332; rna-listen uses relative paths and depends on cwd. Prefer the README
   general-listening command from ../kiwi. Inspect cle-log-preview before moving it.
   Do not silently change their receiver/event semantics.
7. Refresh editable package metadata in the chosen environment. Avoid stale build
   artifacts from the analysis checkout when producing distributions. Existing
   analysis-only installed commands are not part of this release.
8. Repeat offline smoke checks in ../kiwi; then user-authorized normal listening
   and logbook inspection. Keep ../kiwi-rna as fallback until operation is verified.
   Do not remove either worktree or delete the analysis branch as part of preparation.

## Approved merge and migration

On 2026-11-10 the user approved execution. No running receiver/browser processes
were found. Local main was still at 1ab69bd and remained an ancestor of fac8a94.
Switched /home/user/kiwi from the analysis branch to main and fast-forwarded to the
prepared live phase, followed by a feature-branch documentation checkpoint. No
analysis merge, force/reset, worktree deletion or remote push was performed.

Fresh safety copy before migration:
`~/.local/share/kiwi-client/backups/live-phase-20261110-bqhof4f5/`.
The manifest records 25 backed-up files; migration.json records 16 reconciled
operational files. Native SQLite copies passed quick_check and complete logical
dump comparison. Config and presets were identical, so retained. The older
../kiwi saved state was preserved in the backup before adopting current live
state, including zoom/passbands/display levels. Historical stage/source bytes and
frozen evidence were not rewritten or combined.

The target copies of rna-listen, cle-listen and cle-log-preview now resolve paths
relative to their own directory and forward command-line arguments. Existing
receiver/event choices were preserved. Their final hashes are recorded in
launcher-adjustments.json; original fallback scripts are unchanged. Added a
specific ignore for the existing pskov/ archive exposed by leaving the analysis
branch, without importing or deleting that archive.

Refreshed editable installation in /home/user/kiwi/.kiwi-venv using the primary
worktree. Confirmed imports resolve to /home/user/kiwi/src and installed metadata
contains no recorded/analysis entry points. Validation in the primary worktree:
**782 tests passed**, compileall/diff checks passed, migrated general-listening
launcher dry run from /tmp passed with network=false, installed fixture CLI dry
run passed with PYTHONPATH unset, and the logbook loaded all three migrated source
families without errors. Shell syntax checks passed. Native databases were still
logically identical afterward; fallback originals and unrelated target operational
files matched the fresh backup hashes. No receiver connection was made.

Use /home/user/kiwi for subsequent listening and logging. The retained
/home/user/kiwi-rna data is a fallback snapshot, **not synchronized**. Keep it until
normal operation is verified; do not alternate between the two native logbooks.
The analysis branch remains at 9e1c96f with its safety ref intact. Remote refs were
not refreshed and nothing was pushed.

## Remaining limitations

Evidence recording/snapshots, audited standalone editing and general RNA submission
export are future work. Stream deadlines, rapid-switch stress, physical-terminal
behavior and jumpy waterfall cadence remain open. Latest confirmed CLE export is
retained, but CLE332 rules are not a general event framework. See [TODO](../TODO.md).
