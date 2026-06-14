---
description: Add or update a KiwiSDR harness regression test
argument-hint: "<behavior or bug>"
---

Add or update a harness regression test for:

$@

Rules:

- No live network access.
- Use `tests/fixtures/kiwi/` or synthetic data.
- Keep the test deterministic.
- Verify decoded values and units.
- Verify failure behavior if relevant.
- Fix the implementation only after the test exposes or covers the behavior.
- Update `docs/harness.md` or `docs/kiwi-protocol.md` if needed.

Run the relevant test command and report results.
