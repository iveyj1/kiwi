# Radio Lab Notes

## Receivers

| Name | Address | Notes |
|---|---|---|
| kiwi40 | `10.0.0.40:8073` | Primary; may have max users |
| kiwi41 | `10.0.0.41:8073` | Fallback |

## Live-test policy

Use local receivers only unless explicitly requested.

Prefer short tests.

Do not run unattended reconnect loops.

Do not issue admin or mutating commands.

## Live-test record template

```text
Date/time:
Receiver:
Frequency:
Mode:
Filter:
Stream type:
Purpose:
Commands sent:
Observed behavior:
Fixture captured:
Follow-up:
```

## Live-test log

### YYYY-MM-DD

```text
Date/time:
Receiver:
Frequency:
Mode:
Filter:
Stream type:
Purpose:
Commands sent:
Observed behavior:
Fixture captured:
Follow-up:
```
