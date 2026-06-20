# User Guide

This file should describe user-visible behavior as the application develops.

## Basic client

The first basic client is a scriptable command shell. It manages client state and can produce dry-run plans for guarded live operations without connecting.

Run interactively as a command shell:

```bash
PYTHONPATH=src python3 -m kiwi_client.client_app --json
```

Run the curses TUI:

```bash
PYTHONPATH=src python3 -m kiwi_client.tui
```

Optionally pass a TOML configuration file:

```bash
PYTHONPATH=src python3 -m kiwi_client.tui --config ~/.config/kiwi-client/config.toml
```

TUI input has two modes:

- The TUI shows which-key style context hints above the prompt.
- In keymap mode, hints list available configured keys with short action descriptions.
- In command mode, hints group top-level commands by category in two columns with shortcuts before full command names, e.g. `tu (tune)`; typed text filters the list.
- Once the active text uniquely identifies a command, hints keep that command visible and show usage/sub-options.
- For semicolon-separated command entries, hints follow the current command segment after the last unquoted semicolon.
- Command entries may contain multiple commands separated by semicolons, e.g. `:tu 7000; mo usb 300 2700; fi 100 2400`.
- Semicolons inside quoted arguments are preserved.
- Batches containing only radio/state commands are validated before state is changed; if one command is invalid the earlier commands in that batch are not applied. Mixed batches containing live start/stop operations execute sequentially and stop at the first error.
- Keymap mode is the default.
- `:` enters command mode.
- In command mode, `Enter` executes the command and returns to keymap mode.
- In command mode, `Esc` clears the command and returns to keymap mode.
- In command mode, up/down arrows browse command history; the selected command is placed in the prompt for editing.
- In keymap mode, `q` requests cooperative stop of any background operation before exiting the TUI.
- In keymap mode, prefix sequences manage presets and receiver switching: `p <register>` recalls a preset, `s <register>` stores frequency/mode/bandwidth, `S <register>` stores all radio parameters, and `r <receiver>` switches to a stored or configured receiver while preserving radio parameters. Registers are `0..9` or `a..z`; receiver registers come from `add-receiver` entries first, then `[receivers].allowed` order. After pressing a prefix key, hints show defined preset registers with frequency/mode or receiver registers with addresses/descriptions.

Default TUI keymap/step configuration shape:

```toml
[steps]
small_hz = 100
medium_hz = 1000
large_hz = 5000

[volume]
step_percent = 10

[audio]
# Drop/fade decoded live playback audio to hide receiver/audio startup transients.
startup_mute_ms = 100
startup_fade_in_ms = 50
stop_fade_out_ms = 50

[live]
# Default is false. Set true only for trusted local interactive use.
allow_live = false
# 0 means unlimited. Defaults remain bounded.
duration_seconds = 60
max_frames = 1500

[receivers]
# Default is restricted to local receivers.
restricted = true
allowed = ["10.0.0.40:8073", "10.0.0.41:8073"]

[startup]
# mode can be "last", "default", or "preset".
mode = "last"
preset = 1
state_file = "~/.local/state/kiwi-client/state.json"
# Start background playback when [live].allow_live is true.
playback = true

[default_state]
host = "10.0.0.40"
port = 8073
frequency_khz = 5000.0
mode = "am"
low_cut_hz = -5000
high_cut_hz = 5000

[keys]
"right" = "tune-step +medium"
"l" = "tune-step +medium"
"left" = "tune-step -medium"
"h" = "tune-step -medium"
"up" = "volume-step +10"
"k" = "volume-step +10"
"down" = "volume-step -10"
"j" = "volume-step -10"
":" = "command-mode"
```

In keymap mode, the default bindings are:

- right arrow or `l`: increase frequency by the configured medium step.
- left arrow or `h`: decrease frequency by the configured medium step.
- uppercase `L` / `H`: increase/decrease by the configured small step.
- Ctrl+`l` / Ctrl+`h`: increase/decrease by the configured large step where the terminal reports those control keys distinctly.
- up arrow or `k`: increase volume by the configured volume step.
- down arrow or `j`: decrease volume by the configured volume step.

Terminal support for modified arrow keys varies; letter bindings are the portable fallback. Unknown modified-key escape sequences are ignored in keymap mode. If curses reports shift-arrow keys distinctly, shift-right/shift-left use the configured small frequency step.

If you want TUI command aliases like `:pb` to start live operations without typing `--allow-live` every time, explicitly opt in via your TUI config:

```toml
[live]
allow_live = true
```

