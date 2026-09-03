import json

import pytest

from tools.waterfall_gui_benchmark import main, run_no_window_baseline, synthetic_frame


def test_synthetic_benchmark_frame_is_deterministic_and_mapped():
    first = synthetic_frame(3, width=8)
    second = synthetic_frame(3, width=8)

    assert first == second
    assert len(first.dbm) == 8
    assert first.start_khz == pytest.approx(4882.8125)
    assert first.span_khz == pytest.approx(234.375)
    assert first.bin_width_hz == pytest.approx(234_375 / 8)


def test_no_window_baseline_reports_coalescing_at_slower_consumer_rate():
    result = run_no_window_baseline(
        width=16,
        history_rows=4,
        frames=20,
        source_fps=20,
        consumer_fps=10,
    )

    assert result.produced_frames == 20
    assert result.presented_snapshots == 10
    assert result.coalesced_generations == 10
    assert result.virtual_duration_seconds == pytest.approx(1.0)
    assert result.elapsed_seconds > 0
    assert result.producer_fps > 0
    assert result.mean_publish_ms > 0
    assert result.p95_publish_ms > 0


def test_no_window_baseline_rejects_invalid_workload():
    with pytest.raises(ValueError, match="positive"):
        run_no_window_baseline(frames=0)
    with pytest.raises(ValueError, match="positive"):
        run_no_window_baseline(source_fps=0)


def test_benchmark_cli_emits_one_json_result_per_history_depth(capsys):
    assert main([
        "--history-rows", "2,4",
        "--width", "8",
        "--frames", "4",
        "--source-fps", "20",
        "--consumer-fps", "20",
    ]) == 0

    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["history_rows"] for row in rows] == [2, 4]
    assert all(row["presented_snapshots"] == 4 for row in rows)
