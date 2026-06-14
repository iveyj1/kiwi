# MF/LF Beacon Detection

## Purpose

Detect MF/LF radionavigation beacons from KiwiSDR audio/IQ recordings and support later long-integration low-SNR analysis.

## Early detector scope

- Known-frequency carrier detection
- Narrowband spectral power estimate
- Event log output
- Optional Morse/NDB identifier support later

## Synthetic test cases

- No signal
- Strong carrier
- Weak carrier near threshold
- Carrier with frequency offset
- Carrier with drift
- Fading carrier
- Narrowband interferer
- Impulsive noise

## Later analysis

- Long-duration accumulation
- Coherent or semi-coherent integration
- Correlation against expected IDs or modulation patterns
- Drift compensation
- Time-base error handling
- Repeatable offline analysis pipeline
