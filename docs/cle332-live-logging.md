# CLE332 live reception and assisted logging

## Source and confirmed rules

User supplied `/home/user/kiwi/cle/final332.txt`, reviewed 2026-09-26 UTC.
SHA-256: `e21c1a34c8812767ffe2f650ccd0b2d494075fe9b40f1a5a209bcb88ece45796`.
The original remains a user-owned input in the original worktree. Earlier advice
and CLE331 data are reference only. The general `rna-signals.csv` is a catalogue,
not a current event seeklist or evidence of reception.

- Event: September 25–28, 2026, noon Friday to noon Monday **local at the receiver**.
- NDB nominal published frequencies: even integer channels 190–530 kHz inclusive.
- Positive listener identification required; UNIDs and half-kHz channels excluded.
- Use nominal frequency in the report even when listening to a sideband.
- Subject: `CLE332 FINAL`. Prefer plain text in the email body, not an attachment.
- Every log line begins with date and UTC time, nominal kHz, then call ident.
  Optional location/distance follows. Use full ISO dates to avoid UTC-day ambiguity.
- Include receiving location with six-character Maidenhead locator, receiver and
  aerial details. Include the web address for a publicly available remote receiver.
- A remote listener may use **one remote receiver only**, and may not add loggings
  from any other local or remote receiver for this CLE. Receiver failover remains
  possible for general listening but must not silently combine event loggings.
- Send a complete FINAL even if interim logs were sent.
- Log must arrive on the List by **2026-09-30 08:00 UTC**.

The announcement does not specify automatic decoding or recording rules. This
branch is a live, human-confirmed assistant; no automatic identification or mail
submission is planned. The supplied announcement does not give the List's posting
address; do not substitute the coordinator's question/contact address.

## Implemented keyboard workflow

All four milestones below are implemented with offline regressions. Start the new
worktree explicitly (the old editable Python installation otherwise targets the
analysis branch):

```bash
cd /home/user/kiwi-rna
PYTHONPATH=src ../kiwi/.kiwi-venv/bin/python -m kiwi_client.integrated_terminal \
    --allow-live --receiver 10.0.0.43:8073 --audio \
    --rna rna-signals.csv --rna-cle332 \
    --logbook receptions.sqlite --log-event CLE332
```

This command deliberately connects to .43 when run; it was **not** used for live
validation during development. Add `--dry-run` to inspect without connecting.
`--rna-cle332` limits the shortlist to even nominal channels and known catalogue IDs;
this does not confirm reception. The report independently checks eligibility. Use `--rna-sites sites.toml --rna-distance-km N` after
configuring actual receiving coordinates. No location has been guessed for the
local receivers. Choose the one receiver/setup for your event before collecting
loggings, and do not mix fallback receivers into that event log.

`n/N` browses stations, `v` chooses carrier/sideband, `y` tunes CW, `A` changes
activity policy, and `w` opens the hearing-time/notes and explicit confirmation form.
See [User guide](user-guide.md) for edits/export and profile examples. Report checks
cannot verify that a human really copied an ident or that the supplied site is
correct; these remain operator responsibilities.

## Implementation sequence

1. Independent local RNA import/filter model and regression fixtures.
2. Tuning-scale carrier/sideband markers and keyboard station/component selection.
3. Durable assisted logging, with receiver identity, hearing time and catalogue snapshot.
4. Validated plain-text report preview/export using the rules above.

Require the actual receiving site's coordinates/timezone and report station
metadata before final export; do not infer them from the developer computer.
Eligibility is separate from catalogue activity and distance filters. Preserve
all receptions internally; export only eligible confirmed entries. No prior
recording or catalogue row becomes a reception merely by being loaded.
