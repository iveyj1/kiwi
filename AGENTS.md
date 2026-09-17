# Agent Instructions — KiwiSDR Client Project

## Project purpose

This project develops local desktop and analysis clients for KiwiSDR web HF/LF receivers.

Initial experiments:

1. Basic local non-web client with audio playback, frequency selection, and mode selection.
2. Above plus added controls and waterfall display.
3. Automated recording and signal detection for MF/LF radionavigation beacons.
4. Advanced long-term integration and correlation for low-SNR signal detection.

## Local reference material

The directory `kiwiclient/` contains reference code and an API useful for accessing KiwiSDR functions.

Treat `kiwiclient/` as read-mostly reference code unless explicitly asked to modify it.

Before implementing protocol behavior, inspect:

1. Local project code
2. `kiwiclient/`
3. Existing fixtures under `tests/fixtures/kiwi/`
4. `docs/kiwi-protocol.md`

## Local receivers

Available local receivers:

- Primary: `10.0.0.41:8073`
- Fallbacks: `10.0.0.42:8073`, `10.0.0.43:8073`

If the primary receiver has max users, use either fallback.

Do not use public KiwiSDR receivers unless explicitly requested.

## Harness-first rule

Prefer test harnesses before live radio testing.

For protocol, audio, waterfall, recording, and detection work:

1. Add or update a fixture.
2. Add or update a harness/regression test.
3. Fix issues found by the harness.
4. Only then perform live-radio testing.

Live-radio tests are not substitutes for regression tests.

## Live-radio rules

Before live testing:

- State what will be tested.
- Use the local receivers only.
- Avoid reconnect loops.
- Avoid long unattended connections.
- Do not send admin or mutating commands.
- Prefer short, targeted tests.
- Capture useful observations as fixtures when possible.

After live testing:

- Record receiver used.
- Record UTC/local time.
- Record frequency/mode/settings.
- Record observed behavior.
- Update `docs/kiwi-protocol.md` if protocol behavior changed.
- Update or add a regression fixture.

## Architecture rules

Separate these concerns:

- KiwiSDR transport
- Protocol parser/encoder
- Receiver state model
- Audio pipeline
- Waterfall pipeline
- Recording pipeline
- Beacon/signal detection
- Desktop UI
- Diagnostics/logging

The protocol parser must be testable without network access.

The detector must be testable from synthetic and captured fixtures.

Do not bury protocol parsing inside UI code.

## Git workflow

Current user direction: clean up and prepare the tested feature work for merge into `main`.

- Use feature branches for implementation and merge preparation.
- `main` is the intended merge target; the prior `wf1` integration requirement is superseded.
- Preparation is not execution: do not merge into or commit directly on `main` until the user requests the merge.
- Keep untracked screenshots and local state out of commits.

## Development rhythm

For each work slice:

1. Define the goal and done criteria in `TODO.md`.
2. Inspect relevant code/docs first.
3. Add or update tests before live radio work.
4. Implement the smallest useful change.
5. Run the relevant test command.
6. Update docs if behavior, architecture, or user operation changed.
7. Record important notes in `docs/dev-log.md`.
8. In response, describe changes made, a brief manual test/demo process for the user (if appropriate), and next steps.

## Done criteria

A feature is done only when:

- Relevant tests pass.
- Harness coverage exists where practical.
- Live-radio behavior, if tested, is documented.
- User-visible behavior is reflected in `docs/user-guide.md`.
- Protocol discoveries are reflected in `docs/kiwi-protocol.md`.
- No known harness failure is left unresolved before live testing.

## Coding style

Keep changes small.

Prefer simple, inspectable code over clever abstractions.

Avoid adding large frameworks unless they clearly remove complexity.

Keep logging useful for radio/protocol debugging.

Use 4-space indentation in new code where the language does not impose another convention.
