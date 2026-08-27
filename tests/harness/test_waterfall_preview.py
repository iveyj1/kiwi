from pathlib import Path

import pytest

from kiwi_client.waterfall_preview import preview_waterfall_fixture, main


FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")
LOCAL_FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")


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


def test_preview_waterfall_fixture_reduces_local_fixture_to_requested_columns():
    text = preview_waterfall_fixture(LOCAL_FIXTURE, min_dbm=-200, max_dbm=-25, columns=100)

    rows = text.splitlines()
    assert len(rows) == 2
    assert all(len(row) == 100 for row in rows)


def test_waterfall_preview_main_defaults_to_terminal_width(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "120")

    exit_code = main([str(LOCAL_FIXTURE), "--min-db", "-200", "--max-db", "-25"])

    assert exit_code == 0
    rows = capsys.readouterr().out.splitlines()
    assert [len(row) for row in rows] == [120, 120]


def test_waterfall_preview_main_columns_zero_renders_one_char_per_bin(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "120")

    exit_code = main([str(LOCAL_FIXTURE), "--min-db", "-200", "--max-db", "-25", "--columns", "0"])

    assert exit_code == 0
    rows = capsys.readouterr().out.splitlines()
    assert [len(row) for row in rows] == [1024, 1024]


def test_waterfall_preview_main_accepts_mean_reduction(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "120")

    exit_code = main([str(LOCAL_FIXTURE), "--min-db", "-200", "--max-db", "-25", "--reduction", "mean"])

    assert exit_code == 0
    rows = capsys.readouterr().out.splitlines()
    assert [len(row) for row in rows] == [120, 120]


def test_waterfall_preview_main_rejects_negative_columns():
    with pytest.raises(SystemExit):
        main([str(FIXTURE), "--columns", "-1"])
