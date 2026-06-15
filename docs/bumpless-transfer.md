# Bumpless receiver transfer notes

Goal: reduce audible transients when starting playback or switching receivers.

Observed behavior:

- Receiver switches can produce roughly 100–200 ms of transient audio when the new receiver starts.
- The transient is also heard when switching to the same receiver and at app startup.

Possible causes:

1. Kiwi startup audio may be dirty while the receiver/session settles after setup commands.
2. Local audio output may contain buffered or stale samples across stop/start boundaries.
3. Abrupt stop/start causes discontinuities or clicks.
4. Receiver AGC or audio level may settle during the first few frames.

Options considered:

## A. Drop initial playback audio

Drop the first configurable N ms of decoded SND PCM after each playback start while still processing status metrics.

Pros:

- Simple and low risk.
- Handles app startup and receiver-switch startup transients.
- Easy to test from replay fixtures.

Cons:

- Adds a short silence.
- Does not keep old receiver audio alive while the new one starts.

Implemented first as `[audio] startup_mute_ms`, followed by `[audio] startup_fade_in_ms`.

## B. Fade in the new stream

Drop/mute a small initial window, then fade in over another short interval.

Pros:

- Smoother than sudden unmute.
- Can reduce clicks.

Cons:

- Requires gain shaping in the audio pipeline.

Implemented as linear sample-domain fade-in after the startup mute window.

## C. Fade out the old stream

On receiver switch, fade the old stream out before stopping it.

Pros:

- Reduces hard discontinuities.

Cons:

- Current playback worker/sink model does not yet expose live gain control.

Partially implemented for cooperative live playback stop: when frames are still arriving, playback writes a short faded tail before exiting.

## D. Overlap old and new streams

Keep the old receiver playing while a new receiver starts muted/prebuffered, then crossfade once the new stream is healthy.

Pros:

- Closest to true bumpless transfer.
- Keeps previous receiver streaming until replacement is ready.

Cons:

- Larger architecture change: needs a playback manager capable of two concurrent streams and mix/crossfade behavior.

## E. No-op same-receiver switches

Skip restart if selected receiver already matches current receiver.

Pros:

- Very low risk for the special case.

Cons:

- Does not help real receiver changes or startup.

Current direction:

- Implemented option A plus short fade-in/fade-out.
- Evaluate whether mute+fade is enough.
- If not, consider overlapping old/new streams.
