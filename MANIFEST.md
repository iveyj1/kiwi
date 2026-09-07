# Scaffold Manifest

## Root

- `AGENTS.md` — project instructions for Pi Coding Agent.
- `TODO.md` — current status and next-slice tracker.
- `MANIFEST.md` — repository file map.
- `pyproject.toml` — Python package metadata, optional dependencies, and CLI entry points.
- `config.toml` — local working configuration.
- `presets.toml` — durable local radio and receiver presets.

## Docs

- `docs/project-brief.md` — project purpose and staged experiments.
- `docs/architecture.md` — separation of transport, protocol, audio, waterfall, UI, detector.
- `docs/kiwi-protocol.md` — local protocol record.
- `docs/harness.md` — fixture/replay/capture rules.
- `docs/radio-lab.md` — local receiver notes and live-test log.
- `docs/test-plan.md` — test strategy.
- `docs/user-guide.md` — user-visible behavior record.
- `docs/dev-log.md` — lightweight project memory.
- `docs/audio-pipeline.md` — audio pipeline notes.
- `docs/waterfall-rendering.md` — waterfall pipeline notes.
- `docs/beacon-detection.md` — MF/LF beacon detection notes.

## Pi

- `.pi/skills/kiwisdr-client/SKILL.md` — KiwiSDR development skill.
- `.pi/prompts/slice.md` — small work-slice prompt.
- `.pi/prompts/protocol-spike.md` — protocol investigation prompt.
- `.pi/prompts/harness-test.md` — fixture/regression prompt.
- `.pi/prompts/live-radio-test.md` — controlled local live-test prompt.
- `.pi/prompts/review-slice.md` — review prompt.
- `.pi/prompts/fixture-capture.md` — fixture capture prompt.

## Data

- `data/kiwi-public-receivers-2026-09-07.json` — timestamped structured export of 872 online public KiwiSDRs, including SNR and preserved directory metadata.

## Source

- `src/kiwi_client/` — package code for protocol, transport, SND audio, recording, TUI, live workers, and waterfall rendering.
- `src/kiwi_client/public_directory.py` — public-directory click-through fetch and deterministic HTML parser.
- `tools/scrape_kiwi_public.py` — export live or saved public-directory HTML as structured JSON.
- `tools/waterfall_image.py` — optional static PNG inspection helper for W/F fixtures.

## Tests

- `tests/harness/test_public_directory.py` — synthetic directory parser coverage for identity, location, SNR, occupancy, GPS, and preserved metadata.
- `tests/fixtures/kiwi/README.md` — fixture conventions.
- `tests/fixtures/kiwi/snd-basic.jsonl` — placeholder SND fixture.
- `tests/fixtures/kiwi/wf-basic.jsonl` — placeholder waterfall fixture.
- `tests/fixtures/kiwi/protocol-notes.md` — fixture-local protocol notes.
- `tests/fixtures/kiwi/synthetic-beacons/README.md` — synthetic detector fixture notes.
- `tests/protocol/README.md`
- `tests/harness/README.md`
- `tests/audio/README.md`
- `tests/waterfall/README.md`
- `tests/detection/README.md`
