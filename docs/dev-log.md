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

Added bin-to-column reduction to the W/F display path. `render_ascii_waterfall_row()` emitted one character per bin, so a real 1024-bin frame soft-wrapped across roughly six to eleven physical terminal rows and stopped reading as a waterfall. `reduce_bins()` now aggregates bins into display columns before ramp mapping, using `i * bins // columns` bucket edges so every bin lands in exactly one bucket and bucket sizes differ by at most one bin. Default aggregation is `max` so a single-bin carrier survives decimation; `mean` is available for noise-floor viewing. Reduction never upsamples.

`kiwi-wf-preview`, `kiwi-wf-capture`, and `kiwi-wf-live` gained `--columns` (default: detected terminal width, `0` for one character per bin) and `--reduction`. Terminal width is resolved only in the CLI layer via `terminal_columns()` / `resolve_columns()`; `LiveWaterfallCaptureConfig.ascii_columns` carries an explicit count so dry-run plans and capture status metrics remain deterministic under test. Harness tests cover bucket arithmetic, max-vs-mean carrier survival, no-upsample and invalid-argument behavior, terminal-width defaulting via `COLUMNS`, and rendering of the real 1024-bin local fixture through both the offline and fake-websocket live paths. Full suite: 229 passed.

Confirmed this is a decimation defect, not a display-resolution limit, and separate from actual frequency resolution: the local fixture shows `bandwidth=30000000` with `wf_fft_size=1024`, so one bin at zoom 0 spans about 29.3 kHz. Bin/frequency mapping and zoom control remain the next prerequisite before richer rendering.

Also noted from the same fixture: the receiver replied `MSG wf_fps=1` to the client's `SET wf_speed=1` against `wf_fps_max=23`. Live preview frame rate is currently capped by our own default, not the receiver.

Reworked `setup-python` to create and use a project-local virtual environment, `.venv-kiwi` (overridable with `KIWI_VENV`). The previous script assumed a usable ambient interpreter; the system `python3` on this machine has no `pip` module, and Arch enforces PEP 668, so `pip install -e .` into the system interpreter could not work. Added `.venv-kiwi/` to `.gitignore`.

