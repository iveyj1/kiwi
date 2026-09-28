# KiwiSDR Harness

## Purpose

The harness allows development and regression testing without requiring live KiwiSDR hardware.

## Standalone logbook / WWSU review regressions

`tests/fixtures/wwsu/` contains synthetic exported table data and a report, not
personal logs or a bundled Access executable. `test_log_browser.py` and
`test_wwsu_reports.py` cover read-only native SQLite (including WAL), source-isolated
refresh caches, stable record references/revisions, snapshot reconciliation,
personal IDs, same-minute multiplicity, older-only rows, report comments/units and
frequency conflicts. Pure loader/filter tests need no Qt or external MDBTools.
The optional PySide6 test uses the offscreen platform to exercise the real table,
sorting/filtering, station history, reload and noneditable cells; source hashes stay
unchanged. Actual MDBTools extraction was separately checked against the local archive.

```bash
PYTHONPATH=src /home/user/kiwi/.kiwi-venv/bin/python -m pytest -q \
    tests/harness/test_log_browser.py tests/harness/test_wwsu_reports.py
./logbook --dry-run
```

## Pixel-native graphical scale regressions

`tests/fixtures/terminal/pixel-geometry.json` contains synthetic TIOCGWINSZ cases
for 80/174 columns, different heights/DPI, missing pixels and stale cell dimensions.
`tests/harness/test_native_scale_pixels.py` checks exact pane dimensions, identical
bitmap/FreeType glyph pixels across window sizes, final RF marker coordinates,
nearest-neighbour fallback parity, short panes, and repainting after pixel changes.
A fixture-shell resize test verifies native canvases without retuning. No radio or
physical-terminal measurements are required by these tests.

```bash
python -m pytest tests/harness/test_native_scale_pixels.py -q
```

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

## Offline capture writer

The future live capture path should use the same JSONL event shape as the tests. `src/kiwi_client/capture.py` provides an offline `JsonlCaptureWriter` that records:

- one metadata event with receiver/time/frequency/mode/filter/compression fields,
- transmitted command events,
- received `MSG` text events,
- received binary WebSocket payload events encoded as base64.

`tests/harness/test_capture_writer.py` round-trips writer output through the fixture loader, MSG parser, receiver state, and SND audio parser. This is the expected file shape for the first short local capture when live-radio testing is explicitly started.

## Offline replay transport

`src/kiwi_client/transport.py` includes `ReplayTransport`, a strict no-network transport for fixture scripts:

- `send(text)` consumes the next event and requires it to be a matching `tx`/`cmd`.
- `receive()` consumes the next event and returns a received `MSG` text or binary payload.
- Any command mismatch, wrong direction, unsupported type, or exhausted fixture raises `ReplayTransportError`.

Use this before live testing to validate that setup commands and expected responses are in the intended order.

## Guarded SND capture CLI

`src/kiwi_client/live_capture.py` provides the guarded capture tool for the first future local receiver fixture.

Dry-run only, no network:

```bash
PYTHONPATH=src python3 -m kiwi_client.live_capture \
  --dry-run \
  --host 10.0.0.41 \
  --output tests/fixtures/kiwi/local-snd-capture.jsonl
```

Live execution is intentionally gated:

- receiver must be one of `10.0.0.41:8073`, `10.0.0.42:8073`, or `10.0.0.43:8073`,
- duration must be at most 5 seconds,
- frame cap must be at most 100,
- output file must not already exist unless `--overwrite` is supplied,
- compression is fixed off for the first capture path,
- `--allow-live` is required for any network connection,
- optional dependency `websockets` is required for actual live use (`pip install '.[live]'`).

This implementation has only been tested in dry-run/guardrail mode so far.

## First SND capture plan, after harness gate passes

Do not run this until command encoding, parser fixture tests, and dry-run capture guard tests pass.

Planned purpose: capture a short local SND session fixture that validates the synthetic command/session assumptions against a local receiver.

Preconditions:

- `python3 -m pytest tests/harness tests/protocol` passes.
- Use `10.0.0.41:8073`; fall back to `10.0.0.42:8073` or `10.0.0.43:8073` if max users/busy.
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
