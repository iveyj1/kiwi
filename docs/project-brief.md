# KiwiSDR Client Project Brief

## Problem

KiwiSDR provides capable browser-based HF/LF receiver access, but this project explores local desktop and analysis clients with better control over audio, waterfall, recording, and weak-signal analysis workflows.

## Local receivers

- Primary: `10.0.0.40:8073`
- Fallback: `10.0.0.41:8073`

## Reference code

`kiwiclient/` contains reference code/API for accessing KiwiSDR functions.

## Experiments

### 1. Basic local client

A non-web desktop client supporting:

- Connect/disconnect
- Frequency selection
- Mode selection
- Audio playback
- Basic status/error display

### 2. Waterfall client

Adds:

- Waterfall display
- Additional receiver controls
- Better diagnostics

### 3. Recording and beacon detection

Adds:

- Scheduled or manual recording
- MF/LF radionavigation beacon detection
- Signal event logging
- Offline analysis from recordings

### 4. Advanced weak-signal analysis

Adds:

- Long-term integration
- Correlation
- Low-SNR detection
- Repeatable offline analysis

## Process rule

Harness first, live radio second.

No live-radio test should be the only test for important behavior.
