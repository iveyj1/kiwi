#!/usr/bin/env python3
"""Compare optional native GUI adapters with a fixed direct-RGB workload."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

from kiwi_client.waterfall_raster import RasterImage


class GuiAdapter(Protocol):
    name: str

    def start(self, width: int, height: int) -> None: ...
    def present(self, image: RasterImage) -> None: ...
    def pump(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class AdapterBenchmarkResult:
    adapter: str
    width: int
    height: int
    presented_frames: int
    startup_ms: float
    elapsed_seconds: float
    presentation_fps: float
    mean_present_ms: float
    p95_present_ms: float
    rgb_bytes_per_frame: int
    installed_megabytes: float | None


def synthetic_raster(*, width: int, height: int, phase: int) -> RasterImage:
    """Create deterministic packed RGB without including generation in timings."""
    if width <= 0 or height <= 0:
        raise ValueError("raster width and height must be positive")
    rgb = bytearray(width * height * 3)
    offset = 0
    for row in range(height):
        for column in range(width):
            value = (column * 7 + row * 3 + phase * 17) & 0xFF
            rgb[offset:offset + 3] = bytes((value // 4, value, 255 - value))
            offset += 3
    return RasterImage(width, height, bytes(rgb))


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return ordered[index]


def distribution_size_megabytes(names: tuple[str, ...]) -> float | None:
    total = 0
    found = False
    seen: set[Path] = set()
    for name in names:
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        found = True
        for file in distribution.files or ():
            path = Path(distribution.locate_file(file))
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024) if found else None


def benchmark_adapter(
    factory: Callable[[], GuiAdapter],
    *,
    width: int,
    height: int,
    frames: int,
    installed_megabytes: float | None = None,
) -> AdapterBenchmarkResult:
    if frames <= 0:
        raise ValueError("benchmark frames must be positive")
    images = (
        synthetic_raster(width=width, height=height, phase=0),
        synthetic_raster(width=width, height=height, phase=1),
    )
    adapter = factory()
    startup = time.perf_counter()
    adapter.start(width, height)
    startup_ms = (time.perf_counter() - startup) * 1000.0
    timings: list[float] = []
    started = time.perf_counter()
    try:
        for index in range(frames):
            before = time.perf_counter()
            adapter.present(images[index & 1])
            adapter.pump()
            timings.append(time.perf_counter() - before)
    finally:
        adapter.close()
    elapsed = time.perf_counter() - started
    return AdapterBenchmarkResult(
        adapter=adapter.name,
        width=width,
        height=height,
        presented_frames=frames,
        startup_ms=startup_ms,
        elapsed_seconds=elapsed,
        presentation_fps=frames / elapsed if elapsed else float("inf"),
        mean_present_ms=statistics.fmean(timings) * 1000.0,
        p95_present_ms=_p95(timings) * 1000.0,
        rgb_bytes_per_frame=len(images[0].rgb),
        installed_megabytes=installed_megabytes,
    )


class FakeAdapter:
    name = "fake"

    def start(self, width: int, height: int) -> None:
        pass

    def present(self, image: RasterImage) -> None:
        self.image = image

    def pump(self) -> None:
        pass

    def close(self) -> None:
        pass


class PygameAdapter:
    name = "pygame-ce"

    def start(self, width: int, height: int) -> None:
        import pygame

        self.pygame = pygame
        pygame.init()
        self.screen = pygame.display.set_mode((width, height))

    def present(self, image: RasterImage) -> None:
        surface = self.pygame.image.frombytes(image.rgb, (image.width, image.height), "RGB")
        self.screen.blit(surface, (0, 0))
        self.pygame.display.flip()

    def pump(self) -> None:
        self.pygame.event.pump()

    def close(self) -> None:
        self.pygame.quit()


class PySide6Adapter:
    name = "PySide6"

    def start(self, width: int, height: int) -> None:
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import QApplication, QLabel

        self.QImage = QImage
        self.QPixmap = QPixmap
        self.app = QApplication.instance() or QApplication([])
        self.label = QLabel()
        self.label.resize(width, height)
        self.label.show()
        self.app.processEvents()

    def present(self, image: RasterImage) -> None:
        qimage = self.QImage(
            image.rgb,
            image.width,
            image.height,
            image.width * 3,
            self.QImage.Format.Format_RGB888,
        )
        self.label.setPixmap(self.QPixmap.fromImage(qimage))

    def pump(self) -> None:
        self.app.processEvents()

    def close(self) -> None:
        self.label.close()
        self.app.processEvents()


def adapter_factory(name: str, *, headless: bool) -> tuple[Callable[[], GuiAdapter], float | None]:
    if name == "fake":
        return FakeAdapter, None
    if name == "pygame":
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        return PygameAdapter, distribution_size_megabytes(("pygame-ce",))
    if name == "pyside6":
        if headless:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        size = distribution_size_megabytes(("PySide6_Essentials", "shiboken6"))
        return PySide6Adapter, size
    raise ValueError(f"unknown adapter: {name}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Direct-RGB native GUI adapter benchmark")
    parser.add_argument("--adapter", choices=("fake", "pygame", "pyside6"), required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--heights", default="200,400,800")
    parser.add_argument("--frames", type=int, default=400)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    factory, installed_megabytes = adapter_factory(args.adapter, headless=args.headless)
    for height in (int(value) for value in args.heights.split(",")):
        result = benchmark_adapter(
            factory,
            width=args.width,
            height=height,
            frames=args.frames,
            installed_megabytes=installed_megabytes,
        )
        print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
