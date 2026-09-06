# Dev Log

Use this as lightweight project memory. Record facts that future agent sessions should not rediscover.

## 2026-06-13

### Finding

`kiwiclient/kiwi/client.py` decodes SND WebSocket payloads as a 3-byte `SND` tag followed by `flags:u8`, `seq:u32le`, `smeter:u16be`, then audio data. Non-camping, uncompressed mono audio is signed 16-bit big-endian PCM. RSSI is `0.1 * smeter - 127`.

### Decision

First harness tests use `tests/fixtures/kiwi/snd-basic.jsonl`, a synthetic uncompressed mono SND frame, before any live receiver connection. Compressed ADPCM and stereo/IQ fixtures are explicitly follow-on work.

Waterfall rendering may start as a separate lightweight view/process from any TUI if that keeps the early TUI focused on controls/status.

### Test result

`python3 -m pytest tests/harness tests/protocol` passed: 5 tests.

Added minimal `MSG` parsing and receiver state context. `tests/fixtures/kiwi/snd-session-basic.jsonl` now covers synthetic `audio_rate`, `sample_rate`, version, and bandwidth `MSG` events followed by one uncompressed mono SND frame. `ReceiverState` tracks those values separately from audio frame parsing.

`python3 -m pytest` passed: 10 tests.

Added fixture-tested command encoders for the first non-admin SND setup path: auth, identity, mode/frequency/passband, AGC, compression off, and keepalive. `tests/fixtures/kiwi/snd-setup-commands.jsonl` records the expected command sequence.

Documented the first short SND live-to-fixture capture plan in `docs/harness.md`, but did not run it.

`python3 -m pytest tests/harness tests/protocol` passed: 15 tests.

Committed as `dc44b44` (`Add fixture-tested SND command encoders`).

Added offline JSONL capture writer shape in `src/kiwi_client/capture.py`. It records SND capture metadata, tx commands, rx MSG events, and rx binary WebSocket payloads. `tests/harness/test_capture_writer.py` round-trips a synthetic capture through the fixture loader, MSG parser, receiver state, and SND parser.

`python3 -m pytest tests/harness tests/protocol` passed: 16 tests.

### Follow-up

Committed as `68770f5` (`Add offline SND capture fixture writer`).

Added strict offline `ReplayTransport` in `src/kiwi_client/transport.py`. It consumes fixture events in order, validates transmitted commands, and returns received MSG/binary events. `tests/harness/test_replay_transport.py` covers successful setup/session replay and command mismatch failure.

`python3 -m pytest tests/harness tests/protocol` passed: 18 tests.

Next useful slice: add the first guarded live capture command-line tool while leaving actual execution for a separate explicit live-radio-test step, or add more parser coverage for sequence/dropout handling before live capture.

Added audio-layer SND sequence/dropout handling. `SndSequenceTracker` detects missing frames, out-of-order frames, and uint32 wraparound. `tests/fixtures/kiwi/snd-sequence-gap.jsonl` covers frames `1, 3, 4` with one missing frame at expected sequence `2`. ADC overflow flag exposure is covered in audio tests.

`python3 -m pytest` passed: 22 tests.

Committed as `1491c70` (`Add SND sequence gap tracking`).

Added guarded SND live capture module/CLI in `src/kiwi_client/live_capture.py`. It supports dry-run without network, validates the local receiver allowlist, caps duration/frame count, refuses overwrites by default, requires `--allow-live` for actual network use, and writes JSONL via the existing capture writer. Actual live execution was not run.

Dry-run command verified with no network: `PYTHONPATH=src python3 -m kiwi_client.live_capture --dry-run --host 10.0.0.40 --output /tmp/kiwi-dry-run.jsonl --timestamp 123456`.

`python3 -m pytest` passed: 28 tests.

Live local SND capture requested and run against `10.0.0.40:8073` at 5000 kHz AM, filter `-5000..5000` Hz. First attempt connected but showed that live Kiwi MSG frames can arrive as binary WebSocket payloads with `MSG` tag; tool classified them as binary and got no SND frames. Updated the capture flow to classify binary MSG payloads, wait for `audio_rate`, send `SET AR OK in=12000 out=44100`, then send squelch/gen/identity/mod/AGC/compression/keepalive setup.

Second guarded capture succeeded and wrote `tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl`: 22 MSG events, 20 SND frames, seq `1..20`, 512 samples/frame, no parse errors, no sequence gaps. Receiver state was `sample_rate=11998.94054`, `audio_rate=12000`, version `1.842`, bandwidth `30000000` Hz. Added regression coverage in `tests/harness/test_local_snd_capture.py`.

Added offline fixture-to-WAV recording in `src/kiwi_client/recorder.py`. The first recording path writes uncompressed mono SND fixture samples as standard 16-bit PCM WAV, rounding the fixture `sample_rate` to integer Hz for the WAV header. `tests/audio/test_wav_recorder.py` validates the local 5000 kHz fixture produces 20 SND frames, 10240 WAV frames, 11999 Hz, mono, 16-bit, with zero sequence gaps.

Committed as `d73615e` (`Add fixture WAV recording`).

Added a user-facing fixture-to-WAV CLI via `python3 -m kiwi_client.recorder` and project script `kiwi-fixture-to-wav`. The CLI supports `--json` summary output and was used to refresh `recordings/local-snd-5000-am-10khz.wav` from the live radio fixture. Generated recordings remain ignored by git.

Committed as `c31d4ce` (`Add fixture to WAV recorder CLI`).

Added `docs/roadmap.md` as the high-level milestone tracker. It records completed SND harness, guarded local capture, and offline WAV recording milestones, and identifies direct live-to-WAV recording as the recommended next milestone. `docs/project-brief.md` now links to the roadmap. Roadmap maintenance rule: update it whenever milestone status, ordering, protocol behavior, or major risks change.

Committed as `b1ff2af` (`Add project roadmap`).

Advanced Milestone 4 direct live-to-WAV recording: added `src/kiwi_client/live_record.py` with replay-tested direct SND-to-WAV session logic and a guarded live CLI requiring `--allow-live`. Replay coverage uses the local 5000 kHz fixture and validates WAV output without network access.

Started Milestone 5 playback: added `src/kiwi_client/playback.py` with an `AudioSink` interface, `NullAudioSink`, WAV chunk reader, and dry-run CLI. Real audio-device output remains pending.

Dry-runs verified:

- `PYTHONPATH=src python3 -m kiwi_client.live_record --dry-run ...`
- `PYTHONPATH=src python3 -m kiwi_client.playback recordings/local-snd-5000-am-10khz.wav --dry-run --json`

Ran one guarded direct live-to-WAV recording against `10.0.0.40:8073`, 5000 kHz AM, filter `-5000..5000` Hz. Output `recordings/live-snd-5000-am-10khz.wav` was mono 16-bit PCM, 11999 Hz, 10240 frames, 20 SND frames, zero sequence gaps. Generated WAV is ignored by git.

Committed as `22facb5` (`Advance direct recording and playback milestones`).

Implemented guarded live SND playback in `src/kiwi_client/live_play.py`. Added `SoundDeviceSink` to `playback.py` using optional `sounddevice`, plus replay/null-sink tests. Installed `sounddevice` locally and confirmed default output device exists. Ran live playback first with `--null-sink` and then real audio output against `10.0.0.40:8073`, 5000 kHz AM, filter `-5000..5000` Hz. Both runs processed 60 SND frames, 30720 audio frames, 61440 bytes, sample rate 11999 Hz; real run reported `dry_run=false`.

Committed as `9c47013` (`Add guarded live SND playback`).

Started Milestone 6 with `src/kiwi_client/client_app.py`, a scriptable control shell that keeps app state separate from protocol/transport/audio layers. It supports status, connect/disconnect state, receiver, tune, mode/filter, and dry-run plans for play/record/capture. `kiwi-client` project script added.

Committed as `1c8f47e` (`Add basic scriptable client shell`).

Extended the client shell with executable guarded `play`, `record`, and `capture` commands. These require explicit `--allow-live` and reuse the existing guarded live operation modules; tests inject fake operations so command behavior is covered without receiver/audio access. `play --null-sink`, `record --overwrite`, and `capture --overwrite` are supported.

Committed as `58336e2` (`Execute guarded operations from client shell`).

Reduced live operation teardown latency by setting a short WebSocket close timeout for SND capture/record/play and by stopping the audio sink before closing the playback WebSocket. Timing checks at 5000 kHz AM, 60 frames: null-sink returned in about 2.9s and real sounddevice output in about 3.4s.

Committed as `261703a` (`Reduce live audio teardown latency`).

Raised explicit live play/record/capture guardrail caps to 60 seconds and 1500 SND frames. Defaults remain short, so longer live sessions require the user to pass `--duration-seconds` and `--max-frames` explicitly.

Committed as `9b04c00` (`Allow one minute guarded live sessions`).

Started persistent live-mode settings and TUI work for Milestone 6. `ClientState` now carries `duration_seconds` and `max_frames`; `duration` and `frames` commands persist those settings across play/record/capture plans and executions. Added `dashboard` command plus `src/kiwi_client/tui.py`, a pure text dashboard renderer with a thin curses runner. Entry points: `PYTHONPATH=src python3 -m kiwi_client.client_app --tui` and `PYTHONPATH=src python3 -m kiwi_client.tui` / `kiwi-tui`.

Committed as `94f69b4` (`Add TUI dashboard and persistent live settings`). Follow-up fix `115350a` added the missing `python -m kiwi_client.tui` entrypoint.

Added `src/kiwi_client/live_worker.py`, a framework-neutral background operation worker. Client shell now supports `play-bg --allow-live [--null-sink]`, `stop`, and `operation-status`. Live playback accepts a cooperative `stop_event`, and the TUI dashboard displays background operation state.

Committed as `b660770` (`Add background playback worker for TUI`).

Added a command queue to background operations and wired live playback to drain queued control commands after initial SND setup. `tune`, `mode`, and `filter` now queue `SET mod=...` to active background playback and include `active_command` in the response/dashboard. Harness tests cover command queuing without receiver access.

Added `wait [seconds]` to the client shell for scripts/TUI to wait for background operation completion/status. A short local null-sink script verified the background playback queue path: start at 5000 kHz AM, queue `tune 7000`, wait, stop, and wait for completion. The operation processed 18 SND frames and stopped cleanly.

