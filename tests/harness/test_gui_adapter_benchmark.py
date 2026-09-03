import json

from kiwi_client.waterfall_raster import RasterImage
from tools.waterfall_gui_adapter_benchmark import (
    benchmark_adapter,
    main,
    synthetic_raster,
)


class FakeAdapter:
    name = "fake"

    def __init__(self):
        self.started = []
        self.images = []
        self.pumps = 0
        self.closed = False

    def start(self, width, height):
        self.started.append((width, height))

    def present(self, image):
        self.images.append(image)

    def pump(self):
        self.pumps += 1

    def close(self):
        self.closed = True


def test_synthetic_raster_is_deterministic_rgb():
    first = synthetic_raster(width=8, height=4, phase=2)
    second = synthetic_raster(width=8, height=4, phase=2)

    assert first == second
    assert isinstance(first, RasterImage)
    assert len(first.rgb) == 8 * 4 * 3


def test_adapter_benchmark_measures_common_lifecycle_and_presentation():
    adapter = FakeAdapter()

    result = benchmark_adapter(lambda: adapter, width=16, height=8, frames=5)

    assert adapter.started == [(16, 8)]
    assert len(adapter.images) == 5
    assert adapter.images[0] != adapter.images[1]
    assert adapter.pumps == 5
    assert adapter.closed is True
    assert result.adapter == "fake"
    assert result.presented_frames == 5
    assert result.mean_present_ms >= 0
    assert result.p95_present_ms >= 0
    assert result.presentation_fps > 0


def test_adapter_benchmark_closes_adapter_after_failure():
    class FailingAdapter(FakeAdapter):
        def present(self, image):
            raise RuntimeError("display failed")

    adapter = FailingAdapter()
    try:
        benchmark_adapter(lambda: adapter, width=2, height=2, frames=1)
    except RuntimeError as exc:
        assert str(exc) == "display failed"
    else:
        raise AssertionError("expected adapter failure")
    assert adapter.closed is True


def test_fake_cli_emits_json_for_each_height(capsys):
    assert main([
        "--adapter", "fake",
        "--width", "8",
        "--heights", "2,4",
        "--frames", "3",
    ]) == 0

    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["height"] for row in rows] == [2, 4]
    assert all(row["adapter"] == "fake" for row in rows)
    assert all(row["presented_frames"] == 3 for row in rows)
