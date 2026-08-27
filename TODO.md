# TODO

## Current slice

Goal: Implement exact frequency-step cursor selection as prerequisite 1–2 of the requested cursor/navigation/audio sequence.

Done criteria:

- Replace bin-index cursor state with exact selected frequency plus separate raster-resolution metadata.
- Snap initial and moved selection to a zero-anchored round frequency grid.
- Reuse configured per-mode main/small step pairs; add mode and active pair state to the standalone viewer.
- Map exact selection to the nearest raster column without changing selected frequency.
- Use `h`/`l` and arrows for the main step, `H`/`L` and shifted arrows for the small step, and `t`/`T` to cycle step pairs.
- Report exact cursor frequency, main/small steps, active mode, tuned offset, and bin resolution.
- Add pure model/config/key/status/overlay regressions, run the full harness, and merge `feature/wf-frequency-steps` into `wf1`.

Follow-on branches: W/F recenter/zoom command transport, then coordinated SND audio on/off and tune-to-cursor. `main` remains closed.

Live-radio needed: no for this slice.

Goal: Make `kiwi-wf-terminal` honor configured receiver restrictions and allowlists.

Observed failure: adding `misdr.proxy.kiwisdr.com:8073` under `[receivers].allowed` did not affect the standalone W/F client. Configuration discovery loaded the TOML, but `_capture_config()` omitted `config.receivers.restricted` and `config.receivers.allowed`, so `LiveWaterfallCaptureConfig` silently fell back to its built-in local-only guard values.

Done criteria:

- Add config/CLI harness coverage proving an explicitly configured receiver validates in restricted mode.
- Prove `restricted=false` is also propagated rather than replaced by the capture default.
- Pass receiver policy into both temporary-display and `--save-fixture` W/F capture configurations.
- Keep `--allow-live` as a separate explicit network gate.
- Update user/development docs and merge `fix/wf-receiver-config` into `wf1`; do not touch `main`.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_terminal.py tests/harness/test_config.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no. This is deterministic config propagation and validation; do not connect to the external proxy as part of the fix.

Goal: Prevent cursor input setup from making terminal graphics output nonblocking.

Observed failure: live cursor mode raised `BlockingIOError: [Errno 11] write could not complete without blocking` from the background renderer. `control_waterfall_cursor()` calls `os.set_blocking(input_fd, False)`; when shell stdin/stdout are duplicated from the same terminal open-file description, that changes the shared `O_NONBLOCK` status and makes graphics writes fail with `EAGAIN`.

Done criteria:

- Add a pseudo-terminal regression where input and output descriptors share one open-file description.
- Do not alter terminal descriptor blocking mode; `add_reader()` already invokes reads only when input is ready.
- Preserve cbreak setup/restoration and clean keyboard quit.
- Ensure renderer failures are reported without an uncaught traceback if an output `OSError` occurs for another reason.
- Run targeted and full harnesses, document the finding, and merge `fix/wf-keyboard-blocking` into `wf1` while leaving `main` untouched.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_terminal.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no initially; shared descriptor flags and keyboard restoration are deterministic under a pseudo-terminal. User can retry after merge.

Goal: Add a local waterfall cursor, precise frequency readout, and non-transmitting keyboard navigation.

Done criteria:

- Add a renderer-neutral cursor model mapped to source-bin centers and clamped to the current W/F span.
- Preserve cursor frequency where possible when mapped frame context changes.
- Draw a cursor marker distinguishable from tuned-frequency and passband overlays.
- Show cursor frequency, offset from tuned frequency, and source-bin step in a terminal status row.
- Support `h`/`l` or left/right for one-bin movement, `H`/`L` or shifted arrows for ten bins, `0` to reset to tuned frequency, and `q` for clean exit.
- Keep this slice local-only: cursor movement must not send receiver tuning, zoom, or audio commands.
- Restore terminal input mode on normal exit, transport failure, cancellation, and keyboard quit.
- Add pure cursor, key-decoder, overlay, status-row, config, and fake-live harness coverage before user testing.
- Update user/rendering docs and development log.
- Work on `feature/wf-cursor-readout`; merge the tested slice into `wf1`, not `main`.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_raster.py tests/harness/test_waterfall_terminal.py tests/harness/test_config.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no initially. The user can evaluate keyboard feel in an attended local session after merge to `wf1`.

Goal: Prevent terminal output backpressure from stalling the Kiwi W/F network session.

Observed failure: while the Kitty graphics terminal was unfocused, image updates later jumped through accumulated history and `websockets` closed with `1011 keepalive ping timeout`. The synchronous PNG/terminal write currently runs inside the receive callback, so a blocked terminal can starve WebSocket receive, pong, and application keepalive work.

Done criteria:

