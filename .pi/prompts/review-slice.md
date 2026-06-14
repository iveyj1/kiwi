---
description: Review current KiwiSDR changes against project process
argument-hint: "[focus]"
---

Review the current changes.

Focus: ${1:-general correctness}

Check:

- Harness-first rule followed
- Tests added or updated
- No unnecessary live-radio dependency
- Protocol docs updated if needed
- Architecture separation preserved
- Audio/waterfall/detector assumptions documented
- No accidental edits to `kiwiclient/`
- Error handling and logging are adequate

Run read-only inspection first. Then recommend fixes.
