---
name: kiwisdr-client
description: Use for KiwiSDR client, protocol, harness, audio, waterfall, recording, and MF/LF beacon detection work. Enforces harness-first development and local-radio testing rules.
---

# KiwiSDR Client Skill

## First steps

For KiwiSDR work, inspect these first:

1. `AGENTS.md`
2. `docs/project-brief.md`
3. `docs/architecture.md`
4. `docs/kiwi-protocol.md`
5. `docs/harness.md`
6. `kiwiclient/`

## Mandatory rule

Harness first, live radio second.

Do not use live KiwiSDR tests as the first validation step unless explicitly requested.

## Protocol work

When protocol behavior is discovered or changed, update `docs/kiwi-protocol.md`.

Record:

- Message/frame type
- Direction
- Fields
- Units
- Timing
- Source of evidence
- Fixture covering behavior
- Failure behavior

## Audio work

Audio behavior must be testable from fixtures or synthetic samples.

Check:

- Sample rate
- Sample format
- Endianness
- Buffering
- Dropout behavior
- Latency assumptions
- Playback underflow/overflow handling

## Waterfall work

Waterfall behavior must be testable from fixed frames.

Check:

- Frame dimensions
- Bin mapping
- Frequency span
- Scaling
- Color/intensity mapping
- Update rate assumptions

## Beacon detection work

Detection must be validated on synthetic signals before live captures.

Test at minimum:

- Known carrier present
- Known carrier absent
- Frequency offset
- Noise floor change
- Fading
- Weak signal near threshold
- False positive case

## Live radio

Local receivers:

- `10.0.0.40:8073`
- `10.0.0.41:8073`

Use `10.0.0.41:8073` if `10.0.0.40:8073` has max users.

After useful live observations, create or update a fixture.
