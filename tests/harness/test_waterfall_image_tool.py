import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


TOOL_PATH = Path("tools/waterfall_image.py")
SYNTHETIC_FIXTURE = Path("tests/fixtures/kiwi/wf-basic.jsonl")
LOCAL_FIXTURE = Path("tests/fixtures/kiwi/local-wf-5000-zoom0.jsonl")


def load_tool():
    spec = importlib.util.spec_from_file_location("waterfall_image_tool", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_waterfall_image_tool_loads_synthetic_fixture_rows():
    tool = load_tool()

    rows = tool.load_waterfall_dbm_rows(SYNTHETIC_FIXTURE)

    assert tool.matrix_shape(rows) == (1, 5)
    assert rows == [[-255, -200, -127, -55, 0]]


def test_waterfall_image_tool_applies_calibration_offset():
    tool = load_tool()

    rows = tool.load_waterfall_dbm_rows(SYNTHETIC_FIXTURE, calibration_db=-13)

    assert rows == [[-268, -213, -140, -68, -13]]


def test_waterfall_image_tool_loads_local_fixture_shape_and_values():
    tool = load_tool()

    rows = tool.load_waterfall_dbm_rows(LOCAL_FIXTURE)

    assert tool.matrix_shape(rows) == (2, 1024)
    assert rows[0][:8] == [-200, -69, -69, -83, -83, -91, -77, -70]
    assert rows[1][:8] == [-200, -76, -71, -72, -70, -56, -69, -63]


def test_waterfall_image_tool_rejects_non_rectangular_rows():
    tool = load_tool()

    with pytest.raises(ValueError, match="not rectangular"):
        tool.matrix_shape([[1, 2], [3]])


def test_waterfall_image_tool_runs_without_pythonpath(tmp_path: Path):
    pytest.importorskip("matplotlib")
    output = tmp_path / "wf.png"

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL_PATH),
            str(SYNTHETIC_FIXTURE),
            str(output),
            "--summary",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "rows=1 bins=5" in result.stdout
    assert output.exists()