- Keep frame parsing/history updates cheap in the network coroutine.
- Move PNG encoding and terminal output off the asyncio event-loop thread.
- Coalesce redraw requests so slow/background terminal rendering cannot create an unbounded image-update queue.
- Disable library-level WebSocket pings for W/F sessions because Kiwi application `SET keepalive` is already used and terminal rendering must not cause a false ping timeout.
- Convert WebSocket connection closure into a concise `LiveCaptureError` instead of an uncaught traceback.
- Add fake-transport regression coverage for connector options, redraw coalescing, full frame ingestion, and clean closure reporting.
- Update operational/failure documentation and development log.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_live_waterfall.py tests/harness/test_waterfall_terminal.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: only after harness success, and only as a short attended focus/background check on a local receiver if the user requests it.

Goal: Add tuned/passband overlays and persistent standalone waterfall defaults.

Done criteria:

- Add renderer-independent mapping from tuned frequency and passband edges to raster columns.
- Draw deterministic, distinguishable marker patterns without mutating protocol frames or history data.
- Omit markers outside the visible mapped span and validate passband ordering.
- Add optional `--tuned-khz`, `--low-cut-hz`, and `--high-cut-hz` viewer controls.
- Add a `[waterfall]` configuration model for center/zoom, history and terminal rows, render range, speed, refresh rate, interpolation, label density, and overlay defaults.
- Preserve explicit CLI arguments over discovered/configured defaults.
- Add synthetic raster and config/CLI harness coverage before live use.
- Update configuration examples, user/rendering docs, roadmap, and development log.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_raster.py tests/harness/test_waterfall_terminal.py tests/harness/test_config.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no initially; overlays and config precedence are deterministic from synthetic/contextualized frames. User can evaluate overlays in the existing live viewer after harness success.

Goal: Add adaptive frequency labels and verify nonzero-zoom mapping on the local receiver.

Done criteria:

- Select major ruler intervals using 1/2/5 × powers-of-ten spacing.
- Adapt label count to terminal width and avoid overlapping labels.
- Derive label decimal precision from the selected interval.
- Preserve edge labels while adding useful interior major frequencies where space permits.
- Keep tick positions deterministic and proportional to the mapped W/F span.
- Add pure policy/render tests for narrow, medium, AM-band, and narrowband spans.
- After the full harness passes, capture a short attended nonzero-zoom fixture from `10.0.0.40:8073` around known AM/WWV/WWVB signals.
- Verify mapped span/bin width and plausible signal positions, then update protocol, rendering, user, roadmap, and development docs.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_terminal.py tests/protocol/test_waterfall.py tests/harness/test_local_wf_capture.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: yes, only after harness success. Planned test: one short guarded local W/F capture from `10.0.0.40:8073`, no reconnect loop or admin commands, centered to include known local AM or time-signal carriers, with fixture output retained for regression.

Goal: Add fixture-backed waterfall frequency mapping and a terminal ruler.

Done criteria:

- Model W/F metadata from `bandwidth`, `wf_fft_size`, `zoom_max`, `zoom`, `start`, `wf_fps`, and `wf_cal` messages.
- Decode frame zoom from the low bits of `flags_x_zoom_server` while masking W/F flags.
- Map `x_bin_server` and zoom to start/end/center frequency and bin width using the Kiwi maximum-bin grid.
- Contextualize parsed frames independently from network and UI code.
- Add a deterministic terminal ruler showing left, center, and right frequencies without reducing the 1024-bin raster width.
- Cover zoom-0 local fixture mapping and synthetic zoomed mapping before any new live capture.
- Update protocol, rendering, user, roadmap, and development docs.

Test command: `.kiwi-venv/bin/python -m pytest tests/protocol/test_waterfall.py tests/harness/test_local_wf_capture.py tests/harness/test_waterfall_terminal.py tests/harness/test_live_waterfall.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no initially; use the existing local zoom-0 fixture and synthetic zoomed frames. A later zoomed local fixture can verify nonzero-zoom receiver behavior.

Goal: Clarify and validate Kiwi waterfall interpolation modes from reference source.

Done criteria:

- Record that `SET interp` is a categorical FFT-to-waterfall-bin reduction mode, not a monotonic smoothing amount.
- Model modes 0..4 as max/min/last/drop/CMA and 10..14 as the same modes with CIC compensation.
- Reject unsupported values 5..9 and values outside 0..14 before connecting.
- Include the decoded method and CIC state in dry-run plans and improve CLI help.
- Add harness/protocol coverage and update protocol, rendering, user, and development docs.

Test command: `.kiwi-venv/bin/python -m pytest tests/protocol/test_waterfall.py tests/harness/test_live_waterfall.py tests/harness/test_live_waterfall_preview.py tests/harness/test_waterfall_terminal.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no; behavior is established by local `~/kiwiclient` and upstream Kiwi server source and command generation is harness-testable.

Goal: Anchor the Kitty image in visible terminal space during live updates.

Done criteria:

- Reserve the configured terminal-row rectangle once before the first image placement.
- Move back to a stable top-left anchor before drawing so `C=1` does not leave the image clipped below the command line.
- Keep subsequent updates at the same anchor without adding more lines.
- Restore the cursor below the image when the viewer finishes.
- Add backend byte-stream tests for reservation, repeated updates, and finish behavior.
- Update renderer docs and development log.

