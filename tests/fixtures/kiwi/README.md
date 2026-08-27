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

## Captured W/F regression fixtures

- `local-wf-5000-zoom0.jsonl`: two full-band frames from `10.0.0.40:8073`; covers zoom-0 layout and repeated sequence zero.
- `local-wf-am-855-zoom7.jsonl`: five frames centered near 855 kHz at zoom 7 and speed 4; covers nonzero start/zoom mapping and known local carriers near 760 and 950 kHz.

## Policy

Keep ordinary regression fixtures small.

Do not require live radio for normal tests.