With that setting, `:pb --null-sink` is accepted as `play-bg --null-sink` using the configured live opt-in. Without it, live operations still require `--allow-live` on each command. If `[startup] playback = true` is also set, the TUI starts background playback automatically at startup using the restored/default radio state.

Configured live limits can be made unlimited by setting either value to `0`:

```toml
[live]
duration_seconds = 0
max_frames = 0
```

Receiver restrictions can be changed with:

```toml
[receivers]
restricted = true
allowed = ["10.0.0.40:8073", "10.0.0.41:8073"]
```

or explicitly disabled for unrestricted receiver addresses:

```toml
[receivers]
restricted = false
```

Use unrestricted mode carefully; project live-radio practice still prefers local receivers unless explicitly needed.

For long-running live playback/record/capture, the client sends periodic SND keepalives after initial setup. If a session still stops unexpectedly, check the TUI operation result/error and confirm both `duration_seconds` and `max_frames` are `0` if you intend no client-side limit.

Live playback drops the first `[audio].startup_mute_ms` of decoded PCM after each playback start while still updating SND metrics, then fades in over `[audio].startup_fade_in_ms`. Cooperative playback stops fade out over `[audio].stop_fade_out_ms` when frames are still arriving. This is intended to hide short receiver/audio startup and switch transients.

If playback appears active but you hear no audio, check the local output volume because `volume` / `volume-step` now operate on the system mixer. From command mode you can try `:volume 50`, and outside the app check the selected output device/mute state with your desktop audio controls or `wpctl`/`pactl`.

or, after installing the package scripts:

```bash
kiwi-tui
```

Run a script:

```bash
cat > /tmp/kiwi-client-script.txt <<'EOF'
status
tune 5000
mode am -5000 5000
duration 60
frames 1500
dashboard
play-plan
play --allow-live --null-sink
record-plan recordings/client-5000-am.wav
record recordings/client-5000-am.wav --allow-live --overwrite
capture-plan tests/fixtures/kiwi/client-5000-am.jsonl
capture tests/fixtures/kiwi/client-5000-am.jsonl --allow-live --overwrite
quit
EOF

PYTHONPATH=src python3 -m kiwi_client.client_app \
  --script /tmp/kiwi-client-script.txt \
  --json
```

Supported commands:

- `status`
- `connect` / `disconnect` (state only; no persistent receiver session yet)
- `receiver <host>[:port]`
- `add-receiver <receiver-register> <ip/url[:port]> <description>`
- `tune <frequency_khz>`
- `mode <mode> [low_cut_hz high_cut_hz]`
- `filter <low_cut_hz> <high_cut_hz>`
- `tune-step <+/-hz|small|medium|large>`
- `volume <percent>`
- `volume-step <delta_percent>`
- `agc [on|off|hang on|off|threshold <value>|slope <value>|decay <ms>|gain <value>|set key=value ...]`
- `store <n>`
- `store all <n>`
- `recall <n>`
- `duration <seconds>`
- `frames <max_snd_frames>`
- `dashboard`
- `play-plan`
- `play --allow-live [--null-sink]`
- `play-bg --allow-live [--null-sink]`
- `stop`
- `wait [seconds]`
- `operation-status`
- `record-plan <output.wav>`
- `record <output.wav> --allow-live [--overwrite]`
- `record-bg <output.wav> --allow-live [--overwrite]`
- `capture-plan <output.jsonl>`
- `capture <output.jsonl> --allow-live [--overwrite]`
- `capture-bg <output.jsonl> --allow-live [--overwrite]`
- `help`
- `quit`

Command aliases:

- `?` -> `status`
- `re` -> `receiver`
- `ad` -> `add-receiver`
- `tu` -> `tune`
- `mo` -> `mode`
- `fi` -> `filter`
- `du` -> `duration`
- `fr` -> `frames`
- `pb` -> `play-bg`
- `rb` -> `record-bg`
- `cb` -> `capture-bg`
- `sp` -> `stop`
- `he` -> `help`
- `q` / `qu` -> `quit`

AGC commands use the locally verified KiwiSDR command shape `SET agc=<0|1> hang=<0|1> thresh=<n> slope=<n> decay=<ms> manGain=<n>`. Examples:

```text
agc on
agc off
agc hang on
agc threshold -95
agc slope 5
agc decay 750
agc gain 40
agc set on=true hang=false thresh=-100 slope=6 decay=1000 gain=50
```

During active background playback, AGC changes are queued to the active SND WebSocket.

Presets:

```text
store 1        # receiver/frequency/mode/filter only
store all a    # full client/radio state in letter register a
recall a
```

