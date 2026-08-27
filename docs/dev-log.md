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

User follow-up after repeating normal operation: the viewer is much improved and no further connection crash was reported. Time progression remains somewhat jumpy, but matches familiar Kiwi browser-client behavior and is therefore provisionally treated as receiver delivery/render cadence rather than a terminal-client backlog. Timing instrumentation remains available as a future fixture-backed diagnostic if needed. The observed `4882.8`, `5000`, and `5117.2 kHz` ruler labels are expected at center 5000 kHz / zoom 7: the mapped span is 234.375 kHz, giving edges near 5000 ±117.1875 kHz.

Checkpointed the completed raster viewer on integration branch `wf1` as commit `6358c1b` and started cursor work on `feature/wf-cursor-readout`, following the new feature-branch workflow while leaving `main` closed.

Added renderer-neutral `WaterfallCursor` state snapped to source-bin centers, clamped movement, and nearest-frequency preservation across mapped-span changes. The raster overlay now uses magenta for the local cursor, distinct from white tuned frequency and orange passband edges. A second terminal text row reports cursor frequency, tuned offset, source-bin width, and controls.

Added incremental keyboard decoding for `h`/`l`, arrows, `H`/`L`, shifted arrows, `0`, and `q`. Live input uses cbreak mode, restores prior termios and blocking state in `finally`, and only changes local cursor/display state. It does not send W/F recenter, zoom, SND tuning, or admin commands. Cursor changes enter the existing one-bit redraw/coalescing path.

### Follow-up

Have the user evaluate local cursor visibility, key feel, and status density from `wf1` after merge. Next add receiver W/F recenter/zoom command transport under fake-WebSocket coverage; keep actual audio tuning as a separate coordinated-session slice.

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
