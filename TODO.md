# TODO

## Current slice — Native GUI benchmark harness

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed in this branch:

- Added shared paired coordinator, typed session/controller/TUI lifecycle, and headless `radio-bg` operation.
- Added bounded immutable `WaterfallSnapshotPublisher` with per-row original frequency mapping and monotonic arrival time.
- Paired live sessions can publish frames into the controller-owned snapshot boundary.
- Slow consumers coalesce onto the latest generation without queued snapshot growth.
- Added `docs/native-gui-benchmark.md`; no GUI dependency has been selected.

Next goal: implement the toolkit-independent fixture workload and result reporting used by native GUI candidates.

Done criteria:

- Generate/replay deterministic 1024-bin snapshots at configurable history depth and source rate.
- Provide common timing/drop/coalescing/result metrics without importing a GUI toolkit.
- Add a no-window baseline consumer for 200/400/800-row workloads.
- Keep benchmark code outside production transport/session paths.
- Do not add a GUI dependency yet.

## Plan

See `docs/ui-integration-plan.md`.

1. Shared paired-session coordinator.
2. Controller-owned `RadioSessionManager` and typed actions.
3. TUI lifecycle/status integration without embedded graphics first.
4. Native graphical frontend benchmark/prototype.
5. Optional curses-aware Kitty pane if still valuable.
6. One-stream SND consumer fan-out for playback/recording/detection.

## Deferred waterfall questions

- Measure whether zoom-dependent vertical slowdown is receiver cadence or presentation cadence.
- Evaluate a small optional bounded W/F jitter/playout buffer and its smoothness/latency tradeoff.
- Remap retained history across zoom/recenter changes like the KiwiSDR web client, resampling overlap and filling uncovered frequencies with black.

## Validation baseline

- `main` now contains the tested `wf1` integration history.
- Latest full harness before this slice: 289 tests passed.
- `config.toml` remains intentionally unchanged.
