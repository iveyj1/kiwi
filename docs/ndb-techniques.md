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

## Symmetric CW bandwidth adjustment

The console's `j/k` steps select full widths of 10, 20, 30, 50, 100 or 500 Hz.
For current audio passband edges `low` and `high`, preserve midpoint
`m = (low + high)/2` and set the new edges to `m - width/2` and `m + width/2`.
Thus 600–1000 Hz (400 Hz wide, midpoint 800 Hz) narrows to 750–850 Hz at 100 Hz
width. The receiver reference and selected RF component do not change; this avoids
changing the listening pitch just to narrow the filter. This uses the existing
receiver filter command, not local DSP. Very narrow filters can suppress keyed
signal bandwidth or smear transitions; select width by listening rather than
assuming the narrowest filter is always best. Integer-Hz command cuts cannot
preserve a half-Hz midpoint with these even widths; that case is explicitly rejected.

## Distance and activity as listening aids

Distance is the great-circle distance between the receiving antenna's coordinates
and the catalogue station coordinates, using a spherical Earth radius of
6371.0088 km. It is a shortlist aid, not a prediction of path loss or audibility;
propagation, antenna response, local noise and station power still matter.
Coordinates refer to the receiving site even when the operator controls it remotely.
A receiver change must not reuse the previous site's location.

Missing coordinates produce an unknown distance, retained by default. The runtime
`:rna range N` command instead requests a strict known-distance `<= N` test, so it
excludes unknown distances. `:rna power N` similarly requires known catalogue
power `>= N` watts; it does not estimate received power or signal strength. Distance
sort puts unknown distances last. Callsign search still shows excluded rows with
reasons, helping distinguish catalogue absence from an active shortlist filter. RNA activity
is a catalogue assertion, distinct from its last logged date and from a reception
being confirmed now. Filtering out inactive stations is convenient but can miss
reactivations or catalogue errors; the UI allows an all-records view. Neither
distance nor activity filter automatically identifies or logs a signal.
