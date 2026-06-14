from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.protocol import KiwiProtocolError, parse_snd_uncompressed_mono


FIXTURE = Path("tests/fixtures/kiwi/snd-basic.jsonl")


def _fixture_payload() -> bytes:
    [event] = load_jsonl_events(FIXTURE)
    return event.binary_payload


def test_snd_uncompressed_mono_header_fields():
    frame = parse_snd_uncompressed_mono(_fixture_payload())

    assert frame.flags == 0
    assert frame.seq == 1
    assert frame.smeter == 850
    assert frame.rssi_db == pytest.approx(-42.0)


def test_snd_uncompressed_mono_pcm_big_endian():
    frame = parse_snd_uncompressed_mono(_fixture_payload())

    assert frame.samples == (-32768, -1, 0, 1, 32767)


def test_snd_rejects_truncated_header():
    with pytest.raises(KiwiProtocolError, match="shorter than 7-byte header"):
        parse_snd_uncompressed_mono(b"SND\x00\x01")


def test_snd_rejects_odd_pcm_byte_count():
    payload = _fixture_payload() + b"\x00"

    with pytest.raises(KiwiProtocolError, match="odd byte count"):
        parse_snd_uncompressed_mono(payload)