Added live operation metrics to `BackgroundOperation` status and wired playback/record/capture SND frame paths to publish latest `rssi_db`, raw `smeter`, `snd_seq`, and frame count where available. Added `record-bg <output.wav> --allow-live [--overwrite]` and `capture-bg <output.jsonl> --allow-live [--overwrite]`, both using cooperative stop. The TUI dashboard now displays a simple latest RSSI/S-meter and SND frame count when metrics are present. Harness coverage validates background record/capture commands and dashboard rendering without receiver access.

Extended SND status metrics to include rounded sample rate, sequence gap count, and ADC overflow count. Playback uses `SndMetricsTracker`; recording exposes `SndWavRecorder.status_metrics()`; capture uses the same metrics tracker. The curses TUI now sets a 250 ms input timeout and redraws on timeout, so RSSI/status/error updates appear without keyboard input. Harness tests cover metric fields and the periodic timeout behavior.

Added client command aliases for interactive use: `?` for status, `re`, `tu`, `mo`, `fi`, `du`, `fr`, `pb`, `rb`, `cb`, `sp`, `he`, `q`, and `qu`.

Added a two-mode TUI input model. The TUI starts in keymap mode, `:` enters command mode, `Enter` executes and exits command mode, `Esc` clears/exits command mode, and up/down in command mode browse command history for editing.

Added TOML configuration loading in `src/kiwi_client/config.py`. Defaults include small/medium/large frequency steps, volume step percent, and keymap actions. The TUI accepts `--config <path>` to overlay defaults.

Added controller commands `tune-step`, `volume`, and `volume-step`. TUI keymap mode now executes configured key actions, expanding named frequency steps using the loaded TOML step sizes. Volume is currently client state/display only; applying gain to live PCM remains future work.

Added `[live] allow_live = false` to the TOML config schema. When a TUI config explicitly sets `allow_live = true`, controller live-operation guard checks accept commands like `:pb --null-sink` without requiring `--allow-live` each time. The default remains guarded.

Hardened TUI key handling for modified arrow escape sequences. Known curses shift-left/shift-right codes map to configured `shift-left`/`shift-right`; unknown modified-key/escape inputs are ignored in keymap mode instead of exiting or becoming bogus control-key names. Added TOML live limit settings (`duration_seconds`, `max_frames`, `0` = unlimited) and receiver policy settings (`[receivers] restricted`, `allowed`). TUI-created controllers now apply configured live limits and receiver policy to play/record/capture configs.

Added periodic live SND keepalives for playback, recording, and capture loops. The initial setup still sends `SET keepalive`, and long-running sessions now send another keepalive after the configured interval once setup has completed. This addresses receiver-side disconnects around the one-minute mark when client duration/frame limits are unlimited.

Added interactive AGC controls backed by locally verified `SET agc=...` behavior from `kiwiclient/kiwi/client.py`. Commands cover AGC on/off, hang, threshold, slope, decay, manual gain, and key=value batch updates. AGC changes queue to active background playback. No verified Kiwi radio-side volume command was found in local reference code.

Changed `volume` / `volume-step` to control local system output volume via an injectable backend. The default backend tries `wpctl`, then `pactl`, then `amixer`; harness tests use a fake backend and do not touch the system mixer.

Fixed TUI quit behavior while background playback is active. Keymap `q` and command-mode `quit`/`q`/`qu`/`exit` now request cooperative background stop and wait briefly before ending curses. If the worker does not stop quickly, the TUI stays open and reports that shutdown is in progress.

Changed `volume-step` to read the current local system output volume before applying the configured delta. Added preset commands `store <n>`, `store all <n>`, and `recall <n>`, plus TUI keymap preset sequences. The TUI now persists last full state and presets to a JSON state file on safe exit and can start from `[startup] mode = "last"`, `"default"`, or `"preset"`.

Fixed another cooperative shutdown issue for long/unlimited live sessions. Live play/record/capture receive loops now use a short poll timeout around WebSocket receive, so `stop`/TUI `q` can be observed promptly even when `duration_seconds = 0` and no receive timeout would otherwise be active.

Fixed connected status reporting for live background operations: `status` and the TUI dashboard now treat an active background live worker as connected. Added Kiwi MSG error detection for `too_busy`, `badp=1`, and `down`, surfacing explicit server busy/down messages in operation errors.

Added semicolon-separated command batches for the shell and TUI command mode. Semicolons inside quoted arguments are preserved. Radio/state-only batches are validated against a temporary controller before committing changes, so invalid later commands do not partially mutate state. When background playback is active, an atomic radio batch queues final active-stream `SET mod=...` and/or `SET agc=...` commands only after validation succeeds. Mixed batches with live worker operations remain sequential and stop on first error.

Fixed TUI startup restore for `[startup] mode = "last"`. `startup_state_and_presets()` restored the persisted state correctly, but `run_tui()` reapplied `[default_state]` before curses started and wiped out the restored radio state. `run_tui()` now applies only runtime settings at that stage, preserving restored last/preset radio values.

Added which-key style TUI hints. Keymap mode shows configured keys with short action descriptions. Command mode shows command names, aliases, and descriptions; typed text filters rejected commands, unique matches show usage/sub-options, and semicolon-separated command entries use the current segment for context.

Updated normal-mode key hints and key behavior to the register-prefix model. Presets now use `p <register>` to recall, `s <register>` to store frequency/mode/bandwidth, and `S <register>` to store all radio parameters, with registers `0..9,a..z`. Added `r <receiver-register>` to switch to a receiver from `[receivers].allowed` by register order while preserving current radio parameters. Letter preset registers are persisted alongside numeric registers.

Improved pending-register normal-mode hints. After `p`, `s`, or `S`, defined preset registers show saved frequency and mode. After `r`, receiver registers show configured receiver addresses from `[receivers].allowed`.

Fixed receiver register switching during active playback. `r <receiver-register>` now reports the selected receiver explicitly; if background playback is running, the TUI stops it and restarts playback on the new receiver with the current radio parameters. If playback had already failed, `r <receiver-register>` now switches receiver and starts playback instead of only changing state and leaving the stale operation error visible. If the new playback fails immediately, e.g. because the receiver is busy, the TUI restores the previous receiver, restarts playback there when possible, and displays the failure message.

Added `add-receiver <receiver-register> <ip/url[:port]> <description>` with alias `ad`. Stored receiver registers are normalized to `host:port`, persisted in the TUI state file, shown in `r` pending-register hints with address/description, and take precedence over fallback receivers from `[receivers].allowed`.

Added `[startup] playback = true|false`. The project root config enables it so local TUI startup begins background playback automatically when `[live].allow_live = true`; built-in defaults remain guarded with startup playback disabled.

Added `[audio] startup_mute_ms` and defaulted it to 300 ms in the built-in config. Live/replay SND playback still observes startup SND frames for metrics, but drops the configured amount of decoded PCM before writing to the sink to reduce receiver/audio startup transients. Recorded bumpless transfer options in `docs/bumpless-transfer.md`.

Added `[audio] startup_fade_in_ms` and `[audio] stop_fade_out_ms`, with the local root config tuned to 100 ms startup mute, 50 ms fade-in, and 50 ms fade-out. Playback now applies a linear sample-domain fade-in after startup mute/drop and a short fade-out on cooperative live stops when frames are still arriving.

Documented the receiver/playback lifecycle architecture in `docs/radio-session-state.md`. The busy-receiver recovery issue showed that desired receiver, active stream, playback intent, background operation status, and stale errors need an explicit controller-owned session model rather than TUI helpers inferring state from raw worker status.

Added controller-owned `RadioSessionState` and `ClientController.switch_receiver()`. Receiver-register switching now delegates lifecycle policy to the controller, which handles idle receiver changes, active playback restart, failed-playback recovery, and immediate busy rollback while exposing session snapshots in status/operation responses.

Drafted `docs/waterfall-spec.md` for the W/F display path. The plan starts with synthetic W/F fixtures, uncompressed parser tests, a deterministic `WaterfallFrame` model, and an offline ASCII/terminal renderer before local live W/F capture or TUI integration. Updated roadmap, rendering notes, architecture notes, and protocol notes with reference-backed but not-yet-fixture-verified W/F facts.

Added the first synthetic waterfall fixture, `tests/fixtures/kiwi/wf-basic.jsonl`, plus `src/kiwi_client/waterfall.py` with `WaterfallFrame`, `parse_waterfall_uncompressed()`, and raw byte to uncalibrated dBm conversion. Protocol tests now cover W/F tag/header/bin parsing and malformed frame errors without live radio.

Added `src/kiwi_client/waterfall_render.py` with deterministic fixed-scale dBm-to-ramp mapping and ASCII row rendering for one `WaterfallFrame`. Harness tests render the synthetic W/F fixture with clamp behavior, keeping the renderer independent from curses, sounddevice, and live radio.

Added offline fixture-to-text preview command `python3 -m kiwi_client.waterfall_preview` / `kiwi-wf-preview`. It renders W/F binary events from JSONL fixtures as deterministic ASCII waterfall rows without network access.

Added `WaterfallSequenceTracker` for W/F sequence continuity. Tests cover in-order frames, missing-frame gaps, out-of-order frames, and uint32 wraparound.

Added guarded W/F live capture module `python3 -m kiwi_client.live_waterfall` / `kiwi-wf-capture`. Harness tests use an injected fake websocket to verify dry-run plans, guardrails, command sequence, W/F JSONL writing, parsing, sequence metrics, and ASCII row metrics without network access.

Attempted short local W/F capture after harness coverage: `10.0.0.40:8073` returned repeated `MSG redirect=...` to a non-local proxy, so the client did not follow it; `10.0.0.41:8073` reported all four client slots busy. Added `MSG redirect` as a user-facing terminal server response so future capture attempts fail fast instead of collecting redirect chatter.

Added standalone guarded live W/F ASCII preview `python3 -m kiwi_client.live_waterfall_preview` / `kiwi-wf-live`. It reuses guarded W/F capture and prints ASCII rows from status callbacks; tests use a fake websocket and do not require live radio.

