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

For the selected station, the display draws a horizontal C/LSB/USB span below the
frequency scale, with dotted connectors up to the waterfall's bottom edge and a
dedicated label row. It does not draw lines through waterfall history. The guides use the same viewport mapping as
the scale: `x = round((f - start)/(end - start) * (width - 1))`, with all frequencies
in kHz. Thus RJ's carrier is marked at 378.000, LSB at 377.590 and USB at 378.405;
the CW receiver reference at 377.605 is not a station component. A personal stored
RF center gets its own S label/stem, without a fourth connector. The horizontal
span is clipped to the viewport; out-of-view component connectors are omitted,
not clamped to an edge. These are location hypotheses on the spectrum, not detections; missing
or inaccurate catalogue offsets remain a limitation. Fixed-raster tests in
`tests/harness/test_selected_station_markers.py` check RF geometry, unknown offsets,
collision priority and removal of old guides when selection changes.

## Symmetric CW bandwidth adjustment

The console's `j/k` steps request full widths of 2, 5, 10, 20, 30, 50, 100 or 500 Hz.
For current audio passband edges `low` and `high`, preserve midpoint
`m = (low + high)/2` and set the new edges to `m - width/2` and `m + width/2`.
Thus 600–1000 Hz (400 Hz wide, midpoint 800 Hz) narrows to 750–850 Hz at 100 Hz
width. For even-to-even changes the receiver reference and selected RF component do not
change. A 5 Hz width instead needs half-integer edges about an integer midpoint,
but the command encodes integer-Hz cuts. Use cuts 798..803 Hz (midpoint 800.5 Hz)
and lower the receiver reference by 0.5 Hz: the actual RF passband remains symmetric
about the same RF center. A 2 Hz width uses 799..801 Hz and restores the reference.
Canonical integer/half-integer midpoints avoid accumulating reference drift when
cycling repeatedly. Catalogue retuning and logging account for this compensation.
Four or more kHz command decimals are needed for the half-Hz reference adjustment;
at coarser precision, incompatible ladder steps are skipped rather than shifting
RF center silently.

This uses existing receiver commands, not local DSP. The synthetic fixture
`tests/fixtures/kiwi/cw-narrow-commands.json` proves command values and RF mapping,
not receiver acceptance or effective 2/5 Hz selectivity. We have not measured
firmware clamping, filter shape, settling time or achieved rejection at these
widths. Very narrow filters can suppress keyed signal bandwidth or smear transitions;
select width by listening rather than assuming the narrowest request is always best.

## Personal tuning versus catalogue frequencies

Fine tuning may favor a center different from a catalogue sideband. Keep that
observation in personal station state, not as a correction to RNA. Store signed
offset `1000 * (RF_center_kHz - nominal_carrier_kHz)` and full bandwidth in Hz.
The RF center is `UI_frequency + cw_offset/1000 + (low_cut+high_cut)/2000` in CW.
For UI 378.375 kHz, CW offset -800 Hz and cuts 825..875 Hz, center is 378.425 kHz:
+425 Hz from nominal 378, at 50 Hz bandwidth. Recall restores the requested width
and computes the CW UI reference required for that same RF center. It does not
assume the audio midpoint equals the magnitude of the configured CW offset.

These memories reflect a listener's preference/observation, not calibrated carrier
offset measurements: interference, propagation, receiver reference errors and
filter preference may all contribute. They are stored separately in
`station_memory.py`, and immutable reception snapshots supply report comments.
Later personal tuning changes must not retroactively alter previous loggings.
The submitted main frequency column remains nominal; center/offset/BW go in
optional comments after the required date/time/frequency/ID fields.

## Comparing nearby station hypotheses

Nearby identification assistance compares the actual RF passband center with each
shortlisted station's known carrier, LSB, USB and optional personal stored center.
Take the closest component per station within a user-selected radius in Hz, then
order stations by absolute RF separation. A station appears only once even if
several components overlap the window. This does not estimate an ident or confidence:
two AM NDB sidebands may be almost coincident, and distance/power/activity are only
catalogue aids. Missing offsets remain unknown, and active shortlist filters still
apply, including event eligibility if enabled.

Keep the search anchor fixed while cycling. For example, at 300.000 kHz with a
100 Hz radius, components at 300.000 and 300.090 qualify but 300.180 does not.
Retuning to 300.090 must not silently shift the window to admit 300.180; repeated
cycling should compare the same hypotheses. Manual retuning or a changed filter,
receiver or radius starts a fresh window. `RnaBrowser.nearby_components` and
`cycle_nearby` implement this, with synthetic regressions in
`tests/harness/test_nearby_and_log_removal.py`. Human listening and explicit log
review remain necessary; a wrong prior ID can be marked not-heard without erasing
its historical tuning evidence.

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
