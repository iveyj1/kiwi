import pytest

from kiwi_client.protocol import KiwiProtocolError, parse_msg


def test_msg_parses_name_value_pairs():
    msg = parse_msg("MSG sample_rate=12001.135 audio_rate=12000")

    assert msg.params == {
        "sample_rate": "12001.135",
        "audio_rate": "12000",
    }


def test_msg_parses_flag_without_value():
    msg = parse_msg("MSG keepalive")

    assert msg.params == {"keepalive": None}


def test_msg_decodes_percent_escaped_values():
    msg = parse_msg("MSG extint_list_json=%7B%22x%22%3A1%7D")

    assert msg.params == {"extint_list_json": '{"x":1}'}


def test_msg_rejects_non_msg_tag():
    with pytest.raises(KiwiProtocolError, match="expected MSG tag"):
        parse_msg(b"SND whatever")