Retried short local W/F capture on `10.0.0.40:8073` at 2026-06-16 01:50 UTC / 2026-06-15 21:50 local, center 5000 kHz, zoom 0, speed 1, `wf_comp=0`, max 2 frames. Capture succeeded and produced `tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl` with two 1024-bin W/F frames. Both frames decoded with `raw_flags=32`, `x_bin_server=0`, `flags_x_zoom_server=0`, and repeated `seq=0`; sequence semantics need follow-up before treating repeated zero sequence as a real dropout.

Added non-production test-rig helper `tools/waterfall_image.py` to render static PNG images from W/F fixtures using optional matplotlib. It keeps PNG/image experimentation outside production package entrypoints; tests cover the pure fixture-to-dBm-matrix path. Generated local inspection artifact `artifacts/local-wf-5000-zoom0.png` from the real local W/F fixture.

Reorganized TUI command-mode hints into categories similar to keymap hints. Command aliases/shortcuts are now displayed before full command names, e.g. `tu (tune)`, while preserving filtering, unique-command usage hints, and semicolon current-segment context. Key and command hint overviews now use two columns so they consume less vertical space and leave more dashboard/status visible.

Fixed stored numeric receiver registers. `add-receiver 2 ...` stores an integer register internally, and `r2` now resolves it correctly instead of falling through to `[receivers].allowed` and reporting unknown receiver register. Receiver-register hints now merge stored and configured receivers and sort by register. TUI command-mode `add-receiver` appends the normalized receiver to `[receivers].allowed` in the active config file when not already present.

Added `docs/radio-parameters.md`, a concise inventory of currently settable receiver/session, tuning, AGC, local audio, waterfall, and preset-scope parameters.

Split durable and ephemeral TUI persistence. Config discovery now uses explicit `--config`, then `./config.toml`, then `~/.config/kiwi-client/config.toml`, falling back to built-in defaults. `[receivers].allowed` remains in config. Durable radio presets and receiver-register presets now live in `[presets].file` (`presets.toml` by default, resolved relative to the config file). `state.json` now stores only ephemeral `last_state`.

Updated the working-directory config files to the new layout: `config.toml` owns the receiver allowlist including `10.0.0.42:8073`, `presets.toml` owns receiver register presets, and root `state.json` contains only last-state fields. Removed tolerance for old state-file durable keys by rejecting `presets` or `receiver_presets` in `state.json`.

Cleaned preset/state ownership: full radio presets now exclude config/state-owned fields (`allowed_receivers`, audio startup/fade settings, receiver restriction, live limits, user, volume, connected). Receiver prefix hints now show stored receiver registers only when any receiver presets exist, avoiding misleading fallback register `0` for configs whose receivers are explicitly stored as `1`, `2`, `3`. The default local volume state is now 10% when no state file supplies a volume.

Added per-mode passband tuning and CW heterodyne offset handling. AM/USB/LSB/CW now carry separate passbands; `filter` updates the current mode only and bare `mode` restores the mode-specific saved/default passband. In CW, the displayed/user frequency remains passband center while the Kiwi command frequency adds configured `cw_offset_hz` (default `-800`, so `335.000 kHz` sends `334.200 kHz`). Live plans expose both `frequency_khz` and `radio_frequency_khz`.

Added per-mode tuning step pairs and TUI step cycling. Defaults are AM `5000/1000`, USB/LSB `1000/100`, and CW `100/10`; config may define additional `[normal_hz, small_hz]` pairs per mode. Normal tune keys use the current normal step, shifted tune keys use the current small step, and `t`/`T` move between configured pairs with end clamping.

Improved TUI frequency display: `[display].frequency_decimals` controls displayed kHz precision for frequency and step sizes, defaulting to `3`. Steps are shown as fractional kHz (`Step: 1.000/0.100 kHz`). CW dashboard display labels the user frequency as `Center frequency` and adds a separate radio-frequency/offset line. TUI command handling now catches background `RuntimeError`, so repeating `:pb` while playback is already running reports an error instead of unwinding curses.

Added configurable Kiwi command frequency precision via `[tuning].command_frequency_decimals`. Existing behavior remains 3 decimals by default, while local root config uses 4 decimals so sub-Hz steps can produce sub-Hz `SET mod ... freq=` values such as `4999.2005`.

Changed `setup-python` into a fresh-machine bootstrap for the current project harness: it now installs the editable package with `dev`, `live`, `playback`, and `image` extras and verifies that `pytest`, `websockets`, `sounddevice`, and `matplotlib` are importable. Added an explicit `image` optional dependency for the waterfall PNG inspection helper, and improved the helper's missing-matplotlib error to suggest `./setup-python` or `python3 -m pip install -e '.[image]'`.

Regenerated `artifacts/local-wf-5000-zoom0.png` from the local W/F fixture after installing the image extra. The 2x1024 fixture has plausible raw `sample - 255` intensity ranges: row 0 min/max/median `-200/-31/-88 dBm`, row 1 `-200/-25/-87 dBm`, with persistent bright bins around 26/31 and 529/538. Repeated valid local W/F frames both used `seq=0`; `WaterfallSequenceTracker` now reports repeated zero as `repeated_zero=True`/OK instead of an out-of-order dropout while exact sequence semantics remain open.

Changed standalone live W/F ASCII preview defaults to 50 rows and a 60-second cap. Added separate local ASCII display scaling controls (`--render-min-db`, `--render-max-db`, `--ramp`) while leaving receiver-side waterfall commands as `--min-db` / `--max-db`. The capture path includes the render scaling in status metrics and dry-run plans.

Bookmarked future terminal raster-image waterfall work in `docs/terminal-waterfall-renderer.md`. The spec proposes a standalone optional `kiwi-wf-terminal` command with Kitty graphics first, Sixel later, an in-memory waterfall image buffer, deterministic dBm-to-RGB rendering, and harness tests that do not require a graphics-capable terminal.

## 2026-08-26

### Finding

The live ASCII waterfall emits one 1024-character string per 1024-bin W/F frame. Normal terminal wrapping makes a single radio frame occupy several terminal rows; the receiver data itself already has enough horizontal samples for a detailed raster view.

The first user test in Kitty showed protocol acknowledgement text at the left, blank lines between updates, and a native-size 1024x100-pixel image that was too short. Kitty replies when an image id is used, and image placement moves the cursor by default; the program was neither suppressing replies nor disabling cursor movement.

After quiet/fixed-cursor placement was added, the next user test showed no waterfall during live operation but displayed it when the process was killed. With `C=1`, the first image remained anchored at the shell command's cursor, normally near the bottom of the terminal; most or all of its placement rectangle was therefore clipped below the viewport until process-exit scrolling exposed it.

User experimentation showed that lowering `--interp` did not monotonically reduce apparent smoothing. The newly available `~/kiwiclient` reference and upstream Kiwi server source explain why: `interp` is a categorical FFT-bin reduction selector. Modes `0..4` are max/min/last/drop/CMA and `10..14` add CIC compensation. Default `13` is drop+CIC, not “smoothing level 13.”

Kiwi server/browser source also resolves W/F frequency coordinates: `x_bin_server` is the left edge on a `wf_fft_size << zoom_max` precision grid, the low 16 bits of `flags_x_zoom_server` carry zoom, and span is receiver bandwidth divided by `2**zoom`. The existing local zoom-0 fixture supplies enough MSG metadata to prove full-band `0..30000 kHz` mapping even though its original center request was 5000 kHz.

A short local zoom-7 capture centered at 855 kHz mapped known AM carriers near 760 and 950 kHz to `760.127` and `949.870 kHz`. This confirms the source-derived nonzero-zoom formula and low-to-high bin orientation on `10.0.0.40:8073`.

### Decision

Added `WaterfallHistory` as a renderer-neutral fixed-height dBm ring buffer, deterministic black/blue/cyan/yellow/white RGB mapping, and a dependency-free PNG encoder in `src/kiwi_client/waterfall_raster.py`. Added `src/kiwi_client/waterfall_terminal.py` / `kiwi-wf-terminal` with a pure chunked Kitty graphics encoder, conservative Kitty/Ghostty/WezTerm capability detection, fixture mode, guarded live mode, fixed image-id replacement, display throttling, and optional fixture saving. ASCII and matplotlib paths remain available.

The live W/F capture API now offers a parsed `WaterfallFrame` callback. Raster consumers therefore do not need to extract an ASCII row from generic status metrics, while existing ASCII preview behavior remains compatible.

Kitty transmissions now use `q=2` to suppress responses, `C=1` to prevent cursor movement, and a stable placement id as well as image id. Default placement now uses the detected terminal width and half its height; explicit `--terminal-columns` / `--terminal-rows` values still override it. The backend reserves that row rectangle once before the first draw, moves back to its top-left anchor, performs every update there, and restores the cursor below the image when finished.

Added a decoded W/F interpolation model and validation. Dry-run plans now report both the reduction method and CIC state, CLI help describes the categories, and unsupported values `5..9` are rejected before a connection. For least aggregation, `13` is already drop sampling with CIC compensation; `3` provides drop sampling without compensation. This setting does not control Kitty's spatial scaling.

Added `WaterfallReceiverState` and renderer-independent frame contextualization for start/center/span/bin width. Live capture accumulates W/F MSG metadata and delivers contextualized frames. Fixture preview does the same offline. The Kitty backend renders a frequency ruler as terminal text above the image, preserving all 1024 raster bins.

Replaced the fixed three-label policy with adaptive labels: choose 1/2/5 × power-of-ten major spacing from span and terminal width, derive decimal precision from the interval, preserve mapped edge labels, place interior labels proportionally, and omit overlaps. Narrow terminals retain edges while wider views gain useful major frequencies.

Added renderer-side tuned/passband overlays. A white column marks tuned frequency and orange columns mark enabled low/high passband edges. Overlay rendering copies the RGB image and leaves numeric history untouched; out-of-span markers are omitted and reversed passbands are rejected.

Added `WaterfallConfig` and normal config discovery to `kiwi-wf-terminal`. `[waterfall]` persists center/zoom, history/terminal rows, local render range, receiver speed, refresh cap, interpolation, label density, and overlay settings. Parser defaults remain unset until config merge, so explicit CLI values take precedence. Root local defaults record the currently useful 5000 kHz, zoom 7, 300-row, 30-cell, speed-4, 12-Hz, interp-13 setup with a ±5 kHz passband. Terminal viewer duration/frame limits now inherit `[live]`; root zeros therefore preserve continuous interactive use while built-in guarded defaults remain finite.

