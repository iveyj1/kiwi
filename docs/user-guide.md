# User Guide

This file should describe user-visible behavior as the application develops.

## Basic client

The first basic client is a scriptable command shell. It manages client state and can produce dry-run plans for guarded live operations without connecting.

Run interactively:

```bash
PYTHONPATH=src python3 -m kiwi_client.client_app --json
```

Run a script:

```bash
cat > /tmp/kiwi-client-script.txt <<'EOF'
status
tune 5000
mode am -5000 5000
play-plan
record-plan recordings/client-5000-am.wav
capture-plan tests/fixtures/kiwi/client-5000-am.jsonl
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
- `play-plan`
- `record-plan <output.wav>`
- `capture-plan <output.jsonl>`
- `help`
- `quit`

Current limitations:

- `connect` and `disconnect` only update client state for now.
- Plans do not execute live operations from inside the shell yet.
- No live RSSI/sample-rate/status display yet.
- No TUI yet.

Expected next operations:

- Execute guarded playback/record/capture from the shell.
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
- short capture only,
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
  --output recordings/live-5000-am.wav \
  --json
```

Current recording limitations:

- uncompressed mono SND only,
- short guarded sessions only,
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
  --duration-seconds 5 \
  --max-frames 60 \
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
- short guarded sessions only,
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
