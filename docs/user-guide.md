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

Expected later operations:

- Start manual recording
- Stop recording
- Select destination
- View recording metadata

## Beacon detection

TBD.

Expected operations:

- Select frequency range or target
- Run detector
- View detections
- Export event log