Click/tune interaction remains future work. Simultaneous TUI audio and waterfall still requires independent SND/W/F session ownership; the raster viewer remains a standalone companion command.

### Test result

Added harness coverage for history scrolling/padding/orientation, frame-width rejection, fixed RGB values and clamping, PNG structure, Kitty base64 chunking, terminal capability checks, fixture rendering, fake-backend rendering, parsed live frame callbacks, and a fake-WebSocket guarded live viewer.

The system Python had neither pip nor pytest and is PEP 668 externally managed. `setup-python` now creates an ignored `.kiwi-venv`, installs the editable package and all current extras there, verifies imports, and prints activation/direct-test commands.

Initial targeted waterfall tests passed: 32 tests. After the first Kitty visual-test fixes, terminal renderer tests passed: 8 tests; the full harness passed: 221 tests in 3.26 seconds. After adding visible-area reservation and cursor restoration, terminal renderer tests passed: 9 tests and the full harness passed: 222 tests in 2.70 seconds. Interpolation mapping/validation targeted tests passed: 41 tests; the full harness passed: 234 tests in 2.77 seconds. Dry-run output reports `interp_method=drop` / CIC enabled for `13`, and an unsupported `5` exits before connecting.

Frequency mapping/ruler coverage includes synthetic zoom-2 flag masking, local zoom-0 fixture metadata, fake-WebSocket live contextualization, fixed-width ruler placement, and Kitty reserved-area integration. The full harness passed: 240 tests (latest run 2.84 seconds). Offline fixture protocol output contains full-band ruler labels. `python3 -m compileall -q src tests` and `git diff --check` passed.

Adaptive ruler tests cover nice-step selection, interval precision, narrow edge-only layout, AM-band labels, narrowband labels, and non-overlap. After 248 harness tests passed, one guarded local capture was made on `10.0.0.40:8073` at 2026-08-27 04:43:33 UTC / 00:43:33 local: center 855 kHz, zoom 7, speed 4, interp 13, uncompressed, five frames. Fixture `local-wf-am-855-zoom7.jsonl` maps `737.811327..972.186327 kHz` at `228.881836 Hz/bin`; known 760/950 kHz carrier regressions were added. Final full harness after adding explicit medium-width policy coverage: 250 tests in 2.74 seconds.

Overlay tests cover tuned/passband column mapping, colors, immutability, out-of-span omission, reversed cuts, and viewer integration. Config tests cover built-in/root defaults, TOML overlays, and CLI precedence including boolean disable overrides. Targeted overlay/config tests passed: 37 tests. Full harness: 255 tests (latest run 3.38 seconds). Dry-run verification confirmed root duration/frame zeros as well as overlay/default values. Dry-run inspection confirmed root config resolves to center 5000 kHz, zoom 7, 300 history rows, speed 4, refresh 12 Hz, tuned 5000 kHz, and ±5 kHz passband. No live receiver connection was needed.

Investigated a user-reported W/F failure after the Kitty terminal had been unfocused: updates appeared to jump through accumulated time and `websockets` raised `ConnectionClosedError: sent 1011 (internal error) keepalive ping timeout`. Root cause was synchronous raster/PNG/terminal output inside the asyncio receive callback. A background terminal can stop draining graphics output, block stdout, and starve both receive processing and the library's ping/pong timer.

Changed live terminal display to append parsed frames without drawing, signal a single coalescing redraw event, and run raster generation plus terminal output with `asyncio.to_thread()`. Numeric history remains current while the renderer is blocked; when output resumes, one latest-state image replaces stale requests. Added locking and generation tracking so history snapshots are safe and a frame arriving during a draw schedules one later redraw. W/F connections now pass `ping_interval=None` because Kiwi application `SET keepalive` is already sent, and WebSocket closure is wrapped as `LiveCaptureError` for concise CLI reporting without reconnect.

Harness coverage verifies `ping_interval=None`, clean closure conversion, ingestion of 25 immediate frames, one coalesced image, and that drawing occurs off the event-loop thread. Targeted tests: 32 passed. Full harness: 257 passed in 3.71 seconds. No live receiver test was needed or performed for the deterministic backpressure fix.

Cursor tests cover bin-center snapping, movement/clamping, context changes, magenta overlay precedence, split escape-sequence decoding, status/ruler layout, config defaults, pseudo-terminal movement/quit, and exact terminal restoration. Targeted cursor/config tests: 68 passed before the pseudo-terminal case was added. Full harness: 265 passed in 3.85 seconds. No live connection was used.

The blocking regression duplicates a pseudo-terminal input descriptor as output and verifies keyboard startup leaves the shared blocking status unchanged. A CLI harness also verifies output `BlockingIOError` is reported without `Traceback`. Targeted terminal tests: 28 passed; full harness: 266 passed in 3.16 seconds.

Fixed standalone W/F receiver-policy propagation after a user-added `misdr.proxy.kiwisdr.com:8073` allowlist entry was ignored. Config discovery was working, but `_capture_config()` omitted `[receivers].restricted` and `[receivers].allowed`, causing `LiveWaterfallCaptureConfig` to fall back to its built-in local-only policy. Both temporary display and saved-fixture configurations now receive the loaded policy, while `--allow-live` remains mandatory. Dry-run output includes the resolved policy. Restricted-proxy and unrestricted synthetic tests validate without network access; targeted config/terminal tests: 36 passed, full harness: 268 passed in 3.09 seconds.

User validation found the cursor step functional and the current slice acceptable. Final-product requirement: tuning selection must advance on configured round frequency steps, not FFT/source-bin increments. Implemented exact cursor frequency on a zero-anchored grid, independent bin-resolution metadata, per-mode main/small step pairs from existing tuning config, and `t`/`T` pair cycling. Main and shifted movement now use main/small steps respectively; the marker projects exact selection to the nearest raster column. Harness coverage includes snapping, clamping, exact preservation across resolution changes, key decoding, pair cycling, status, and config. Full harness: 269 passed in 3.11 seconds. No live connection was used.

Added queued interactive W/F navigation. `c` emits `SET zoom=<current> cf=<exact cursor>`, `+`/`=` zoom in, and `-` zooms out, bounded by local zoom limits. `capture_live_waterfall()` drains a command queue inside the existing session and records dynamic commands in saved fixtures. Pure encoder, fake-WebSocket send, key decoding, exact-center, and bound tests pass. Full harness: 272 passed in 3.14 seconds; no live connection was used.

Added coordinated but separately owned SND audio to `kiwi-wf-terminal`. Enter queues an exact `SET mod` tune, `--audio`/`[waterfall].audio` enables local output initially, `a` toggles output, and `--null-audio` provides device-free diagnostics. Audio config inherits receiver policy, limits, fades, mode/passband, command precision, and CW offset. Audio status appears in the terminal row; runner errors are isolated from rendering and viewer shutdown stops both tasks. Fake-runner tests cover toggle, exact AM tune, error isolation, and CW radio offset; dry-run exposes the full SND plan. Full harness: 275 passed in 3.18 seconds. No live receiver or audio device was used.

First proxy tests exposed W/F closure code 1005 when audio was added, including immediate `--audio`. Shared timestamp was necessary but insufficient: browser startup opens SND before W/F, while the project scheduled W/F first. `play_live_snd()` now signals readiness after SND open/auth; combined startup waits for it before opening W/F and aborts cleanly if primary SND fails. To support later `a` toggles without reversing pair order, combined live mode always retains the primary SND stream and uses a lazy `SwitchableAudioSink` to mute/enable local output. Fake ordering, failure, muted sink, and restoration tests pass; full harness: 280 passed in 3.33 seconds. No automatic external retest was made.

User retest confirmed combined W/F and audible SND are working after the SND-primary ordering fix. Report received around 2026-08-28 03:07 UTC / 2026-08-27 23:07 local against `misdr.proxy.kiwisdr.com:8073`, using `--audio` and the working config defaults (5000 kHz AM, ±5 kHz passband, W/F zoom 7, speed 4, interp 13). This validates shared timestamp plus SND-ready-before-W/F ordering on the proxy. No project-side external connection or fixture capture was made.

User follow-up after repeating normal operation: the viewer is much improved and no further connection crash was reported. Time progression remains somewhat jumpy, but matches familiar Kiwi browser-client behavior and is therefore provisionally treated as receiver delivery/render cadence rather than a terminal-client backlog. Timing instrumentation remains available as a future fixture-backed diagnostic if needed. The observed `4882.8`, `5000`, and `5117.2 kHz` ruler labels are expected at center 5000 kHz / zoom 7: the mapped span is 234.375 kHz, giving edges near 5000 ±117.1875 kHz.

Checkpointed the completed raster viewer on integration branch `wf1` as commit `6358c1b` and started cursor work on `feature/wf-cursor-readout`, following the new feature-branch workflow while leaving `main` closed.

Added renderer-neutral `WaterfallCursor` state snapped to source-bin centers, clamped movement, and nearest-frequency preservation across mapped-span changes. The raster overlay now uses magenta for the local cursor, distinct from white tuned frequency and orange passband edges. A second terminal text row reports cursor frequency, tuned offset, source-bin width, and controls.

Added incremental keyboard decoding for `h`/`l`, arrows, `H`/`L`, shifted arrows, `0`, and `q`. Live input uses cbreak mode, restores prior termios state in `finally`, and only changes local cursor/display state. It does not send W/F recenter, zoom, SND tuning, or admin commands. Cursor changes enter the existing one-bit redraw/coalescing path.

The first user run exposed `BlockingIOError: [Errno 11] write could not complete without blocking`. Cursor input had called `os.set_blocking(input_fd, False)`. Shell stdin and stdout may be duplicates sharing one open-file description, so the `O_NONBLOCK` status also affected graphics output and made the renderer fail with `EAGAIN`. Removed all keyboard changes to descriptor blocking mode: asyncio `add_reader()` already calls the read callback only when input is ready. Cbreak attributes are still restored. Main now also converts any unrelated output `OSError` into a concise CLI error instead of a traceback.

### Follow-up

Have the user evaluate local cursor visibility, key feel, and status density from `wf1` after merge. Next add receiver W/F recenter/zoom command transport under fake-WebSocket coverage; keep actual audio tuning as a separate coordinated-session slice.

