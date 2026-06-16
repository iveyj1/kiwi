from pathlib import Path

import pytest

from kiwi_client.fixtures import load_jsonl_events
from kiwi_client.waterfall import parse_waterfall_uncompressed
from kiwi_client.waterfall_render import DEFAULT_ASCII_RAMP, dbm_to_ramp_index, render_ascii_waterfall_row


FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")


def _fixture_frame():
    events = load_jsonl_events(FIXTURE)
    [event] = [event for event in events if event.type == "binary"]
    return parse_waterfall_uncompressed(event.binary_payload)


def test_dbm_to_ramp_index_uses_fixed_scale_and_clamps():
    assert dbm_to_ramp_index(-255, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 0
    assert dbm_to_ramp_index(-110, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 0
    assert dbm_to_ramp_index(-55, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 5
    assert dbm_to_ramp_index(0, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 9
    assert dbm_to_ramp_index(10, min_dbm=-110, max_dbm=0, ramp=DEFAULT_ASCII_RAMP) == 9


def test_render_ascii_waterfall_row_from_fixture():
    frame = _fixture_frame()

    row = render_ascii_waterfall_row(frame, min_dbm=-110, max_dbm=0)

    assert row == "   +@"


def test_render_ascii_waterfall_row_accepts_custom_ramp():
    frame = _fixture_frame()

    row = render_ascii_waterfall_row(frame, min_dbm=-110, max_dbm=0, ramp="._#")

    assert row == "..._#"


def test_dbm_to_ramp_index_rejects_invalid_scale():
    with pytest.raises(ValueError, match="max_dbm must be greater"):
        dbm_to_ramp_index(-50, min_dbm=0, max_dbm=0)


def test_dbm_to_ramp_index_rejects_short_ramp():
    with pytest.raises(ValueError, match="at least two"):
        dbm_to_ramp_index(-50, ramp="@")
