# NDB reception techniques

## Nominal carrier, modulation sidebands and CW listening

A catalogue station is identified by its nominal published carrier frequency
and location/ident, not by the receiver dial setting used to hear it. Amplitude
modulation produces components on either side of the carrier. RNA lists the
observed lower and upper offsets separately; they need not be identical.

For nominal carrier `f_c` in kHz and positive offsets `d_L`, `d_U` in Hz:

```
f_L = f_c - d_L / 1000
f_U = f_c + d_U / 1000
```

Our RJ example is 378.000 kHz with offsets 410/405 Hz: components at 377.590 and
378.405 kHz. Selecting USB here means selecting that RF component, not setting the
receiver's demodulation mode to USB. The assistant tunes the chosen component in
CW. The existing signed CW tuning offset makes it audible as a tone.

With an -800 Hz CW offset and selected component 378.405 kHz, the receiver reference
is 377.605 kHz. Audio passband limits 600–1000 Hz map to RF 378.205–378.605 kHz.
The component falls at 800 Hz audio. Other configured offsets/passband limits can
place the reference away from the actual passband centre. The catalogue supplies
RF frequencies only; applying the CW offset in the catalogue as well as in the
controller would shift tuning twice.

The display therefore separates carrier/component annotations from the receiver
reference/passband. The log stores all relevant frequencies, but CLE eligibility
and report lines use **378 kHz**, not 378.405 or 377.605. A carrier or nearby spectral
line alone does not confirm the station ident. Co-channel stations, interference,
stale catalogue information and drift can all mislead an operator.

Missing offsets stay unknown. Text such as `~400` currently remains unknown with
a diagnostic rather than becoming an exact marker. Raw catalogue fields are kept
for review. See `rna_catalogue.py`, `rna_console.py` and the asymmetric-offset
fixture `tests/fixtures/rna/catalogue.csv`.

## Distance and activity as listening aids

Distance is the great-circle distance between the receiving antenna's coordinates
and the catalogue station coordinates, using a spherical Earth radius of
6371.0088 km. It is a shortlist aid, not a prediction of path loss or audibility;
propagation, antenna response, local noise and station power still matter.
Coordinates refer to the receiving site even when the operator controls it remotely.
A receiver change must not reuse the previous site's location.

Missing coordinates produce an unknown distance, retained by default. RNA activity
is a catalogue assertion, distinct from its last logged date and from a reception
being confirmed now. Filtering out inactive stations is convenient but can miss
reactivations or catalogue errors; the UI allows an all-records view. Neither
distance nor activity filter automatically identifies or logs a signal.