## 2026-09-03

### Finding

Project review found `wf1` aligned with the handoff notes: the latest completed baseline is the combined Kitty raster W/F viewer with paired primary SND audio. The working tree was clean except for local Pi provider-payload logs. `TODO.md` still contained many completed historical slices, and `MANIFEST.md` referenced a missing `README.md`.

### Decision

Removed the local Pi provider-payload logs, collapsed `TODO.md` to current status plus next slice candidates, and refreshed `MANIFEST.md` without changing `config.toml`.

### Test result

Full harness after cleanup: `.kiwi-venv/bin/python -m pytest -q` passed, 280 tests in 3.48 seconds.

### Follow-up

Run the full harness and then choose the next slice: attended combined-viewer evaluation, compact status/key-help refinement, optional timing diagnostics, or UI direction decision.

## 2026-09-03 — Waterfall redraw cadence

### Finding

User validation confirmed cursor movement, Enter-to-tune, recenter/zoom controls, and live audio all work. The cursor is intentionally magenta. At `rows=500`, `terminal_rows=40`, `refresh_hz=20`, and `speed=4`, the process used about 40% CPU while presenting roughly four visible updates per second. A second test with `rows=200`, `terminal_rows=20`, `refresh_hz=50`, and `speed=4` showed a feature crossing the display in only about 14 visible jumps. Since the receiver reports about 23 W/F frames/sec at speed 4, increasing the redraw cap above source cadence did not solve full-image render/terminal pressure.

### Decision

Added a bounded RGB history parallel to numeric dBm history so each received row is color-mapped once rather than rebuilding every retained row on each redraw. Changed transient PNG compression from zlib default level 6 to level 1 and changed redraw scheduling to preserve draw-start cadence rather than waiting a full refresh interval after each completed draw. One-bit redraw coalescing and off-event-loop terminal output remain unchanged.

### Test result

New deterministic tests cover cached row conversion, padding/orientation, bounded history, width rejection, fast PNG compression, and redraw deadline behavior. Targeted raster/terminal tests passed: 53. Full harness passed: 283 tests in 3.51 seconds. `compileall` and `git diff --check` passed before documentation updates. A synthetic 1024×500 benchmark improved snapshot plus PNG work from about 235 ms (75 ms recoloring + 160 ms level-6 PNG) to about 18 ms (sub-millisecond cached snapshot + 17 ms level-1 PNG), with data-dependent encoded size increasing from about 502 KB to 606 KB.

### Follow-up

Post-merge user validation found a broad optimum around `refresh_hz=20`. Motion now has more frequent, smaller jumps, making individual transitions difficult to count and noticeably improving the previous jarring presentation. `rows=400` / `terminal_rows=20` gives a useful approximately one-source-row-per-displayed-pixel presentation at both half and full terminal width. Zooming in appeared to slow vertical travel; leave whether this is receiver or renderer cadence as an open question until measured. Treat cadence optimization as successful for now; add achieved draw/terminal timing counters only if remaining jumps become operationally problematic. CPU after optimization was not recorded.

Future zoom rendering should preserve old W/F history like the KiwiSDR web client: remap prior rows onto the new frequency scale, stretch/resample overlapping data where necessary, and fill frequencies not covered by old rows with black.

Also consider an optional small bounded W/F jitter/playout buffer. The goal would be steady timed row release despite bursty network arrival, trading a controlled amount of latency for smoothness. Any experiment must measure receive cadence first, keep network ingestion nonblocking, cap queued frames, define underflow/overflow behavior, and remain separate from terminal redraw coalescing.

## 2026-09-03 — Direct waterfall frequency entry

### Decision

Added interactive direct frequency entry to `kiwi-wf-terminal`. Pressing `f` opens a status-row kHz prompt; decimal digits and one decimal point edit the value, Backspace removes a character, Esc cancels, and Enter applies. A valid finite non-negative value updates the tuned frequency, queues an exact mode/passband SND modulation command (including CW offset), and queues W/F recenter at the current zoom. Frequencies outside the old visible span remain pending until a recentered contextual frame can place the magenta cursor exactly. Empty/invalid input sends no receiver commands.

### Test result

Pure decoder/parser/model tests and pseudo-terminal routing tests cover editing, cancellation, exact AM commands, CW offset, pending cursor placement, visible prompt status, invalid input isolation, and terminal restoration. Targeted terminal harness: 47 tests passed. Full harness: 289 tests passed in 3.49 seconds; `compileall` and `git diff --check` passed. No live connection was made.

### Follow-up

User-attended validation of `f` entry after merge.

## 2026-09-03 — Shared paired-session coordinator

### Decision

After merging the completed `wf1` history into `main`, added `docs/ui-integration-plan.md` on `feature/shared-radio-session`. Curses remains a control/diagnostic fallback rather than the primary graphical architecture. Shared receiver lifecycle comes first, followed by controller/TUI integration and a native raster frontend evaluation.

Extracted shared timestamp assignment and SND-first/W/F-second lifecycle into UI-neutral `src/kiwi_client/paired_session.py`. `PairedSessionCoordinator` owns the shared stop boundary and distinct SND/W/F command queues. The terminal viewer retains rendering/input policy but now runs capture through the coordinator. Pre-readiness SND failure prevents W/F startup; W/F completion, failure, and cancellation stop primary SND. Post-readiness SND errors remain independently visible under the existing terminal audio controller policy.

### Test result

New fake-runner tests cover timestamp assignment/mismatch, startup ordering, readiness failure, independent queues, cancellation, W/F failure, and post-ready primary error policy. Targeted paired/terminal harness: 54 tests passed. Full harness: 296 tests passed in 3.99 seconds; `compileall` and `git diff --check` passed. No live connection was made.

### Follow-up

Add the controller-owned paired-session state and typed action foundation before changing TUI behavior.

## 2026-09-03 — Interactive session action foundation

### Decision

Added UI-neutral `src/kiwi_client/session_manager.py`. `RadioSessionManager` reduces typed lifecycle, transport, selection, tune, direct-frequency, recenter, zoom, and audio actions into immutable `RadioSessionSnapshot` values plus separate SND/W/F command batches. Errors carry session generations so stale transport results cannot overwrite a restarted session. CW command routing preserves user frequency while applying the configured radio offset.

This is a state/action foundation only. Existing `ClientController` compatibility state and live `BackgroundOperation` behavior remain unchanged until an adapter is harnessed.

### Test result

Six pure tests cover exact dual-stream direct tuning, CW offset, recenter/zoom bounds, local audio state, stale generation rejection, and error clearing on session restart. Full harness: 302 tests passed in 3.73 seconds; `compileall` and `git diff --check` passed. No live connection was made.

### Follow-up

Add a compatibility adapter from `ClientState`/`ClientController` into the shared snapshot and migrate controller command routing incrementally.

## 2026-09-03 — ClientController shared-state adapter

### Decision

Added `paired_snapshot_from_client_state()` and initialized a `RadioSessionManager` inside `ClientController`. Tune, tune-step, mode, filter, atomic batches, receiver changes, and status synchronize the shared receiver/frequency/mode/passband/CW/precision snapshot. `status` now includes `paired_session` while retaining the legacy `session` response during migration. No live operation behavior changed.

### Test result

New controller tests cover initialization from CW `ClientState`, radio command synchronization, exact frequency state, passband changes, and compatible status output. Targeted client/session/TUI tests: 97 passed. Full harness: 304 tests passed in 3.78 seconds; `compileall` and `git diff --check` passed. No live connection was made.

### Follow-up

Map legacy playback lifecycle and generation-aware errors into the shared state, then display paired status in the TUI before starting W/F from it.

## 2026-09-03 — TUI paired lifecycle status adapter

### Decision

Mapped current legacy audio-only `BackgroundOperation` playback into the generation-aware shared session snapshot without changing live startup. Playback start records a new shared generation and desired receiver; status maps SND to running/stopping/failed/stopped and explicitly marks W/F inactive. Intentional stop advances generation so late worker state cannot overwrite the newer stop state. Local audio enabled state reflects null versus real sink selection.

Extended the pure TUI dashboard with optional shared-session lines for desired/active receiver, SND/W/F states, audio state, and W/F zoom. Legacy operation metrics and `RadioSessionState` remain during migration.

### Test result

New controller and dashboard tests cover audio-only lifecycle mapping and paired status rendering. Targeted client/session/TUI harness: 99 tests passed. Full harness: 306 tests passed in 3.91 seconds; `compileall` and `git diff --check` passed. Existing receiver-switch recovery tests remain green. No live connection was made.

### Follow-up

Define and harness a paired TUI operation using `PairedSessionCoordinator`, initially publishing W/F state/metrics without embedding terminal graphics.

## 2026-09-03 — Headless paired TUI operation

### Finding

The existing continuous terminal viewer used `capture_live_waterfall()` with a temporary output path, but the capture writer retained every event in memory until shutdown. Unlimited interactive W/F therefore had unbounded fixture-event growth even though the temporary file was not needed.

### Decision

Added `src/kiwi_client/live_session.py` with a headless paired operation built on `PairedSessionCoordinator`. `radio-bg --allow-live [--null-sink]` starts primary SND then W/F without an embedded raster, publishes SND/W/F status plus filtered W/F metrics, and routes `RoutedSessionCommand` values to independent queues. Existing raw active modulation commands default to SND compatibility. `wf-center [frequency_khz]` and `wf-zoom <+/-levels>` use typed session actions and route to W/F. Receiver switching restarts the same audio-only or paired operation type.

Added optional no-capture mode to live W/F streaming. Headless paired sessions and temporary terminal viewing no longer retain fixture events; explicit `--save-fixture` behavior is unchanged.

### Test result

Fake SND/W/F runners verify SND-first startup, status publication, filtered metrics, stream command routing, and coordinated stop. Controller tests cover configured W/F startup values, SND tune routing, W/F center/zoom routing, and paired receiver restart. A fake-WebSocket regression verifies no fixture is written when event storage is disabled. Targeted live/session/controller/TUI tests: 154 passed before final metric filtering. Full harness baseline: 310 tests passed in 3.99 seconds. No live connection was made.

### Follow-up

Define a bounded renderer-neutral snapshot publisher for future native GUI and optional terminal-pane consumers.

