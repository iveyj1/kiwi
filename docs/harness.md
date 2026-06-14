# KiwiSDR Harness

## Purpose

The harness allows development and regression testing without requiring live KiwiSDR hardware.

## Required capabilities

### Fixture replay

Replay captured KiwiSDR stream data into the client.

Use for:

- Protocol parser tests
- Audio pipeline tests
- Waterfall tests
- Regression tests

### Capture

Capture short live sessions from local receivers into fixture files.

Record:

- Receiver
- Date/time
- Stream type
- Frequency
- Mode
- KiwiSDR version if available
- Commands sent
- Frames received
- Notes

### Synthetic signal generation

Generate known audio/IQ data for detector tests.

Use for:

- Carrier detection
- Morse/NDB ID detection
- SNR threshold tests
- Frequency offset tests
- Fading/noise tests
- Long integration tests

## Fixture policy

Fixtures should be small unless intentionally marked as large.

Normal unit/regression fixtures should run quickly.

Long captures belong under a separate large-data directory or external dataset path.

## Suggested fixture formats

### JSONL control/session fixture

Each line is one event:

```json
{"t":0.000,"dir":"tx","stream":"snd","type":"cmd","text":"SET ..."}
{"t":0.025,"dir":"rx","stream":"snd","type":"msg","text":"MSG ..."}
{"t":0.041,"dir":"rx","stream":"snd","type":"binary","encoding":"base64","data":"..."}
```

### Binary payload fixture

For larger stream captures:

```text
fixture-name.jsonl      metadata and event index
fixture-name.bin        concatenated binary payloads
```

The JSONL file should contain byte offsets and lengths into the binary file.

## First SND capture plan, after harness gate passes

Do not run this until command encoding and parser fixture tests pass.

Planned purpose: capture a short local SND session fixture that validates the synthetic command/session assumptions against a local receiver.

Preconditions:

- `python3 -m pytest tests/harness tests/protocol` passes.
- Use only `10.0.0.40:8073`; fallback to `10.0.0.41:8073` only if max users/busy.
- No admin commands.
- No reconnect loop.
- Short, attended capture only.

Planned SND setup:

1. Open an SND WebSocket session.
2. Send `SET auth t=kiwi p=`.
3. Apply the fixture-tested setup command sequence from `tests/fixtures/kiwi/snd-setup-commands.jsonl`.
4. Request `SET compression=0` so captured audio matches the first uncompressed PCM parser.
5. Capture initial `MSG` metadata and a small number of SND frames.
6. Stop and write a JSONL fixture with receiver, UTC/local time, frequency, mode, filter, command sequence, frame count, and notes.

Initial proposed settings:

- Frequency: `4625.000` kHz
- Mode: `am`
- Filter: `-4900..4900` Hz
- AGC: default on
- Compression: off
- Duration: a few frames / under 5 seconds

## Live-to-fixture workflow

1. Reproduce behavior on local receiver.
2. Capture short fixture.
3. Add failing or covering test.
4. Fix implementation.
5. Confirm fixture test passes.
6. Retest live only if needed.
