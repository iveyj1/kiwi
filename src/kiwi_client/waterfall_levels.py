"""Manual and percentile-based automatic waterfall display levels."""

from __future__ import annotations

from dataclasses import dataclass, field

from kiwi_client.waterfall_snapshots import WaterfallSnapshot


@dataclass
class WaterfallLevelController:
    min_dbm: float = -100
    max_dbm: float = -40
    automatic: bool = False
    low_percentile: float = 0.05
    high_percentile: float = 0.98
    padding_db: float = 3
    smoothing: float = 0.20
    minimum_range_db: float = 20
    update_generations: int = 20
    _last_generation: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_dbm <= self.min_dbm:
            raise ValueError("waterfall max dB must exceed min dB")
        if not 0 <= self.low_percentile < self.high_percentile <= 1:
            raise ValueError("waterfall percentiles must be ordered within 0..1")
        if not 0 < self.smoothing <= 1:
            raise ValueError("waterfall level smoothing must be within 0..1")
        if self.padding_db < 0 or self.minimum_range_db <= 0 or self.update_generations <= 0:
            raise ValueError("waterfall level padding/range/cadence must be positive")

    def set_automatic(self, enabled: bool) -> bool:
        changed = self.automatic != enabled
        self.automatic = enabled
        if enabled:
            self._last_generation = 0
        return changed

    def adjust_min(self, delta_db: float) -> bool:
        self.automatic = False
        value = min(self.min_dbm + delta_db, self.max_dbm - self.minimum_range_db)
        changed = value != self.min_dbm
        self.min_dbm = value
        return changed

    def adjust_max(self, delta_db: float) -> bool:
        self.automatic = False
        value = max(self.max_dbm + delta_db, self.min_dbm + self.minimum_range_db)
        changed = value != self.max_dbm
        self.max_dbm = value
        return changed

    @staticmethod
    def _percentile(values: list[int], fraction: float) -> float:
        return float(values[round((len(values) - 1) * fraction)])

    def observe(self, snapshot: WaterfallSnapshot) -> bool:
        if not self.automatic or snapshot.generation - self._last_generation < self.update_generations:
            return False
        values = sorted(value for row in snapshot.rows for value in row.dbm)
        if not values:
            return False
        target_min = max(-255.0, self._percentile(values, self.low_percentile) - self.padding_db)
        target_max = min(0.0, self._percentile(values, self.high_percentile) + self.padding_db)
        if target_max - target_min < self.minimum_range_db:
            midpoint = (target_min + target_max) / 2
            target_min = midpoint - self.minimum_range_db / 2
            target_max = midpoint + self.minimum_range_db / 2
        new_min = self.min_dbm + (target_min - self.min_dbm) * self.smoothing
        new_max = self.max_dbm + (target_max - self.max_dbm) * self.smoothing
        self._last_generation = snapshot.generation
        if abs(new_min - self.min_dbm) < 0.25 and abs(new_max - self.max_dbm) < 0.25:
            return False
        self.min_dbm = new_min
        self.max_dbm = new_max
        return True

    def status_text(self) -> str:
        mode = "auto" if self.automatic else "manual"
        return f"scale {mode} {self.min_dbm:.0f}..{self.max_dbm:.0f} dB"
