---
description: Perform a controlled local KiwiSDR live-radio test
argument-hint: "<purpose>"
---

Perform a controlled local KiwiSDR live-radio test:

$@

Rules:

- Use `10.0.0.41:8073` or fallbacks `10.0.0.42:8073` and `10.0.0.43:8073`.
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