Reviewed `docs/terminal-waterfall-renderer.md` backend priority against the actual terminal. The bookmarked spec proposes Kitty graphics first and Sixel later, but the terminal in use is foot 1.27.0, which implements Sixel (`\EPq ... \E\` per `foot-ctlseqs`) and does not implement the kitty graphics protocol; its kitty support covers the keyboard protocol, text sizing, and notifications only. Initially recommended inverting that order. Corrected later the same day: foot was happenstance, and kitty and ghostty are also in use on this machine, both of which support the Kitty graphics protocol. The spec's Kitty-first order is therefore fine. What the spec actually needs is runtime capability detection plus a text fallback, since the terminal varies between sessions and no single protocol covers all of them. Not yet applied to the spec.

Captured the project's first zoom != 0 W/F fixtures and used them to resolve the bin-to-frequency mapping. `tests/fixtures/kiwi/local-wf-910-zoom8.jsonl` (center 910 kHz, zoom 8) and `tests/fixtures/kiwi/local-wf-760-zoom9.jsonl` (center 760 kHz, zoom 9), both 60 frames at `wf_speed=4`. The files were originally saved under names claiming zoom 4 and zoom 6; they were renamed to match their actual capture metadata.

`x_bin_server` turned out to equal `MSG start`, which is why it looked unused at zoom 0 where both are `0`. `start` counts in zoom-max bin units of `bandwidth / (wf_fft_size * 2**zoom_max)` = 1.788139 Hz. Added `WaterfallSpan` (geometry and bin/frequency conversion), `WaterfallSessionMetadata` (accumulates `bandwidth`, `wf_fft_size`, `zoom_max`, `zoom`, `start` across MSG frames), `apply_span()` (fills the previously unused `center_khz`/`span_khz`/`start_khz`/`bin_width_hz` fields on a frame), and a provisional `zoom_from_flags()`. Window center now reproduces the tuned `cf` to within a few Hz.

Verified the mapping against known AM broadcast carriers rather than against itself: all 11 channels from 860-960 kHz in the zoom-8 capture and all 5 from 740-780 kHz in the zoom-9 capture peak on the predicted bin, each more than 6 dB above the median bin level. Tests live in `tests/waterfall/test_frequency_mapping.py` and need no receiver. Full suite: 251 passed.

`BIN_CENTER_OFFSET = 0.83` is recorded as provisional and unexplained. Known carriers peak 0.83 bins below the naive `start_hz + i * bin_hz` prediction, identically in both captures despite different zoom, center, and bin width, so it is constant in bins rather than Hz. The two captures bound it to `0.75 < offset <= 0.90`, which rules out both a half-bin and a whole-bin center convention. Needs a third capture at another zoom and a real explanation before it is treated as settled.

Answered the "2-character wide carrier" question from the fixture. Display columns cannot split an FFT bin, because `reduce_bins` partitions bins with `i*bins//columns` edges and each bin belongs to exactly one column, so two bright characters require two bright bins. At 950 kHz there genuinely are two: bins 860 at -39 dBm and 861 at -38 dBm, ordinary FFT scalloping from a carrier sitting at fractional bin position 0.71. Whether those two bins render as one character or two then depends on terminal width; they fall in separate columns at widths 145, 170, and 195 but share a column at 150, 160, 175, 180, and 190. The per-frame peak bin was stable across all 60 frames, so this is not time smearing from max-hold.

Other observations from the same captures: `seq` stayed `0` for all 60 frames at `wf_fps=23`, so repeated zero is not a slow-rate artifact; `SET wf_speed=4` produced `MSG wf_fps=23`; and the receiver reported `rx_chans=8 wf_chans=3 wf_share=1 zoom_cap=11` against the June capture's `rx_chans=4 wf_chans=4 zoom_cap=14`, so either it was reconfigured or the address fronts more than one host. `zoom_cap`, not `zoom_max`, is the effective zoom ceiling.

Captured `tests/fixtures/kiwi/local-wf-910-zoom11.jsonl` (center 910 kHz, zoom 11, 60 frames) specifically to discriminate whether the bin center offset is constant in bins or in Hz. Zoom 11 bins are 14.3 Hz against zoom 8's 114.4 Hz, so a fixed frequency error would have shown up as about 6.6 bins. The measured offset was 1.0 bins. **The offset is constant in bins.**

Tightened the magnitude by parabolic interpolation of carrier peaks in the dB domain across all three zoomed captures, 17 carriers total: mean 0.895 bins, sd 0.192, standard error 0.047, 95% interval 0.803 to 0.986. This agrees with the independent rounding-based bound of `0.75 < offset <= 0.90` derived earlier. Raised `PROVISIONAL_BIN_CENTER_OFFSET` from 0.83 to 0.89.

Kept it provisional. The cause is still unknown, and an exact whole-bin offset of 1.0 cannot be ruled out: it sits just outside the 95% interval, but parabolic interpolation carries a window-dependent bias of comparable size and the receiver's FFT window is unknown. Recorded that the choice does not affect bin selection at all, since any value in 0.75..0.90 puts every measured carrier on the same bin; only sub-bin frequency readout depends on it. Identifying the FFT window is the likely path to closing this.

Added two tests beyond extending the existing parametrized set: one asserting the Hz-constant hypothesis predicts the wrong bin at zoom 11 while the bin-constant one predicts the right bin, and one asserting the zoom-11 window contains exactly one 10 kHz AM channel, so that single-carrier calibration cannot silently pass on a mis-tuned capture. Full suite: 258 passed.

Process note: an uncapped `kiwi-wf-live --save-fixture` run at `wf_speed=4` reached 12 MB and 8112 frames in six minutes. A `git add -A` swept a partially-written 191 KB snapshot of it into a commit; it was removed by amending before the commit was final. Two lessons recorded: stage fixture paths explicitly rather than using `git add -A` while a capture may be running, and cap capture length, since the calibration needs only 60 frames.

Corrected the bin center offset back to 0.83 after a question exposed a bad choice. Raising it to 0.89 on the strength of the interpolated mean was wrong: requiring all 17 measured carriers to round onto their observed bins admits only `0.762 < offset <= 0.895`, so 0.89 sat 0.005 bins from the edge and the interpolated mean of 0.895 landed exactly on it. A point estimate landing precisely on a hard bound is evidence the dB-domain parabolic interpolation is biased high, not evidence the bound is coincidental. The configured value is now the window center, which maximises margin against misbinning a carrier this data has not seen.

Also disproved the leading explanation. If `x_bin_server` pointed one bin below the first displayed bin, the offset would be exactly 1.0; that misplaces 3 of 17 carriers, so it is excluded. A half-bin center convention misplaces 7 of 17. Both are now ruled out rather than merely unsupported.

Recorded that accuracy is not what the choice trades off: the whole admissible window spans 0.133 bins, about 7 Hz at zoom 8 and 1 Hz at zoom 11. Bin-selection robustness is. Added two tests, one asserting the configured offset stays more than 0.05 bins clear of both edges of the admissible window, and one asserting 1.0 remains excluded so the documentation cannot drift from the data.

Clarified in the protocol notes what the offset is actually between, since that was not stated: the naive bin index `(f - start_hz) / bin_hz` for a carrier of known frequency, and the measured index of its energy peak.

Added `src/kiwi_client/waterfall_sweep.py` / `kiwi-wf-sweep` to measure the bin center offset directly rather than inferring it from broadcast carriers. Against a reference of known exact frequency it steps the window past the tone and takes one constraint per window position; the intersection collapses once the peak crosses a bin boundary. Precision is set by the step size, not by the reference's frequency error, so it is bounded by `2**(zoom_max - zoom)` positions per bin: 32 at zoom 9. Against a synthetic sweep with a planted 0.83 offset the tool returns `(0.8260, 0.8573]`, 0.031 bins wide, about four times narrower than the 0.133 bins the AM carriers give.

Frames are grouped by the `x_bin_server` the receiver reports rather than by the retune command that produced them. That avoids correlating frames with commands and tolerates the receiver quantising a requested `cf` to its own grid, so the sweep does not need `cf` control finer than the receiver's own step.

Analysis averages frames rather than max-holding them. Max-hold is right for finding strong stable carriers but latches onto noise peaks exactly when the reference is weak, which is the regime a 60 kHz reference will be in. Every earlier analysis in this project used max-hold; that was fine for AM broadcast carriers and would have been wrong here.

Three configurations are rejected at validation rather than producing a fixture that turns out to say nothing: a sweep too short to cross a bin boundary, a step coarser than 0.1 bins which could not improve on the existing bound, and a zoom too low to center the reference. The first was found by reading the dry-run plan of the original defaults, which swept only 0.84 bins.

Recorded the zoom trade-off. Higher zoom narrows bins and collects less atmospheric noise, roughly 3 dB per step, which matters for a weak LF reference; but positions per bin halve at the same rate, so sweep resolution coarsens just as fast, and at zoom 14 there is one position per bin and the method fails entirely. Zoom 9 or 10 balances them.

Noted candidate references. WWVB at 60 kHz is cesium-referenced and needs zoom 8 or higher, since lower zooms cannot center it and clamp against 0 Hz where bin 0 is dead in every frame at every zoom. Its BPSK modulation at +/-45 degrees leaves about half the power in the discrete carrier line so it remains usable. WWV at 10 MHz would place `start` several hundred times higher than a 60 kHz sweep, testing whether the offset depends on `start` at all. The receiver's own signal generator would be ideal, being locked to the same ADC clock as the FFT so clock error cancels, but whether `SET gen=` is global or per-connection is unverified and a global generator would inject a tone into every other connected user.

Tests: 23 pure-analysis tests build synthetic sweeps with planted offsets from 0.0 to 1.5 and check recovery, precision matching the step size, SNR rejection, and the contradictory-input and nothing-detected error paths. 16 harness tests cover guardrails, the dry-run plan, the CLI including offline `--analyse` mode, and a live loop against a fake receiver that tracks `SET zoom/cf` and synthesises frames for whatever window it is tuned to. Full suite: 299 passed.

Ran the first live sweeps, against WWVB at 60 kHz and WWV at 10 MHz, both zoom 9 with 40 window positions. Both returned contradictory constraints, which falsifies the constant-offset model rather than the sweep. Two independent facts rule a constant out: per-position offsets span 1.062 bins, where a constant can only span below 1.0; and peak bin transitions fall 35 window positions apart, where a constant requires exactly `2**(zoom_max - zoom)` = 32. The effective offset drifts about 0.094 bins between consecutive transitions.

Both references trace an identical pattern, agreeing to about 0.003 bins at every position, despite 60 kHz versus 10 MHz and `start` values differing by roughly 300x (17148 versus 5576006). So the effect follows window position, not frequency and not absolute `start`. Mean offset is +0.907 and +0.903 bins respectively, which is near 1.0 and notably above the 0.83 the AM carriers gave; that is consistent with the carriers having sampled arbitrary phases of a varying quantity, and explains their otherwise-puzzling 0.86 bin scatter that I had attributed to station tolerance plus bin quantisation.

The puzzle is that both pieces the sweep contradicts are independently confirmed. Bin width is confirmed as `bandwidth / (1024 * 2**zoom)` by AM carrier spacing over 874 bins at zoom 8 and 699 bins at zoom 9, and `unit_hz` is confirmed by window centre recovery reproducing the tuned `cf` to a few Hz at three zooms. Given both, `bin_width / unit_hz` must be exactly 32, yet 35 `start` counts are what move the peak one bin. Best current guess is that the receiver's passband does not move by exactly one `unit_hz` per reported `x_bin_server` count during retuning, making `x_bin_server` an accurate label for a window but not a linear measure of its position. Settling that needs the KiwiSDR BeagleBone and DSP sources, not more black-box captures.

Deferred deliberately, at the user's call. `PROVISIONAL_BIN_CENTER_OFFSET` stays at 0.83, which still puts every measured carrier on the correct bin, and the protocol notes now open with a warning that the constant model is known incomplete. Nothing in the project depends on sub-bin accuracy today; beacon-detection frequency estimates would be the first thing that does.

Reworked the sweep tool so the failure is informative rather than fatal. `offset_window()` still raises when no constant fits, but now names the non-constant offset as a known cause. Added `bin_transitions()`, `positions_per_bin()`, `observed_positions_per_bin()`, and `offset_statistics()`, which stay valid when the constant model fails and are what actually diagnose it. `summary()` no longer raises in that case, reporting `constant_offset_fits: false` plus the statistics; previously `--json` on a contradictory sweep crashed with a traceback. The text report now prints mean, range, transition spacing, and the model-versus-observed positions per bin.

Added `--export-samples`, writing a compact per-position record. A raw sweep fixture is about 1.3 MB because it keeps every frame; the record keeps only what the analysis consumes, around 7 KB, so the evidence is committable. Both sweeps are exported to `docs/evidence/` and asserted by tests, while the raw `sweeps/` directory is gitignored. Full suite: 311 passed.

Scoped the waterfall as a visualization path rather than a measurement path, at the user's call, and recorded the boundary in `docs/architecture.md`. This settles the bin center offset question: it becomes a display concern affecting axis labels and cursor readout, not a blocker for anything.

The reasoning, beyond the offset itself. W/F is lossy by design: 8-bit levels quantised to 1 dB, receiver-side `interp` smoothing already applied, no phase at all. SND carries full 16-bit PCM, preserves phase, offers IQ mode, and reports `sample_rate` to six decimals (`11998.940540` locally against a nominal 12000) so the timebase can be corrected. The waterfall exposes no equivalent and derives every frequency from the nominal `bandwidth=30000000`. For a steady carrier the audio path gives 1/T Hz from a plain FFT, so 0.017 Hz from a minute, against 14.3 Hz bins at zoom 11 with unusable sub-bin refinement.

Milestone 9's long-integration and correlation work needs phase, which the waterfall discards entirely, so this was never going to work from W/F data regardless of the offset. Corrected an earlier dev-log and TODO claim that beacon-detection frequency estimates would be the first thing to need sub-bin waterfall accuracy; `docs/roadmap.md` already specified Milestone 8 as audio-based, so the architecture was right and only these notes were wrong.

Added a colour waterfall pane to the curses TUI, fed from fixtures. Three new modules keep the layers apart: `waterfall_display.py` holds the buffer, dBm-to-level quantisation and half-block cell packing with no terminal knowledge; `waterfall_palette.py` maps levels onto the xterm-256 colour cube; `waterfall_pane.py` builds pane-sized cells and draws them through injected curses primitives, so drawing is testable with a fake window.

Each character row shows two waterfall frames using the upper half block with foreground as the upper frame and background as the lower, so a 12-row pane displays 24 frames. Bin reduction to pane width happens at draw time rather than on the way into the buffer, so the buffer keeps full resolution and the pane can be resized without reloading. Drawing groups equal-coloured runs into single curses calls; a 100-cell row of one colour becomes one call rather than 100.

Two constraints found by checking before designing. Curses colour is capped at the terminal's 256-colour palette: `init_extended_pair` is absent from the local Python curses build, so 24-bit colour is unreachable from a curses pane even on a truecolor terminal, and an earlier claim in this session that half blocks would give 24-bit was wrong for the TUI case. And `tui.py` never called `locale.setlocale`, which would have made the half-block glyph render as garbage; that is now set before curses starts. Palette entries come from the 6x6x6 colour cube rather than `init_color`, so terminals that refuse palette changes still work. 24 levels need 576 colour pairs against the 32767 local terminals report.

The pane hides itself rather than failing when the terminal lacks 256 colours, and `draw_waterfall_pane` swallows the curses write error that occurs at the window's last cell rather than unwinding the TUI.

Commands `wf`, `wf load`, `wf scale` and `wf height` are handled in the TUI rather than the controller, because they touch display state only; anything that tunes or streams still belongs to the controller. `handle_tui_key` takes the pane as an optional keyword argument, so existing callers and tests are unaffected and `wf` still falls through to the controller when no pane is passed.

Rebalanced `format_hint_categories_two_columns`. It paired hint blocks by alternating index, which pairs a tall category against a short one and wastes rows; adding one Waterfall category pushed the overview from 25 to 30 lines and broke the existing screen-budget test. It now splits the blocks at the point that balances total column height, which brought the overview to 24 lines including the new category and made the columns read top-to-bottom instead of interleaved.

Live W/F into the pane is deliberately not wired up. `BackgroundOperation` runs one operation at a time and live audio occupies it, so that needs either a second worker slot or an explicit mutually-exclusive policy. Full suite: 357 passed.

Wired a live W/F feed into the TUI waterfall pane. The controller now owns a second `BackgroundOperation` slot, `waterfall_background`, so a live waterfall and live playback run at the same time instead of competing for the single shared worker. That removes the constraint the roadmap had flagged as blocking TUI waterfall integration.

Rows move from the worker thread to the display through a bounded `queue.Queue` on the controller, drained by the TUI on each redraw. Sampling the worker's status metrics instead would have dropped most frames, since W/F arrives at up to 23 fps while the TUI redraws about four times a second. The queue is bounded at 256 rows so a display that stops draining cannot grow without limit; excess rows are dropped rather than blocking the worker.

`LiveWaterfallCaptureConfig.output` is now optional. The live display feed passes `output=None`, which skips the `JsonlCaptureWriter` entirely rather than just skipping the final write, because the writer accumulates every event in memory and this stream runs open-ended. `capture_live_waterfall` returns `Path | None` accordingly. Capture behaviour with an output path set is unchanged.

W/F status metrics now carry `dbm_row`, `x_bin_server` and `flags_x_zoom_server` alongside the existing `ascii_row`, so a display can consume decoded rows without re-parsing payloads.

Retuning to a different zoom changes the bin count mid-feed. The drain helper starts a fresh buffer on a width mismatch rather than refusing the row, so the pane never mixes rows of different spans in one image.

`wf live [zoom] [center_khz]` and `wf stop` are routed from the TUI to the controller, while the display-only subcommands stay local; lifecycle policy remains controller-owned per the architecture rule. `wf live` defaults to zoom 8 at the currently tuned frequency.

Tests use a fake operations layer that emits synthetic rows through the status callback, so the whole path from controller command to pane cells is covered without a receiver. An end-to-end check with synthetic carriers at bins 180, 512 and 790 placed them in pane columns 15, 45 and 69 against predicted 16, 45 and 69, the difference being max-hold correctly catching a deliberate one-bin drift. Full suite: 368 passed.

Not yet confirmed against a live receiver.

Fixed a segfault reported after repeating `wf live 9 910` in the TUI. Diagnosed from the core dump rather than guessed: the crashing thread was `Thread-1 (_run)`, the playback worker, inside `libasound` `snd_pcm_poll_descriptors_revents` via `libportaudio` and cffi, while the main thread was in `_Py_Dealloc`. Signal 11, `SEGV_MAPERR`. Not memory pressure; 9.5 GB was available.

The chain had two independent faults.

First, the trigger. Reissuing `wf live` while a feed was running raised `RuntimeError("background operation already running")` from `BackgroundOperation.start`. The TUI's controller path already caught `RuntimeError` for exactly this reason, added earlier when repeating `:pb` unwound curses, but the new `wf` interception sat before that guard and caught only `ClientCommandError`. So the new command path reintroduced a bug the project had already fixed once.

Second, and worse, the reason it was fatal rather than merely ugly. `run_tui` called `curses.wrapper` with no `try/finally`, so any exception left daemon worker threads running into interpreter shutdown. The playback worker sits in PortAudio/ALSA through cffi; tearing down the interpreter underneath it frees state it is still using. This was a pre-existing latent bug, not something the waterfall work introduced: any unhandled TUI exception with playback active would have done it. Only the orderly `q` path stopped workers.

Fixes: `ClientController.shutdown()` stops and joins every worker, called from a `finally` around `curses.wrapper` so it runs on exception paths too; the `wf` interception now catches `RuntimeError` like the controller path; and `_start_waterfall_background` replaces a running feed instead of refusing, because reissuing `wf live` with a different zoom is how a user changes span, which is precisely what prompted the crash. Stopping or replacing a feed also drains the row queue so stale rows from the previous span cannot appear under the new one.

Regression tests cover the reissue, the RuntimeError reaching the user as a message rather than propagating, shutdown stopping both workers, and `run_tui` shutting workers down when the UI raises. Full suite: 374 passed.

Fixed the live waterfall looking like random speckle with false horizontal banding. The cause was `SET interp=13`, carried since the first spec draft. Reading `rx/rx_waterfall.cpp` in the firmware shows `interp` values of 10 or more enable CIC compensation and have 10 subtracted, with the remainder selecting `wf_interp_t { WF_MAX=0, WF_MIN, WF_LAST, WF_DROP, WF_CMA }`. So 13 was `WF_DROP`, which discards FFT bins instead of combining them; every displayed bin then carried one un-averaged FFT bin's full noise variance. Changed the default to `10`, which is `WF_MAX` plus CIC compensation, matching the receiver's own fallback.

Also confirmed from the same file that the byte to dBm mapping is right: the sender clamps dB to 0..-200 and the client recovers `dBm = byte - 255`, with `wf_cal` already applied at the sender.

Added display auto-ranging, on by default. A fixed dB window cannot serve every zoom, because the noise floor moves by roughly 3 dB per zoom step as bins narrow. The previous fixed -110..-20 default spread 32 levels over 90 dB, 2.8 dB per level, which put a -70 dB floor at level 14, mid palette, so the floor itself rendered as green and yellow and per-frame noise flickered a level either way. `auto_scale_dbm()` anchors the low end just below the measured floor percentile so the floor stays dark. `wf auto [off]` toggles it, and an explicit `wf scale` turns it off so a manual choice is not overwritten on the next redraw. Full suite: 390 passed.

Found the waterfall banding. It was neither the data nor the cell computation: `curses.color_pair()` packs the pair number into the 8-bit `A_COLOR` field, `0xFF00` here, so only pairs 1..255 are addressable. With 32 levels a half-block cell needs `1 + 32*32 = 1025` pairs, and every pair above 255 silently wrapped to `number & 0xFF`, selecting an unrelated pair.

The wedge test pattern made it obvious. For a wedge `upper == lower == L`, so the pair is `1 + 33L`: levels 0..7 give 1..232 and rendered correctly, which is why the left third of the wedge was clean. Level 8 gives 265, which masks to 9, and pair 9 is `(upper=0, lower=8)`, so those cells drew a black top half over a coloured bottom half. That is exactly the black horizontal striping, beginning exactly where the arithmetic says it should.

The guard in `init_waterfall_pairs` had been checking `curses.COLOR_PAIRS`, which the local terminals report as 32767 or 65536. That is the terminfo capability, not what `color_pair()` can address; reaching it needs `init_extended_pair`, which this Python curses build does not provide. That absence had been noted earlier in the session but never connected to the pair budget, so the guard validated against a number three orders of magnitude too large and passed.

Levels are now 15, needing 226 pairs, and the guard checks the addressable ceiling regardless of what the terminal advertises. The cost is 13 distinct colours instead of 18. Tests now assert that no two registered pairs collide after 8-bit masking, which is the property that actually broke.

Ruled out first, and worth keeping on record: the cell computation is correct, since constant input yields identical cells, a vertical ramp yields a monotonic sequence, and a horizontal wedge is byte-identical across character rows; and the captured fixtures show no frame-to-frame alternation, with mean lag-1 and lag-2 median differences within 10 percent.

## YYYY-MM-DD

### Finding

### Decision

### Test result

### Follow-up
