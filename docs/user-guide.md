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

- Keymap mode is the default.
- `:` enters command mode.
- In command mode, `Enter` executes the command and returns to keymap mode.
- In command mode, `Esc` clears the command and returns to keymap mode.
- In command mode, up/down arrows browse command history; the selected command is placed in the prompt for editing.

Default TUI keymap/step configuration shape:

```toml
[steps]
small_hz = 100
medium_hz = 1000
large_hz = 5000

[volume]
step_percent = 10

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

With that setting, `:pb --null-sink` is accepted as `play-bg --null-sink` using the configured live opt-in. Without it, live operations still require `--allow-live` on each command.

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
- `tune <frequency_khz>`
- `mode <mode> [low_cut_hz high_cut_hz]`
- `filter <low_cut_hz> <high_cut_hz>`
- `tune-step <+/-hz|small|medium|large>`
- `volume <percent>`
- `volume-step <delta_percent>`
- `agc [on|off|hang on|off|threshold <value>|slope <value>|decay <ms>|gain <value>|set key=value ...]`
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

Current limitations:

- `connect` and `disconnect` only update client state for now.
- Live operations from the shell require explicit `--allow-live`.
- TUI is an initial curses command/dashboard shell, not a full SDR interface yet.
- RSSI/S-meter display is a simple latest-value readout from SND frames, not a calibrated meter widget.
- `volume` / `volume-step` control local system output volume via common Linux mixer tools (`wpctl`, `pactl`, then `amixer`). The local `kiwiclient` reference has verified `SET agc=...` receiver-side gain control, but no verified Kiwi radio-side volume command.
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

While a background SND operation is running, `operation-status` and the TUI dashboard show latest RSSI/S-meter/SND frame metrics after the first SND frame arrives. The dashboard also shows sample rate, sequence gap count, and ADC overflow count when available. The TUI refreshes periodically, so these fields and background operation errors update without requiring a keypress.

During background playback, these parameter changes queue `SET mod=...` to the active playback WebSocket after the initial Kiwi SND setup has completed:

```text
tune 7000
mode usb 300 2700
filter 100 2400
```

The dashboard response includes `Applied to active stream: ...` when a control command is queued.

Expected next operations:

- Add live status/error display.
- Add persistent session lifecycle.

## Waterfall

TBD.

Expected operations:

- Show waterfall
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
