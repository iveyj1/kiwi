---
description: Prepare or perform a short local KiwiSDR fixture capture
argument-hint: "<stream/behavior>"
---

Prepare a fixture capture for:

$@

Rules:

- Use local receivers only: `10.0.0.41:8073`, with `10.0.0.42:8073` and `10.0.0.43:8073` as fallbacks.
- Keep capture short.
- Avoid reconnect loops.
- Do not send admin or mutating commands.
- Store fixture under `tests/fixtures/kiwi/`.
- Include metadata: receiver, time, frequency, mode, stream, commands, frame counts, and purpose.
- Add or update a replay/regression test after capture.
- Update `docs/harness.md` and `docs/kiwi-protocol.md` if behavior is learned.

Before connecting live, state the exact command/session behavior to be tested.
