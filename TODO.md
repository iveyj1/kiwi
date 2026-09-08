# TODO

## Current slice — Console offscreen tuning and screen jumps

Goal: recenter the waterfall when direct frequency entry lands outside the visible range and provide one-screen horizontal frequency movement from vertical/page keys.

Done criteria: fixture-backed helper tests cover in-window entry without recenter, offscreen entry with exact SND tune and W/F recenter, and one-span lower/higher jumps; integrated key handling and user guide are updated; full harness passes.

- Implemented conditional frequency-entry recentering.
- Added Up/Page Up and Down/Page Down one-visible-span tune/recenter controls.

## Current slice — Browser/reference-client compatibility research

Goal: explain the public-receiver reliability gap by comparing browser session setup, bundled kiwiclient tools, KiwiSDR policy/forum guidance, and relevant open-source clients before changing transport behavior.

Done criteria: run reference tools locally before bounded Starlink/public tests; document exact SND/W/F ordering, timestamp, handshake, channel/API policy findings and responsible-use guidance; identify reproducible reference-tool failures versus project failures; survey comparable GitHub projects; propose a harness-first browser-compatible implementation plan without using forum credentials for any mutating action.

- Implemented browser-compatible `/VER` timestamp bootstrap and `/ws/kiwi/<ts>/<stream>` paths with fake-HTTP regression coverage.
- Paired startup now waits for SND `MSG badp=0` before opening W/F; all nonzero `badp` values fail explicitly.
- Increased bounded WebSocket close-handshake time to reduce orphaned allocations; a short local paired validation succeeded. Public rapid-switch/stall validation remains pending first-data diagnostics.

## Current slice — Public receiver directory scrape

Goal: scrape the explicitly authorized KiwiSDR public directory into structured JSON containing URL, name, location, SNR, occupancy, hardware/software, antenna, GPS, band, API capacity, and preserved source metadata.

Done criteria: deterministic parser coverage from synthetic HTML, click-through fetch support without browser automation/passwords, one timestamped local JSON export, receiver/SNR count validation, docs/dev-log update, and full harness pass.

Completed: exported 872 receivers to `data/kiwi-public-receivers-2026-09-07.json`; all 872 include overall/HF SNR and 871 include location. The complete source metadata map is retained per receiver.

## Current slice — Existing TUI lower-panel behavior

Branch: `feature/shared-radio-session`, based on the newly updated `main` integration branch.

Completed and validated:

- Fixed zoom-transition history so every retained/new row remaps from its own captured frequency coordinates instead of the newest row's scale.
- Fixed live tune state being overwritten during legacy/shared status synchronization.
- `f` and selection+Enter now tune without implicit recenter; `c` remains explicit center.
- Added a high-resolution Kiwi-style raster tuning strip so sub-cell indicator movement remains visible.
- Controller-backed `--allow-live --receiver <local>` mode uses one paired SND/W/F worker and bounded snapshots.
- Typed session commands route through a public controller API; shutdown stops and joins the worker.
- Fake-operation coverage includes frame delivery, command routing, failure, null/audio startup, and idempotent cleanup.
- Two bounded local `10.0.0.40:8073` runs displayed actual 5000 kHz W/F data with synchronized running status.
- Automated live screenshot: `docs/screenshots/kiwi-console-live-local.png`.

Completed:

