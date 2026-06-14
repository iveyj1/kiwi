"""Fixture loading helpers for KiwiSDR JSONL event streams."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FixtureEvent:
    """One event from a JSONL fixture."""

    t: float
    dir: str
    stream: str
    type: str
    raw: dict[str, Any]

    @property
    def binary_payload(self) -> bytes:
        """Return decoded binary payload for base64-encoded binary events."""
        if self.type != "binary":
            raise ValueError(f"event type is not binary: {self.type!r}")
        encoding = self.raw.get("encoding")
        if encoding != "base64":
            raise ValueError(f"unsupported binary event encoding: {encoding!r}")
        data = self.raw.get("data")
        if not isinstance(data, str):
            raise ValueError("binary event data must be a base64 string")
        return base64.b64decode(data, validate=True)


def load_jsonl_events(path: str | Path) -> list[FixtureEvent]:
    """Load non-metadata events from a KiwiSDR JSONL fixture."""
    return list(iter_jsonl_events(path))


def iter_jsonl_events(path: str | Path) -> Iterator[FixtureEvent]:
    """Yield non-metadata events from a KiwiSDR JSONL fixture."""
    with Path(path).open("r", encoding="utf-8") as fp:
        for line_no, line in enumerate(fp, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("dir") == "meta":
                continue
            try:
                yield FixtureEvent(
                    t=float(obj["t"]),
                    dir=str(obj["dir"]),
                    stream=str(obj["stream"]),
                    type=str(obj["type"]),
                    raw=obj,
                )
            except KeyError as exc:
                raise ValueError(f"missing required fixture key on line {line_no}: {exc}") from exc