## 2026-09-03 — Renderer-neutral waterfall snapshots

### Decision

Added `WaterfallSnapshotPublisher` as the bounded frontend boundary for future native GUI and optional terminal-pane consumers. Each immutable row retains numeric dBm values, sequence, monotonic arrival time, and original start/center/span/bin-width metadata. The latest snapshot contains a bounded tuple of rows and a generation. `wait_for_newer()` returns the newest generation directly, intentionally coalescing superseded display states rather than maintaining a consumer queue; `close()` wakes blocked consumers.

Headless paired sessions now accept a frame callback. `ClientController` owns a configured publisher for `radio-bg`, recreates it per paired run, and closes it after joined shutdown. TUI config supplies history depth. This does not render graphics or add a GUI dependency.

Added `docs/native-gui-benchmark.md` defining fixed 1024-bin, 200/400/800-row, 20-FPS fixture workloads and comparison criteria for Tkinter, PySide6/Qt, and pygame/SDL. No toolkit is selected or installed.

### Test result

Five pure publisher tests cover bounded immutable history, coalescing, blocking wakeup/close, width validation, and preserving different frequency mappings across zoom changes. Existing fake paired/controller tests now prove frame publication through the shared boundary. Targeted snapshot/live/controller/TUI tests: 101 passed. Full harness: 315 tests passed in 4.09 seconds; `compileall` and `git diff --check` passed. No live connection was made.

### Follow-up

Implement the toolkit-independent benchmark workload/result harness before trying candidate GUI dependencies.

## 2026-09-03 — Native GUI benchmark baseline

### Decision

Added toolkit-independent `tools/waterfall_gui_benchmark.py`. It generates deterministic mapped W/F rows, publishes them through `WaterfallSnapshotPublisher`, samples at a configurable virtual consumer rate, and emits JSON metrics for produced/presented snapshots, coalesced generations, elapsed throughput, and mean/p95 publish time. This establishes one workload/result format before any GUI toolkit adapter is added.

### Test result

Four harness tests cover deterministic frame generation, exact slower-consumer coalescing, validation, and multi-depth JSON CLI output. A 1200-frame 1024-bin no-window run produced mean/p95 publish costs of approximately 0.140/0.171 ms at 200 rows, 0.159/0.222 ms at 400 rows, and 0.158/0.197 ms at 800 rows. Snapshot publication is not the expected GUI bottleneck. Tkinter, PySide6, and pygame are not installed in the current environment; no dependency was added. Full harness: 319 tests passed in 4.14 seconds; `compileall` and `git diff --check` passed.

### Follow-up

Choose an isolated optional toolkit benchmark strategy. Compare at least two viable adapters before selecting the production native frontend.

## 2026-09-03 — Native GUI adapter comparison

### Decision

Added a common direct-RGB adapter benchmark with deferred imports and fake-adapter lifecycle tests. Added separate optional `gui-pyside`, `gui-pygame`, and `gui-benchmark` extras; default/setup dependencies remain unchanged. Compared PySide6/Qt offscreen with pygame-ce/SDL dummy at 1024×200/400/800 over 400 alternating frames.

Both have ample margin over 20 FPS. At 1024×400, PySide6 measured about 0.412 ms mean / 0.609 ms p95 presentation cost; pygame-ce measured 0.844/1.115 ms. PySide6 Essentials plus shiboken occupies about 226 MB versus pygame-ce about 32 MB. Select PySide6 for the first fixture GUI prototype because its widget/layout/input facilities remove substantial application code; retain pygame-ce as a fallback pending an attended real-window test.

### Test result

Four fake-adapter tests cover deterministic RGB, common lifecycle/timing results, cleanup after failure, and multi-height JSON CLI output. Optional PySide6 6.11.2 and pygame-ce 2.5.8 were installed in `.kiwi-venv` for benchmarking only. Full harness pending after the next fixture-prototype slice. No receiver connection was made.

### Follow-up

Build a fixture-only PySide6 window against the shared snapshot/raster boundary, then perform an attended local window test before any live-session integration.

## 2026-09-03 — Fixture-only PySide6 GUI prototype

### Decision

Added optional `kiwi-gui` / `src/kiwi_client/gui_app.py`. The first native window is deliberately fixture-only: it replays contextualized W/F fixture rows into `WaterfallSnapshotPublisher`, builds the existing deterministic RGB raster, and presents it directly through `QImage`/`QPixmap`. It shows mapped frequency range and compact frame/bin/history status. `--repeat` fills a diagnostic history from short captures; `--dry-run` validates the complete model without importing Qt or opening a display.

PySide6 imports remain deferred and failure reports `pip install -e '.[gui-pyside]'`. No live receiver, audio, mouse, or control integration was added.

### Test result

Two model/CLI tests cover repeated contextualized fixture publication, 1024×400 direct RGB construction, mapped text/status, and Qt-free dry-run output. Manual dry-run produced 400 frames over 737.8113..972.1863 kHz from the zoom-7 local fixture. Full harness: 325 tests passed in 4.17 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

User-attended static window validation, then add timed snapshot consumption and controls before connecting the paired live session.

## 2026-09-03 — Native fixture-window exit controls

### Finding

The first attended `kiwi-gui` fixture test found the image/window acceptable, but the attempted exit interaction did not close the application.

### Decision

Added explicit application quit-on-last-window policy and window-scoped `q`, Esc, and Ctrl+Q shortcuts while retaining normal window-manager close behavior. The close-key policy is toolkit-neutral and testable without importing Qt.

### Test result

Targeted GUI model tests: 3 passed. Full harness: 326 tests passed in 3.78 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

User-attended retry confirmed the added GUI exit controls work. Proceed to timed snapshot presentation and basic native controls while remaining fixture-only before live pairing.

## 2026-09-03 — Timed native fixture playback

### Decision

Added `FixtureWaterfallTimeline` to publish contextualized fixture rows incrementally at configurable cadence. Added `SnapshotRasterizer`, which tracks presented generation and converts only new numeric rows to RGB; if a consumer falls behind beyond retained history it rebuilds from the latest bounded snapshot. `kiwi-gui --animate --fps <rate>` drives publication with a Qt timer, consumes the latest snapshot, and reports source/presented generations, requested FPS, and ended state. Static fixture mode remains available.

### Test result

Six GUI harness tests cover mapped static output, finite repeated timeline progression, incremental/padded rasterization, animated dry-run summary, close-key policy, and Qt-free dry-run behavior. Animated dry-run at 20 FPS configuration produced 10/10 source/presented generations for the two-repeat local zoom-7 fixture. Full harness: 329 tests passed in 3.84 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Run the attended animated fixture command, then add shared-state overlays and local controls before live pairing.

## 2026-09-03 — Native one-pixel-per-frame scale

### Finding

User validation confirmed native fixture animation works and requested one displayed pixel row per W/F frame as the default where feasible.

### Decision

Added a pure DPI-aware vertical sizing policy and `--row-pixels` control, defaulting to `1.0`. The Qt raster label has fixed vertical height derived from source history rows divided by device-pixel ratio, while width remains independently resizable. If exact scale exceeds available screen height, it is capped and status reports the effective physical pixels per frame.

### Test result

Seven GUI harness tests pass, including normal-DPI, high-DPI, screen-cap, and explicit 2× vertical-scale policy cases. Animated dry-run reports the requested row scale. Full harness: 330 tests passed in 3.81 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

User-attended animated fixture validation reported the default one-pixel-per-frame scale looks about right. Resume fixture-only overlays and controls.

## 2026-09-03 — Native fixture controls and overlays

### Decision

The native fixture model now initializes `RadioSessionManager` from captured W/F center/zoom metadata and routes selection, tune, direct-frequency, recenter, and zoom actions through it. The raster presentation applies white tuned, orange passband-edge, and magenta selected-frequency overlays after incremental base-image conversion. Keyboard shortcuts and simple native controls expose the actions, but generated SND/W/F commands remain intentionally unsent.

### Test result

Ten GUI harness tests cover session action/command results, overlay columns and precedence, key policy, incremental playback/rasterization, scale policy, and Qt-free dry-run. Full harness: 333 tests passed in 3.87 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Run the attended animated fixture demo and verify overlays, main/small cursor movement, tuning, direct entry, local center/zoom status, exit, and uninterrupted animation.

## 2026-09-03 — Native control visibility and focus corrections

### Finding

Attended control validation found one-pixel markers too thin, tune/center/zoom changes visually unclear, zoom below one apparently frozen, and initial focus trapped in direct-frequency entry so global keys did not work.

### Decision

Markers are now two pixels. Fixture rendering derives a local viewport from shared center/zoom state and incrementally remaps captured rows, using black outside captured frequency coverage. Coincident selection is omitted after tuning so the white tuned marker becomes visible. Zoom remains bounded and responsive at zero. Startup focus now explicitly targets the waterfall; `f` opens frequency entry and accepted input returns focus to the waterfall.

### Test result

Targeted GUI/raster harness: 26 tests passed. Added coverage for marker width, visible zoom/recenter ranges, bounded zero zoom, tuned-marker precedence, and focus policy. Full harness: 337 tests passed in 3.91 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Repeat attended animation and verify two-pixel markers, visible local remapping, tune marker change, zero-zoom responsiveness, focus/keymaps, and timer continuity.

## 2026-09-03 — Primary UI pivot to integrated Kitty terminal

### Finding

Attended PySide6 evaluation did not produce a convincing workflow. The desired layout is a waterfall and frequency/preset ruler above terminal controls, potentially as coordinated windows. Kitty is installed and selected as the initial terminal target.

### Decision

Build one integrated process first: curses owns input and layout, a reserved upper rectangle hosts Kitty graphics, and the shared manager/coordinator owns one paired SND/W/F session. This avoids duplicated controls, IPC, and duplicate receiver connections. Keep standalone TUI/W/F commands as fallbacks and PySide6 as an optional prototype. DWM can manage the resulting terminal normally; a later two-window mode would require explicit IPC/session ownership.

### Follow-up

Create a fixture-only integrated layout and fake-terminal harness covering placement, rulers/presets, redraw coalescing, resize, deletion, and restoration before attended Kitty testing.

## 2026-09-03 — Integrated Kitty fixture shell

### Decision

