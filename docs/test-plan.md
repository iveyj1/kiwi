# Test Plan

## Test order

Use this order for new behavior:

1. Unit tests for parser/encoder logic.
2. Fixture replay tests.
3. Synthetic audio/IQ/waterfall tests.
4. Integration tests against a local fake receiver, if implemented.
5. Short manual live-radio test against local receiver.

Do not skip directly to live radio unless explicitly requested.

## Protocol tests

Protocol tests should verify:

- Message type recognition
- Binary frame decoding
- Field extraction
- Units
- Sequence number behavior
- Malformed frame handling
- Disconnect/max-user behavior where fixture data exists

## Audio tests

Audio tests should verify:

- Sample rate
- Sample format
- Gain/scaling
- Buffering
- Dropout handling
- Underflow/overflow behavior
- Recording file output, if applicable

## Waterfall tests

Waterfall tests should verify:

- Frame dimensions
- Bin ordering
- Frequency mapping
- Intensity scaling
- Fixed-input deterministic rendering model

## Beacon detection tests

Synthetic detector tests should include:

- Signal absent
- Signal present above threshold
- Signal near threshold
- Frequency offset
- Carrier drift
- Fading
- Impulsive noise
- Narrowband interferer
- False-positive case

## Regression gate

Before live-radio testing, relevant harness tests should pass.

Before committing, run the smallest relevant test set plus any changed-area regression tests.
