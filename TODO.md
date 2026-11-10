# TODO

## Live/RNA phase — merged 2026-11-10

Goal: deliver the tested live receiver, catalogue and logbook phase to `main`.
Keep experimental recorded-receiver and analysis work on
`feature/ndb-analysis-plan`; do not merge that branch wholesale.

- [x] Preserve branch tips and back up local operational files separately from Git.
- [x] Audit all 16 analysis-only commits and shared runtime changes.
- [x] Port independent live-client fixes with failing-then-passing regressions.
- [x] Consolidate current instructions; archive superseded task/handoff notes.
- [x] Finish full-suite, compile, CLI/browser and terminal smoke validation:
  782 tests passed; real-curses fixture logging and clean wheel installation checked.
- [x] Record final readiness, remaining limitations and migration instructions.
- [x] After explicit approval: fast-forward main in ../kiwi and reconcile local
  files. Config/presets matched; the older saved state was backed up before adopting
  the current live state. Native database copies were logically verified.
- [x] Refresh editable installation and validate in ../kiwi: 782 tests passed,
  launcher/browser/installed CLI dry runs and compilation passed. No radio access.

Done criteria: tested feature commits, clean tracked worktree, documented audit and
migration, no experimental analysis merge, no personal reception data in commits.
The user explicitly approved this merge/migration. Use /home/user/kiwi for new
listening/logging; /home/user/kiwi-rna remains a fallback with unsynchronized data.
Analysis remains on its original branch. Nothing was pushed.

See [merge review](docs/live-phase-merge-review.md),
[current handoff](docs/handoff.md) and [user guide](docs/user-guide.md).

## Next user-facing work (not merge blockers)

- [ ] Attach hearing evidence: audio plus waterfall/frequency/text snapshot tied
  to the same frozen reception record. Keep capture separate from identification.
- [ ] Standalone audited log editing with conflict checks; the current desktop
  logbook is read-only. Do not rewrite historical WWSU/label sources.
- [ ] General RNA submission export and reusable event profiles; only CLE332 has
  a dedicated exporter today.
- [ ] Further refine text layout while preserving existing editable mockups.
- [ ] Investigate jumpy waterfall cadence on 8-channel receivers. The advertised
  zoom-cap blank-view bug is fixed, not proof that cadence issues are resolved.

## Reliability backlog

- [ ] First-message/first-frame/stalled-stream deadlines and explicit diagnostics.
- [ ] Rapid-switch stress coverage, including stalled authentication and socket
  opening/closing. Preserve the earlier unreproduced hang report.
- [ ] Audit bootstrap, network guardrails and cancellation across every frontend.
- [ ] Check ordinary-use persistence and physical-terminal focus behavior; offline
  tests do not establish that all reported terminal/window-manager issues are fixed.
- [ ] Measure acquisition and presentation separately before considering a short,
  bounded playout buffer. Current presentation default is 20 Hz. Do not synthesize
  signal measurements or introduce reconnect loops to mask stalls.
- [ ] Header-based view gating cannot prove underlying FFT-content freshness.

## Deferred analysis direction

The existing experiments remain on `feature/ndb-analysis-plan`, including recorded
USB playback, candidate review, ranking, DSP experiments and report serving. Future
SND/IQ fan-out, recording/detection and long-term integration require their own
fixture-first review; they are not dependencies of this live-client release.

## Historical milestones

Completed slices and their original test counts are retained in
[the archived task log](docs/archive/live-phase-todo-20261110.md) and
[development log](docs/dev-log.md). Archived plans are historical, not current
instructions. User-authored layout examples have not been regenerated or removed.