Added `kiwi-console`, a fixture-only single-process shell. Curses owns the alternate-screen layout and keyboard input; a Kitty presenter writes a replaceable image at an absolute saved-cursor position in the reserved upper half. Adaptive frequency and visible-preset rulers sit below the image, followed by compact status, controls, direct entry, and local preset recall. Source publication and image refresh rates are separate, duplicate generations coalesce, resize invalidates placement, and shutdown explicitly deletes the image.

### Test result

Six focused tests cover layout bounds, small-terminal rejection, preset ruler filtering/placement, Kitty placement/save/restore/deletion bytes, generation coalescing, and network-free dry-run. Full harness: 343 tests passed in 4.14 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Run the fixture shell inside Kitty and validate image/text placement, ruler alignment, key controls, resize, and terminal restoration before paired live integration.

## 2026-09-04 — Kiwi-style console scale and automated Kitty capture

### Finding

The integrated Kitty shell was accepted. Full-height line cursors were difficult to distinguish over waterfall energy. The supplied KiwiSDR reference uses an external bright passband bracket/center indicator above its waterfall and dedicates the lower area to controls.

### Decision

The console no longer overlays tuned/passband/selection lines on raster data. It renders a green external passband bracket with center notch and a separate selection pointer, followed by frequency and preset rulers. The bottom terminal half remains available for a controller/TUI modeled after the existing curses interface. Added a clean timed demo exit so automated desktop capture exercises normal image deletion and terminal restoration.

### Validation

Launched a real Kitty window on local X11/DWM with fixture-only input and captured `docs/screenshots/kiwi-console-fixture.png` after the 400-row history filled. Placement, ruler alignment, passband bracket, preset marker, and lower UI reservation are visible in the captured artifact. Kitty emitted a non-fatal local `libsystemd.so` warning; console execution and capture succeeded. Full harness: 344 tests passed in 4.09 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Add controller-backed live mode using the existing `radio-bg` paired session and bounded snapshots. Reuse existing TUI startup, command/keymap, status, presets, and persistence concepts where appropriate. Validate startup, commands, failure, and cleanup with fake operations before one short attended local-radio test.

## 2026-09-04 — Controller-backed live integrated waterfall

### Decision

Added `ControllerConsoleSource`, which starts the existing controller `radio-bg` paired operation, binds its bounded waterfall publisher and shared session manager to the console display, routes typed session actions through a public controller API, polls synchronized stream state, and idempotently stops/joins the worker. `kiwi-console --allow-live --receiver <local>` now selects this path; audio defaults to a null sink and `--audio` opts into local output. Fixture and live modes are mutually exclusive, and live dry-run does not connect.

### Harness and live result

Fake-controller and fake-operation tests cover startup command selection, optional audio, frame publication, routed SND commands, synthetic failure, and repeated cleanup. Full harness: 350 tests passed in 4.35 seconds; `compileall` and `git diff --check` passed. Two bounded local `10.0.0.40:8073` checks at 5000 kHz AM/zoom 7 succeeded; the second confirmed synchronized `SND running / W/F running`, 85 displayed generations, normal timed shutdown, and automated screenshot capture at `docs/screenshots/kiwi-console-live-local.png`. No admin commands or reconnect loop were used.

### Follow-up

Replace the compact lower panel with existing TUI dashboard/keymap/command-mode components where they fit, then add audio toggle/status and preset persistence through the controller.

## 2026-09-04 — Live console tuning indicator correction

### Finding

User testing found `c` moved the live viewport, but `f` and `h`/`l` followed by Enter did not move the receiver indicator. Controller status polling was adapting stale legacy `ClientState.frequency_khz` back over the shared manager after typed tune actions. Direct entry also recentered implicitly, leaving the bracket centered and visually unchanged. Terminal-cell brackets additionally lack resolution for configured 100 Hz steps across a 234 kHz span.

### Decision

Public typed Tune/Direct actions now synchronize tuned frequency back into legacy controller state before subsequent status adaptation. Console `f` and preset recall use Select+Tune without recentering; `c` remains explicitly responsible for W/F center. Added an 8-pixel high-resolution black tuning strip beneath raster data with a two-pixel green passband bracket/center and magenta selection pointer, while retaining the text scale as fallback.

### Test result

Harness coverage proves controller frequency survives status synchronization, console direct tune preserves center, and exact 1024-bin strip columns/colors. Full harness: 353 tests passed in 3.95 seconds; `compileall` and `git diff --check` passed. No additional receiver connection was made for this correction.

### Follow-up

Repeat live `f` and selection+Enter testing, then continue existing-TUI lower-panel reuse.

## 2026-09-04 — Console scale alignment and duplicate bracket removal

### Finding

Live validation confirmed W/F, tuning, and presets but no sound because the console intentionally defaulted to a null sink. It also exposed duplicate green passband brackets (one high-resolution raster strip and one terminal-text fallback), preset stems positioned at label starts rather than exact frequencies, unnecessary `kHz` suffixes, and distracting exact edge labels such as `308.6` beside round major ticks.

### Decision

Retained only the high-resolution raster passband bracket. Frequency marks now occupy exact frequency columns on a dedicated tick row, labels omit units, and non-major exact edges are suppressed while aligned round edge majors remain. Preset stems now occupy the exact mapped column and labels are placed adjacent without moving the stem. Sound remains opt-in with `--audio`; runtime audio controls and automatic/manual colormap scaling are added to the lower-panel plan.

### Test result

Focused ruler tests cover exact preset/tick columns, unit-free labels, and suppression of an uneven 308.6 kHz edge. Full harness: 353 tests passed in 4.01 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Retry with `--audio` if sound is desired, then implement lower-panel audio and colormap controls through existing TUI/controller behavior.

## 2026-09-04 — Per-row zoom history remapping

### Finding

Live zoom initially remapped retained history correctly, then appeared to return to the old scale as new frames arrived. Each snapshot row already retained its original start/span, but `SnapshotRasterizer` rebuilt every historical row using only the newest snapshot mapping during a zoom transition.

### Decision

The rasterizer now caches only the target viewport and remaps every retained or newly appended row from that row's own immutable `start_khz`/`span_khz`. Old and new zoom generations therefore share the current ruler correctly, with black fill outside each row's captured coverage.

### Test result

Added a mixed-history regression containing a 0..100 kHz row followed by a 25..75 kHz row and proved each maps independently into the 25..75 kHz target. Targeted GUI/console harness: 29 tests passed. Full harness: 354 tests passed in 3.92 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Repeat live zoom transitions and verify retained history remains registered to the current ruler while new rows arrive.

## 2026-09-04 — Graphical scale direction

### Finding

Attended zoom validation now looks good. Terminal-cell frequency ticks and preset annotations remain visibly disconnected from the pixel-exact waterfall coordinate system; even correctly calculated stems quantize to character columns.

### Decision

Move the complete waterfall-relative presentation into one raster: W/F history, tuning/passband strip, major tick stems and numeric labels, and preset stems/labels all share the same 1024-bin frequency transform. Use deterministic harness-testable bitmap text and pixel-coordinate collision rejection. Keep the lower control/status half in curses so existing TUI behavior remains reusable rather than turning the entire application into a custom graphical toolkit.

### Follow-up

Implement fixture tests for bitmap glyphs, round major ticks, exact frequency columns, preset label collisions, and composed-image dimensions before replacing the terminal ruler rows.

## 2026-09-04 — Graphically composed waterfall scales

### Decision

Added `waterfall_scale.py` with a dependency-free 5x7 bitmap font and one compositing pass for W/F-relative UI. Tuning/passband, selection, round major tick stems/numeric labels, and visible preset stems/register-frequency labels now share the exact 1024-bin frequency transform. Labels reject collisions in pixel coordinates, omit units, and naturally exclude non-major exact edges. Removed the three terminal-cell scale rows and returned their space to the lower curses panel.

### Test and visual result

Three pure raster tests cover deterministic glyph output, exact marker/tick/preset columns, composed dimensions, round-edge behavior, and preset collision rejection. Full harness: 356 tests passed in 4.02 seconds; `compileall` and `git diff --check` passed. An automated fixture-only Kitty run completed normally and refreshed `docs/screenshots/kiwi-console-fixture.png`; graphical 750/800/850/900/950 ticks, passband bracket, and preset A label align with the waterfall. No receiver connection was made.

### Follow-up

Proceed with existing-TUI lower-panel reuse and manual/automatic colormap controls.

## 2026-09-04 — FreeType graphical scale labels

### Finding

The dependency-free 5x7 font kept exact alignment but was visibly crude, and its Python per-pixel glyph loop was inappropriate as the preferred renderer.

### Decision

Added a lazy Pillow/FreeType scale renderer using DejaVu Sans Mono with anti-aliasing and C-backed rasterization. Text labels are collected and rendered onto the composed image in one Pillow pass rather than copying the image per label. `auto` falls back to the deterministic bitmap renderer if Pillow/font loading is unavailable; `pillow` and `bitmap` can be selected explicitly, and the font name is configurable. Added the optional `terminal-graphics` dependency group.

### Test and visual result

A focused test verifies FreeType output includes anti-aliased intermediate pixel values while existing exact-column/collision tests remain backend-independent. Automated Kitty fixture capture refreshed `docs/screenshots/kiwi-console-fixture.png` and shows materially smoother frequency/preset labels. Full harness: 357 tests passed in 3.95 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Implement manual/automatic colormap scaling, then reuse existing TUI lower-panel behavior.

## 2026-09-04 — Manual and automatic waterfall display levels

### Decision

Added `WaterfallLevelController` for local-only colormap limits. Manual keys independently adjust min/max in 5 dB steps and disable auto mode. Automatic mode samples bounded numeric history every 20 generations, estimates configurable low/high percentiles with padding, enforces a minimum 20 dB range, and smooths changes. Applying new limits invalidates cached RGB history and recolors retained numeric rows without affecting receiver commands or frame queues. Console status reports mode and effective range.

### Test result

Pure tests cover independent manual adjustment, auto-mode cancellation, percentile outlier resistance, padding, smoothing, minimum range, cadence, and status. GUI-model coverage proves scale changes invalidate/rebuild RGB history. Full harness: 362 tests passed in 3.99 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Evaluate default percentile/padding values during attended use, then proceed with existing-TUI lower-panel reuse.

