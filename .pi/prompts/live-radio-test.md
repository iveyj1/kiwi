---
description: Perform a controlled local KiwiSDR live-radio test
argument-hint: "<purpose>"
---

Perform a controlled local KiwiSDR live-radio test:

$@

Rules:

- Use only `10.0.0.40:8073` or fallback `10.0.0.41:8073`.
- First confirm the related harness tests pass.
- Keep the test short.
- Avoid reconnect loops.
- Do not send admin or mutating commands.
- Capture useful behavior as a fixture if practical.
- Update `docs/radio-lab.md`.
- Update `docs/kiwi-protocol.md` if protocol behavior is learned.

Report:

- Receiver used
- Frequency/mode/settings
- Commands sent
- Result
- Fixture captured
- Follow-up required
