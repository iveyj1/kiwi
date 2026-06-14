from pathlib import Path

from kiwi_client.commands import encode_ar_ok, encode_auth, encode_basic_snd_setup
from kiwi_client.fixtures import load_jsonl_events


FIXTURE = Path("tests/fixtures/kiwi/snd-setup-commands.jsonl")


def test_snd_setup_command_fixture_matches_encoder_sequence():
    expected = [event.raw["text"] for event in load_jsonl_events(FIXTURE)]

    generated = [encode_auth(), encode_ar_ok(12000)] + encode_basic_snd_setup(
        user="kiwi-client",
        frequency_khz=4625.0,
    )

    assert generated == expected