Test command: `.kiwi-venv/bin/python -m pytest tests/harness/test_waterfall_terminal.py && .kiwi-venv/bin/python -m pytest`

Live-radio needed: no initially; terminal layout bytes are deterministic. User can retry after harness validation.

Goal: Stabilize Kitty live rendering after first user visual test.

Done criteria:

- Suppress Kitty protocol acknowledgements so terminal responses are not echoed as visible escape/ANSI text.
- Keep cursor position fixed and reuse a stable image placement so repeated live updates do not introduce blank lines or scroll the terminal.
- Auto-fit default image placement to the current terminal width and half its row height while preserving explicit placement overrides.
- Add pure harness coverage for protocol controls and default placement sizing.
- Update user/rendering docs and the development log.

Test command: `.venv/bin/python -m pytest tests/harness/test_waterfall_terminal.py && .venv/bin/python -m pytest`

Live-radio needed: no initially; protocol bytes and sizing are deterministic. User can retry the existing live command after harness validation.

Goal: Standalone raster waterfall foundation and Kitty terminal viewer.

Done criteria:

- Add a fixed-height, renderer-neutral waterfall history buffer with deterministic orientation and width validation.
- Add deterministic dBm-to-RGB mapping and dependency-free PNG encoding.
- Add a pure, harness-covered Kitty graphics protocol encoder.
- Add fixture-backed `kiwi-wf-terminal` rendering without requiring a graphics-capable terminal in tests.
- Refactor live W/F delivery so raster consumers receive parsed `WaterfallFrame` objects rather than extracting pre-rendered ASCII from status metrics.
- Add guarded live terminal viewing while preserving fixture capture, ASCII preview, and local-radio guardrails.
- Update the roadmap, waterfall docs, user guide, and development log.

Test command: `python3 -m pytest tests/protocol/test_waterfall.py tests/harness/test_waterfall_raster.py tests/harness/test_waterfall_terminal.py tests/harness/test_live_waterfall.py tests/harness/test_live_waterfall_preview.py && python3 -m pytest`

Live-radio needed: no initially; use synthetic and captured fixtures plus fake WebSockets. A short local-only visual test may follow after the full harness passes.

Goal: Waterfall fixture inspection and sequence semantics.

Done criteria:

- Generated static W/F PNG inspection path is usable from a fresh setup.
- `setup-python` installs the development, live, playback, and waterfall image dependencies needed to run the full harness on a new machine with Python already installed.
- Missing waterfall image libraries report a clear remediation command.
- The standalone live ASCII preview prints 50 rows by default.
- The standalone live ASCII preview can adjust local display scale separately from receiver-side W/F min/max dB settings.
- The local W/F fixture `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` is inspected for plausible bin orientation/scaling.
- Repeated local W/F `seq=0` behavior is investigated before sequence tracking treats repeated zero as dropout.
- `docs/kiwi-protocol.md`, `docs/waterfall-rendering.md`, and `docs/dev-log.md` are updated if protocol/rendering conclusions change.

Test command: `python3 -m pytest`

Live-radio needed: not initially; use existing fixtures first. If more W/F frames are needed, perform a short guarded local-only capture after harness tests pass.

Goal: Support sub-Hz Kiwi tuning commands.

Done criteria:

- Add configurable Kiwi modulation command frequency precision.
- Preserve existing 3-decimal default command formatting unless configured otherwise.
- Root config enables 4-decimal command frequency formatting for local sub-Hz step testing.
- Active playback retune commands and live setup plans use configured command precision.
- Harness tests prove a sub-Hz step emits a sub-Hz `SET mod ... freq=` value.
- Update root `config.toml`, user docs, radio parameter docs, Kiwi protocol notes, and dev log.

Test command: `python3 -m pytest tests/protocol/test_commands.py tests/harness/test_config.py tests/harness/test_client_app.py tests/harness/test_tui.py && python3 -m pytest`

Live-radio needed: no; command encoding behavior only.

Docs to update: `docs/user-guide.md`, `docs/radio-parameters.md`, `docs/kiwi-protocol.md`, `docs/dev-log.md`.

## Next

- If temporal jumps become problematic, instrument receive cadence, coalesced redraw count, and draw duration before changing buffering; current behavior resembles the Kiwi browser client.
- Evaluate adaptive ruler density, marker prominence, and persisted operating defaults during normal use.
- Replace bin-sized cursor movement with configured round frequency steps before cursor-driven tuning; map the exact selected frequency to the nearest raster column while reporting bin width only as display resolution.
- Add fixture-tested keyboard recenter and zoom commands around the exact-frequency cursor.
- Decide how the standalone W/F viewer should exchange selected/tuned state with the audio controller before sending SND tuning commands.
- Decide whether to add a native desktop raster backend, integrate a compact image pane into the curses TUI, or retain `kiwi-wf-terminal` as a companion view.

## Later

- Basic desktop client: connect, tune, mode, audio.
- Waterfall decode and rendering.
- Recording pipeline.
- MF/LF beacon detector.
- Long-integration/correlation analysis.
