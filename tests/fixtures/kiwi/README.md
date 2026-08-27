# KiwiSDR Fixtures

Fixtures live here so protocol, audio, waterfall, recording, and detection behavior can be tested without live receivers.

## Naming

Use descriptive names:

```text
snd-basic.jsonl
snd-frequency-mode-change.jsonl
wf-basic.jsonl
snd-max-users.jsonl
beacon-synthetic-weak-carrier.jsonl
```

## Suggested JSONL event format

```json
{"t":0.000,"dir":"tx","stream":"snd","type":"cmd","text":"..."}
{"t":0.025,"dir":"rx","stream":"snd","type":"msg","text":"..."}
{"t":0.041,"dir":"rx","stream":"snd","type":"binary","encoding":"base64","data":"..."}
```

## Metadata to include

Each real capture should document:

- Receiver address
- Local and/or UTC time
- Frequency
- Mode
- Filter
- Stream type
- Commands sent
- Frame counts
- Capture duration
- Why the fixture exists

## Local W/F captures

Real captures use `local-wf-<center_khz>-zoom<zoom>.jsonl`. The name must match the
`center_khz` and `zoom` recorded in the fixture's own `dir="meta"` first line; if a
capture is re-run with different settings, rename the file to match.

| Fixture | Receiver | Center | Zoom | Frames | Why it exists |
| --- | --- | --- | --- | --- | --- |
| `local-wf-5000-zoom0.jsonl` | `10.0.0.40:8073` | 5000 kHz | 0 | 2 | First real W/F capture; full 30 MHz span. |
| `local-wf-910-zoom8.jsonl` | `10.0.0.40:8073` | 910 kHz | 8 | 60 | Bin/frequency calibration against AM carriers 860-960 kHz. |
| `local-wf-760-zoom9.jsonl` | `10.0.0.40:8073` | 760 kHz | 9 | 60 | Independent calibration check at a different zoom, 740-780 kHz. |

The two zoomed captures back `tests/waterfall/test_frequency_mapping.py`. They are
larger than the "keep fixtures small" rule would normally allow, because the
calibration needs many frames and real carriers across a wide window. Do not
replace them without re-running that test.

## Policy

Keep ordinary regression fixtures small.

Do not require live radio for normal tests.
