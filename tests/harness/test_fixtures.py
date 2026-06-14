from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events


FIXTURE = Path("tests/fixtures/kiwi/snd-basic.jsonl")


def test_snd_fixture_loads_jsonl_events():
    events = load_jsonl_events(FIXTURE)

    assert len(events) == 1
    event = events[0]
    assert event.t == 0.0
    assert event.dir == "rx"
    assert event.stream == "snd"
    assert event.type == "binary"
    assert event.binary_payload.startswith(b"SND")