## 2026-09-04 — Integrated default steps and TUI input reuse

### Decision

The integrated console now defaults selection to 1.0/0.1 kHz regardless of the first configured per-mode step pair; `--main-step-khz` and `--small-step-khz` override it without changing `config.toml`. In controller-backed live mode, the lower panel delegates command mode, editing/history, contextual hints, configured non-waterfall keys, preset/store/receiver prefixes, command parsing, errors, and persistence paths to existing TUI functions. Waterfall selection, Enter tune, center/zoom, direct entry, and display-level keys remain intentional console-specific intercepts.

### Test result

Dry-run coverage records 1.0/0.1 kHz defaults. Existing TUI key/command harness remains shared with the integrated path; focused integrated/TUI/level tests: 67 passed. Full harness: 362 tests passed in 4.00 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Refine compact dashboard/status reuse and add explicit runtime audio state/toggle behavior.

## 2026-09-04 — Step cycling, edge passbands, and Kitty flicker

### Finding

Attended use found `t`/`T` changed controller step-pair state without updating console selection increments, passbands disappeared when either edge left the viewport, and high-zoom operation occasionally showed one fully black W/F/scale frame.

### Decision

Live startup now selects the configured pair nearest the requested 1.0/0.1 kHz console defaults. Existing TUI `t`/`T` dispatch remains authoritative and synchronizes resulting main/fine values back into the waterfall model; status shows both. Graphical passbands now draw their visible intersection with the viewport and clip at boundaries. Routine redraw no longer calls curses `erase()` over the Kitty placement: only lower text rows are cleared, while full-screen clearing is reserved for startup/resize. This removes the likely clear-before-image-transfer flicker path without changing image coalescing.

### Test result

Focused tests cover nearest configured step-pair choice and a partially off-screen passband at exact clipped columns. Integrated/scale/TUI harness: 69 tests passed. Full harness: 364 tests passed in 3.99 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Repeat high-zoom operation. If a black frame persists without curses clearing, instrument/replace same-image-ID transfer with a double-buffered Kitty placement.

## 2026-09-04 — Integrated RSSI indication

### Decision

Added a compact lower-panel RSSI meter sourced from existing primary SND worker metrics. It reports calibrated RSSI dB, a conventional HF estimate using S9=-73 dBm and 6 dB per unit below S9, and a clamped 10-segment visual range mapped over -130..-20 dB. Fixture/no-metric state reports unavailable without inventing a value.

### Test result

Pure coverage verifies S1, S9, and S9+ labels plus weak/strong/unavailable bounded bars. Targeted integrated harness: 15 tests passed. Full harness: 365 tests passed in 5.47 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Evaluate readability during the next attended live run and later add peak/decay behavior only if instantaneous RSSI is too noisy.

## 2026-09-04 — Receiver-switch publisher rebinding and stable RSSI

### Finding

RSSI/S-unit text changed width as values varied and used dB rather than dBm. More importantly, receiver switching restarted paired audio successfully but permanently stopped console W/F display: `ClientController` correctly replaced its bounded publisher for the new paired operation, while `ControllerConsoleSource` retained the closed previous publisher.

### Decision

RSSI now uses fixed-width numeric and five-character S-unit fields with dBm units. The live source polls controller publisher identity as well as generation. On replacement it binds the new publisher, resets RGB history while preserving shared session view, reports a source transition, and clears the old Kitty placement while waiting for the new receiver's first frame. The presenter now supports reusable idempotent clear separately from final shutdown.

### Test result

Harness coverage replaces the publisher directly and also performs a complete fake paired receiver switch from `10.0.0.40` to `.41`, proving a new publisher, new frame, command routing, and final cleanup. Fixed-width RSSI tests cover weak/strong/unavailable formatting and dBm/S-unit output. Full harness: 366 tests passed in 4.02 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Repeat a live receiver-register switch and verify audio plus W/F resume together with a fresh history.

## 2026-09-05 — Live receiver-switch validation

### Decision

Separated persistent UI event messages from continuously refreshed transport status so receiver-switch results remain observable. Transport status now always includes active receiver plus SND/W/F state.

### Live result

After harness coverage passed, automated Kitty input tuned a bounded null-audio session to 5000 kHz on local `.40` and sent stored receiver register `r2`. The controller restarted on `10.0.0.41:8073`; the console detected the replacement publisher, cleared old history, and displayed 38 fresh W/F rows with both streams running and RSSI -96.3 dBm S5. Screenshot: `docs/screenshots/kiwi-console-switch-41.png`. Normal exit succeeded; no reconnect loop or admin commands were used. Full harness remained green at 366 tests in 4.00 seconds; `compileall` and `git diff --check` passed.

### Follow-up

Proceed with runtime audio state/toggle and compact dashboard refinement.

## 2026-09-05 — Runtime integrated audio toggle

### Decision

Moved the existing lazy switchable sink from the standalone waterfall module into the shared playback layer and made it lock-protected. Controller-backed paired sessions now always use this gate: `--audio` controls startup state and `a` opens/closes `SoundDeviceSink` without stopping primary SND. Typed `ToggleAudio` updates the device gate, shared status, and receiver-restart preference; device startup failure restores the prior muted state. The standalone terminal reuses the same implementation.

### Test result

Audio tests cover muted startup, lazy device creation, writes, mute, reopen, stop, and pre-start misuse. Controller tests cover toggle state/restart preference and failure rollback. Focused audio/standalone/controller/console harness: 112 tests passed before the rollback addition. Full harness: 370 tests passed in 4.07 seconds; `compileall` and `git diff --check` passed. No additional receiver connection was made.

### Follow-up

Attended-test `a` mute/unmute and volume keys, then refine compact dashboard/persistence behavior.

## 2026-09-05 — Double-buffered Kitty presentation

### Finding

User validation confirmed `a` audio toggle works, including across receiver switching. Roughly ten full W/F+ruler black flashes per minute remained at maximum zoom after routine curses image-area clears had already been removed. This isolates the likely gap to same-image-ID replacement in Kitty presentation rather than network history or curses layout.

### Decision

`KittyPanePresenter` now alternates image/placement IDs 41 and 42. It transmits and displays the complete next PNG at the stable rectangle before deleting the previous image ID, preserving one visible placement throughout ordered terminal processing. Coalescing remains generation/layout based; clear and final cleanup delete only the active slot and remain idempotent.

### Test result

A byte-level regression proves the second image/display command precedes deletion of the first and final cleanup deletes the active second image. Targeted presenter harness: 17 tests passed. Full harness: 371 tests passed in 4.04 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

User validation at maximum zoom reported no further black flashes after double buffering. Continue compact dashboard, persistence, and volume-control refinement.

## 2026-09-05 — Shared receive-mode keymap and compact volume status

### Decision

Added `m` as a shared TUI/integrated prefix for receive modes: `a` AM, `u` USB, `l` LSB, and `c` CW. Selection delegates to existing `mode` command behavior, so configured mode passbands, active SND command routing, shared state, and subsequent mode step pairs remain authoritative. Pending-mode hints show each mode and passband. The integrated compact status now includes controller volume percentage beside fixed RSSI and W/F generations; `k`/`j` continue through configured existing TUI volume actions.

### Test result

TUI harness cycles all four mode mappings and verifies expected default passbands plus pending-map hints. Existing 16-line key-hint bound is preserved by compacting step/mode help. Focused TUI/integrated harness: 69 tests passed. Full harness: 373 tests passed in 4.01 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

### Follow-up

Attended-test mode switching and volume/audio controls, then verify preset/store persistence from the integrated command surface.

## 2026-09-05 — CW graphical passband reference correction

### Finding

At user frequency 300 kHz, CW passband graphics appeared near 300.650–301.050 kHz. The scale composed every mode's cuts directly around the user frequency, but existing CW protocol/state documentation defines the Kiwi radio frequency as `user frequency + cw_offset_hz`. The command path already applied that offset; only the graphical scale omitted it.

### Decision

The graphical scale now accepts a distinct passband reference frequency. The integrated console supplies the radio frequency for CW and the user frequency for other modes. The green center/reference marker remains at the user frequency, while CW bracket edges show the actual RF interval. With current settings (`cw_offset_hz=-800`, cuts 650..1050 Hz), 300 kHz produces edges 299.850..300.250 kHz rather than 300.650..301.050 kHz.

The existing configuration calls the user frequency the passband center, but its 850 Hz cut midpoint differs from the 800 Hz offset by 50 Hz. Therefore the actual bracket center is 300.050 kHz. This small residual is configuration semantics, not a rendering error; exact centering would require matching the offset magnitude to the cut midpoint (for example `-850` with the current cuts), which was not changed.

### Test result

A pixel-level regression verifies both CW RF edges, the unchanged 300 kHz user marker, and absence of the former unshifted edge. Focused scale/integrated harness: 23 tests passed. Full harness: 374 tests passed in 4.03 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

## 2026-09-05 — Prevent scroll-wheel volume changes

### Finding

There was no intentional mouse-to-volume mapping. The integrated console had not enabled curses mouse reporting, so Kitty's alternate-screen fallback translated wheel rotation into repeated up/down arrow sequences. Existing configured up/down actions step volume by 10 percent, producing large changes from a small wheel rotation.

### Decision

Enable curses mouse event reporting for the console lifetime, consume `KEY_MOUSE` events with `getmouse()`, and restore the previous no-reporting behavior during cleanup. All mouse events are currently ignored; keyboard up/down and `k`/`j` volume mappings remain unchanged.

### Test result

A regression verifies reported mouse input is consumed while keyboard `KEY_UP` remains available to normal configured dispatch. Integrated harness: 18 tests passed. Full harness: 375 tests passed in 4.02 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

## 2026-09-05 — Ten frequency divisions per label interval

### Decision

The graphical frequency ruler now divides each adjacent major-label interval into ten equal intervals. Minor ticks use the same exact frequency-to-pixel transform as labels and passband graphics but are two pixels high; labeled major ticks remain five pixels high. Labels and their adaptive 1/2/5 major step are unchanged.

### Test result

The scale regression verifies minor ticks at the first and ninth subdivisions and distinguishes their height from major stems. Focused scale/integrated harness: 24 tests passed. Full harness: 375 tests passed in 4.04 seconds; `compileall` and `git diff --check` passed. No receiver connection was made.

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
