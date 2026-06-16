from pathlib import Path

import pytest

from kiwi_client.waterfall_preview import preview_waterfall_fixture, main


FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")


def test_preview_waterfall_fixture_renders_binary_wf_rows():
    text = preview_waterfall_fixture(FIXTURE, min_dbm=-110, max_dbm=0)

    assert text == "   +@\n"


def test_preview_waterfall_fixture_renders_custom_ramp():
    text = preview_waterfall_fixture(FIXTURE, min_dbm=-110, max_dbm=0, ramp="._#")

    assert text == "..._#\n"


def test_waterfall_preview_main_prints_rows(capsys):
    exit_code = main([str(FIXTURE), "--min-db", "-110", "--max-db", "0"])

    assert exit_code == 0
    assert capsys.readouterr().out == "   +@\n"


def test_waterfall_preview_main_rejects_bad_scale(capsys):
    with pytest.raises(SystemExit):
        main([str(FIXTURE), "--min-db", "0", "--max-db", "0"])
