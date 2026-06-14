from pathlib import Path

from kiwi_client.audio import SndSequenceTracker, has_adc_overflow
from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import SND_FLAG_ADC_OVFL, SndAudioFrame, parse_snd_uncompressed_mono


FIXTURE = Path("tests/fixtures/kiwi/snd-sequence-gap.jsonl")


def test_snd_sequence_tracker_detects_fixture_gap():
    tracker = SndSequenceTracker()
    frames = [parse_snd_uncompressed_mono(event.binary_payload) for event in load_jsonl_events(FIXTURE)]

    statuses = [tracker.observe(frame) for frame in frames]

    assert [frame.seq for frame in frames] == [1, 3, 4]
    assert statuses[0].ok
    assert statuses[1].expected_seq == 2
    assert statuses[1].missing_count == 1
    assert not statuses[1].ok
    assert statuses[2].ok


def test_snd_sequence_tracker_accepts_uint32_wraparound():
    tracker = SndSequenceTracker()

    statuses = [
        tracker.observe(SndAudioFrame(flags=0, seq=0xFFFFFFFF, smeter=0, rssi_db=-127.0, samples=())),
        tracker.observe(SndAudioFrame(flags=0, seq=0, smeter=0, rssi_db=-127.0, samples=())),
    ]

    assert statuses[0].ok
    assert statuses[1].expected_seq == 0
    assert statuses[1].ok


def test_snd_sequence_tracker_marks_out_of_order_frame():
    tracker = SndSequenceTracker()

    first = tracker.observe(SndAudioFrame(flags=0, seq=10, smeter=0, rssi_db=-127.0, samples=()))
    second = tracker.observe(SndAudioFrame(flags=0, seq=9, smeter=0, rssi_db=-127.0, samples=()))

    assert first.ok
    assert second.expected_seq == 11
    assert second.out_of_order
    assert not second.ok


def test_has_adc_overflow_exposes_snd_flag():
    assert has_adc_overflow(SndAudioFrame(flags=SND_FLAG_ADC_OVFL, seq=1, smeter=0, rssi_db=-127.0, samples=()))
    assert not has_adc_overflow(SndAudioFrame(flags=0, seq=1, smeter=0, rssi_db=-127.0, samples=()))