In keymap mode, press `s1`, `Sa`, or `pa` for the same store/store-all/recall operations. After `p`, `s`, or `S`, defined preset registers are shown with frequency and mode. Add stored receiver registers with `add-receiver 2 10.0.0.42:8073 Backup receiver` or alias `ad a http://10.0.0.42:8073/ Backup receiver`; URL-like addresses are normalized to `host:port`. When the TUI was started with `--config`, newly added receivers are appended to `[receivers].allowed` if not already present. Receiver prefix `r <receiver>` switches to a stored receiver if the register is defined, otherwise to `[receivers].allowed` using register order `0..9,a..z`, while preserving frequency/mode/filter and other radio parameters; after `r`, hints show receiver registers sorted by register with addresses/descriptions. If background playback is active, the TUI stops it and restarts playback on the selected receiver. If playback had already failed, for example because the current receiver was busy, `r <receiver>` switches receiver and starts playback on the selected receiver. If the new receiver fails immediately, such as reporting busy, the TUI restores the previous receiver, restarts playback there when possible, and shows the failure message. The TUI persists the last full state, presets, and stored receivers to `[startup].state_file` on safe exit. On restart, `[startup].mode` controls whether to use `last`, `default`, or a configured `preset`.

Current limitations:

- `connect` and `disconnect` only update client state for now.
- Live operations from the shell require explicit `--allow-live`.
- TUI is an initial curses command/dashboard shell, not a full SDR interface yet.
- RSSI/S-meter display is a simple latest-value readout from SND frames, not a calibrated meter widget.
- `volume-step` reads the current system output volume before applying its delta, then sets the new local system volume via common Linux mixer tools (`wpctl`, `pactl`, then `amixer`). The local `kiwiclient` reference has verified `SET agc=...` receiver-side gain control, but no verified Kiwi radio-side volume command.
- `connect` is not a continuously open retunable WebSocket session yet.

Example shell commands for persistent live settings and guarded execution:

```text
duration 60
frames 1500
play --allow-live --null-sink
record recordings/client-5000-am.wav --allow-live --overwrite
capture tests/fixtures/kiwi/client-5000-am.jsonl --allow-live --overwrite
```

Example background playback from the shell/TUI:

```text
play-bg --allow-live --null-sink
tune 7000
operation-status
stop
wait 2
operation-status
```

Example background record/capture from the shell/TUI:

```text
record-bg recordings/client-5000-am.wav --allow-live --overwrite
operation-status
stop
wait 2

capture-bg tests/fixtures/kiwi/client-5000-am.jsonl --allow-live --overwrite
operation-status
stop
wait 2
```

While a background SND operation is running, `status`, `operation-status`, and the TUI dashboard report the client as connected. The dashboard shows latest RSSI/S-meter/SND frame metrics after the first SND frame arrives. It also shows sample rate, sequence gap count, and ADC overflow count when available. The TUI refreshes periodically, so these fields and background operation errors update without requiring a keypress.

If the Kiwi reports `too_busy`, `badp=1`, or `down`, the live operation error shows an explicit server busy/down message instead of a generic failure.

During background playback, these parameter changes queue `SET mod=...` to the active playback WebSocket after the initial Kiwi SND setup has completed:

```text
tune 7000
mode usb 300 2700
filter 100 2400
```

A semicolon-separated radio batch queues active playback control commands only after the whole batch validates. For modulation-related changes, the active stream receives one final `SET mod=...` for the final state; AGC changes receive a final `SET agc=...` when included.

```text
:tu 7000; mo usb 300 2700; fi 100 2400; agc gain 35
```

The dashboard response includes `Applied to active stream: ...` for each queued control command.

Expected next operations:

- Add live status/error display.
- Add persistent session lifecycle.

## Waterfall

The current waterfall path is offline and harness-first. Synthetic or captured W/F JSONL fixtures can be rendered as deterministic ASCII rows:

```bash
PYTHONPATH=src python3 -m kiwi_client.waterfall_preview tests/fixtures/kiwi/wf-basic.jsonl
```

Installed script name:

```bash
kiwi-wf-preview tests/fixtures/kiwi/wf-basic.jsonl
```

This preview command does not connect to a receiver.

For test-rig visual inspection, a non-production matplotlib helper can render a static PNG from a fixture:

```bash
PYTHONPATH=src python3 tools/waterfall_image.py \
  tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl \
  artifacts/local-wf-5000-zoom0.png \
  --summary \
  --title "Local W/F 5000 kHz zoom 0"
```

Guarded short local W/F capture is available behind `--allow-live`:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_waterfall \
  --dry-run \
  --host 10.0.0.40 \
  --output tests/fixtures/kiwi/local-wf-capture.jsonl
