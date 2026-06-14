# User Guide

This file should describe user-visible behavior as the application develops.

## Basic client

TBD.

Expected early operations:

- Connect to receiver
- Disconnect from receiver
- Select frequency
- Select mode
- Start/stop audio playback
- View status/errors

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

Current playback limitations:

- no real audio-device output yet,
- dry-run uses `NullAudioSink` and reports frames/chunks/bytes,
- intended next backend is likely `sounddevice`, but not selected/finalized.

## Beacon detection

TBD.

Expected operations:

- Select frequency range or target
- Run detector
- View detections
- Export event log