- Made all radio controls safe before the first W/F frame: incremental/direct tune, audio toggle, explicit recenter, and zoom no longer require GUI frequency mapping; automatic edge recenter remains deferred.
- User attended validation confirmed immediate tuning on a local receiver.
- Made simple immediate tuning the integrated-console default: cursor steps tune SND immediately, crossing a visible edge recenters W/F, and live startup centers W/F on startup/restored frequency.
- Added a distinct amber CW receiver-frequency marker at `nominal + cw_offset_hz`; CW compact status now labels both nominal and RX frequencies.
- Divided every graphical frequency-label interval into ten equal intervals with short minor ticks while retaining full-height major stems.
- Enabled curses mouse reporting and explicitly discard integrated-console mouse events, preventing Kitty wheel motion from falling back to repeated volume-mapped up/down arrows.
- Fixed CW graphical passband placement: RF edges now include the configured CW radio-frequency offset while the center/reference marker remains at the user frequency.
- Added shared `m` receive-mode prefix map (`a` AM, `u` USB, `l` LSB, `c` CW) using existing mode/passband/controller routing in both TUI and integrated console.
- Added current system-volume percentage to the compact RSSI/W/F status row; `k`/`j` remain existing configured TUI actions.
- Replaced same-ID Kitty frame updates with two alternating image/placement IDs; user validation at maximum zoom confirmed black flashes are eliminated.
- User confirmed runtime audio toggle continues working across receiver switches.
- Added runtime `a` audio mute/output toggle backed by one shared lazy sink; device state survives receiver restart and failed enable rolls back cleanly.
- Made RSSI numeric/S-unit fields fixed width, corrected units to dBm, and retained the bounded signal-strength bar.
- Detect controller publisher replacement after receiver switch, clear old Kitty history/placement, and bind/display new receiver frames.
- Synchronized `t`/`T` configured step-pair cycling into console selection and exposed current main/fine steps in status.
- Clipped partially visible passbands at viewport boundaries instead of dropping the entire bracket.
- Stopped routine curses refreshes from erasing the Kitty image region; full-screen clearing is now limited to startup/resize to prevent transient black frames.
- Set integrated-console selection defaults to 1.0/0.1 kHz with explicit CLI overrides, independent of local config step-pair ordering.
- Reused existing live TUI key dispatch, command editing/history, contextual hints, preset/store/receiver prefixes, configured non-waterfall actions, and error handling in the lower panel.
- Added runtime manual min/max dB adjustment and percentile-based automatic scaling with bounded cadence, smoothing, padding, and minimum range.
- Replaced the prototype 5x7 scale font with anti-aliased Pillow/FreeType DejaVu Sans Mono; retained deterministic bitmap fallback and explicit backend/font options.
- Composed W/F history, passband/selection strip, frequency ticks/labels, and preset stems/labels into one 1024-bin Kitty image.
- Added deterministic dependency-free 5x7 bitmap text, round major ticks, exact shared frequency columns, and pixel-coordinate collision rejection.
- Removed redundant terminal-cell scale rows and returned that space to curses controls.
- Updated automated Kitty fixture screenshot.

Next goal:

- Continue compact dashboard/status refinement using existing TUI model data; receiver, streams, tuning, steps, mode, audio, RSSI, volume, W/F generation, scale, and persistent messages are now connected.
- Verify preset/receiver persistence and refine audio/volume status; command/history/hints, configurable dispatch, and runtime audio toggle are now integrated for live mode.
- Keep waterfall-specific selection/tune/recenter behavior explicit where it intentionally differs from direct TUI tuning.
- Add pure/fake-operation tests before another attended local session.

## Plan

See `docs/ui-integration-plan.md`.

1. Shared paired-session coordinator.
2. Controller-owned `RadioSessionManager` and typed actions.
3. TUI lifecycle/status integration without embedded graphics first.
4. Native graphical frontend benchmark/prototype.
5. Integrated curses-aware Kitty console (active primary UI direction).
6. One-stream SND consumer fan-out for playback/recording/detection.

## Deferred waterfall questions

- Add first-message/first-frame and stalled-stream deadlines: a Starlink paired sample succeeded fully on 4/10 public receivers, and the same four worked through Verizon hotspot, but repeated switching eventually froze both streams. Further receiver switching did not recover; process restart did. User reconfirmed after browser-compatible bootstrap that switching to an available local receiver still could not recover. Reproduce delayed/stalled worker teardown in the harness and distinguish socket/task startup from actual data flow before adding explicit session recovery. Fixed immediate defect: SND cooperative stop could enter fade-out after prior audio and wait forever when no further frame arrived; a receive timeout now abandons the fade, and paired teardown force-cancels a primary runner that ignores cooperative stop. Unpaired parallel operation consumes separate allocations and is not an acceptable fallback.
- Measure whether zoom-dependent vertical slowdown is receiver cadence or presentation cadence.
- Evaluate a small optional bounded W/F jitter/playout buffer and its smoothness/latency tradeoff.
- Remap retained history across zoom/recenter changes like the KiwiSDR web client, resampling overlap and filling uncovered frequencies with black.

## Validation baseline

- `main` now contains the tested `wf1` integration history.
- Latest full harness before this slice: 289 tests passed.
- `config.toml` remains intentionally unchanged.
