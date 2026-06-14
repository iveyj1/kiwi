# KiwiSDR Desktop Client Project Scaffold

This scaffold gives Pi Coding Agent a lightweight development process for a small KiwiSDR desktop/audio/waterfall/analysis client.

## Intended workflow

1. Copy these files into the root of the KiwiSDR client project.
2. Keep the existing `kiwiclient/` directory as reference code.
3. Start Pi from the project root.
4. Use the prompts under `.pi/prompts/` for work slices.

## Main rule

Harness first, live radio second.

Develop protocol, audio, waterfall, recording, and detection behavior against fixtures or synthetic data before testing against live KiwiSDR receivers.

## Local receivers

- Primary: `10.0.0.40:8073`
- Fallback: `10.0.0.41:8073`

Use the fallback if the primary has max users.

## First suggested Pi command

```text
/slice inspect kiwiclient and create the first concrete plan for fixture-based SND audio tests. Do not connect to live receivers yet.
```

## Then

```text
/harness-test first synthetic or captured SND audio frame decode path
```

After harness tests exist and pass:

```text
/live-radio-test short connection to 10.0.0.40:8073 for basic audio capture fixture; fallback to 10.0.0.41:8073 if max users
```
