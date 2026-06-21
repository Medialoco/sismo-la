"""Calibration model: measured amplitude -> magnitude.

We fit, by least squares, the linear relation:

    Mw ~= a * log10(PGA_g) + b * log10(distance_km) + c

from the pairs (local shake, confirmed USGS earthquake). The model is persisted
to disk so it survives restarts.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict, field

import numpy as np


@dataclass
class CalPoint:
    pga_g: float
    distance_km: float
    magnitude: float
    event_id: str = ""


@dataclass
class CalibrationModel:
    state_file: str
    min_points: int = 8
    points: list[CalPoint] = field(default_factory=list)
    coeffs: list[float] | None = None  # [a, b, c]
    rmse: float | None = None

    def load(self) -> None:
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.points = [CalPoint(**p) for p in raw.get("points", [])]
            self.coeffs = raw.get("coeffs")
            self.rmse = raw.get("rmse")
            self._fit()

    def save(self) -> None:
        payload = {
            "points": [asdict(p) for p in self.points],
            "coeffs": self.coeffs,
            "rmse": self.rmse,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @property
    def ready(self) -> bool:
        return self.coeffs is not None and len(self.points) >= self.min_points

    def add_point(self, pga_g: float, distance_km: float, magnitude: float,
                  event_id: str = "") -> None:
        if pga_g <= 0 or distance_km <= 0:
            return
        self.points.append(CalPoint(pga_g, distance_km, magnitude, event_id))
        self._fit()
        self.save()

    def _design_matrix(self, pts: list[CalPoint]) -> np.ndarray:
        return np.array(
            [[math.log10(p.pga_g), math.log10(p.distance_km), 1.0] for p in pts]
        )

    def _fit(self) -> None:
        if len(self.points) < 3:
            return
        x = self._design_matrix(self.points)
        y = np.array([p.magnitude for p in self.points])
        coeffs, *_ = np.linalg.lstsq(x, y, rcond=None)
        residuals = y - x @ coeffs
        self.coeffs = coeffs.tolist()
        self.rmse = float(np.sqrt(np.mean(residuals**2)))

    def estimate_magnitude(self, pga_g: float, distance_km: float) -> float | None:
        if self.coeffs is None or pga_g <= 0 or distance_km <= 0:
            return None
        a, b, c = self.coeffs
        return a * math.log10(pga_g) + b * math.log10(distance_km) + c

    def status(self) -> str:
        n = len(self.points)
        if not self.ready:
            return f"not calibrated ({n}/{self.min_points} points)"
        return f"calibrated ({n} points, RMSE={self.rmse:.2f} Mw)"
