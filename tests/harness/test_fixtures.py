from pathlib import Path

from kiwi_client.fixtures import load_jsonl_events


FIXTURE = Path("tests/fixtures/kiwi/snd-basic.jsonl")
WF_FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")


def test_snd_fixture_loads_jsonl_events():
    events = load_jsonl_events(FIXTURE)

    assert len(events) == 1
    event = events[0]
    assert event.t == 0.0
    assert event.dir == "rx"
    assert event.stream == "snd"
    assert event.type == "binary"
    assert event.binary_payload.startswith(b"SND")


def test_wf_fixture_loads_jsonl_events():
    events = load_jsonl_events(WF_FIXTURE)

    assert len(events) == 4
    binary_events = [event for event in events if event.type == "binary"]
    assert len(binary_events) == 1
    event = binary_events[0]
    assert event.t == 0.05
    assert event.dir == "rx"
    assert event.stream == "wf"
    assert event.binary_payload.startswith(b"W/F")