```

Actual short capture, only when explicitly intended:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_waterfall \
  --allow-live \
  --host 10.0.0.40 \
  --output tests/fixtures/kiwi/local-wf-capture.jsonl
```

A standalone guarded live ASCII preview is also available:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_waterfall_preview \
  --allow-live \
  --host 10.0.0.40 \
  --max-frames 5
```

Installed script names:

```bash
kiwi-wf-capture --allow-live --host 10.0.0.40 --output tests/fixtures/kiwi/local-wf-capture.jsonl
kiwi-wf-live --allow-live --host 10.0.0.40 --max-frames 5
```

Expected future operations:

- Show live waterfall inside the TUI or richer UI
- Tune by cursor or control input
- Adjust span/zoom if supported

## Recording / fixture capture

The first user-visible capture tool is guarded and intended for short local fixture captures, not unattended recording.

Dry-run, no network:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_capture \
  --dry-run \
  --host 10.0.0.40 \
  --output tests/fixtures/kiwi/local-snd-capture.jsonl
```

Actual live capture, only when explicitly intended:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_capture \
  --allow-live \
  --host 10.0.0.40 \
  --output tests/fixtures/kiwi/local-snd-capture.jsonl
```

Guardrails:

- local receivers only,
- live duration capped at 60 seconds,
- live SND frames capped at 1500,
- defaults remain short unless longer values are explicitly requested,
- no admin commands,
- compression off for first SND PCM fixture path,
- no output overwrite unless requested.

Offline fixture-to-WAV recording is available from the CLI:

```bash
PYTHONPATH=src python3 -m kiwi_client.recorder \
  tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl \
  recordings/local-snd-5000-am-10khz.wav \
  --json
```

Or from Python:

```bash
PYTHONPATH=src python3 - <<'PY'
from kiwi_client.recorder import write_snd_fixture_wav
result = write_snd_fixture_wav(
    'tests/fixtures/kiwi/local-snd-5000-am-10khz.jsonl',
    'recordings/local-snd-5000-am-10khz.wav',
)
print(result)
PY
```

Direct guarded SND-to-WAV recording is available as a dry-run plan:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_record \
  --dry-run \
  --host 10.0.0.40 \
  --frequency-khz 5000 \
  --mode am \
  --low-cut-hz -5000 \
  --high-cut-hz 5000 \
  --output recordings/live-5000-am.wav
```

Actual direct live recording, only when explicitly intended:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_record \
  --allow-live \
  --host 10.0.0.40 \
  --frequency-khz 5000 \
  --mode am \
  --low-cut-hz -5000 \
  --high-cut-hz 5000 \
  --duration-seconds 60 \
  --max-frames 1500 \
  --output recordings/live-5000-am.wav \
  --json
```

Current recording limitations:

- uncompressed mono SND only,
- guarded sessions only, capped at 60 seconds / 1500 SND frames,
- no compressed ADPCM,
- no stereo/IQ,
- sample rate is rounded to integer Hz for the WAV header,
- direct live recording does not yet save a JSONL sidecar automatically.

Expected later operations:

- Start manual recording
- Stop recording
- Select destination
- View recording metadata

## Playback

Playback scaffolding is available in dry-run mode for WAV files:

```bash
PYTHONPATH=src python3 -m kiwi_client.playback \
  recordings/local-snd-5000-am-10khz.wav \
  --dry-run \
  --json
```

Live SND playback dry-run plan:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_play \
  --dry-run \
  --host 10.0.0.40 \
  --frequency-khz 5000 \
  --mode am \
  --low-cut-hz -5000 \
  --high-cut-hz 5000
```

Live SND playback with audio output, only when explicitly intended:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_play \
  --allow-live \
  --host 10.0.0.40 \
  --frequency-khz 5000 \
  --mode am \
  --low-cut-hz -5000 \
  --high-cut-hz 5000 \
  --duration-seconds 60 \
  --max-frames 1500 \
  --json
```

Live SND playback with receiver connection but no audio-device output:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_play \
  --allow-live \
  --null-sink \
  --host 10.0.0.40 \
  --frequency-khz 5000 \
  --mode am \
  --low-cut-hz -5000 \
  --high-cut-hz 5000 \
  --json
```

Current playback limitations:

- uncompressed mono SND only,
- guarded sessions only, capped at 60 seconds / 1500 SND frames,
- no compressed ADPCM,
- no stereo/IQ,
- no user-facing audio device selector yet,
- buffering and underflow/overflow diagnostics are minimal.

## Beacon detection

TBD.

Expected operations:

- Select frequency range or target
- Run detector
- View detections
- Export event log
