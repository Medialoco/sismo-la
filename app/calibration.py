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


@dataclass
class DistanceModel:
    """Single-station distance estimator, learned from USGS matches.

    Coda duration and dominant frequency both correlate with epicentral
    distance, so we fit:

        log10(R_km) ~= a * log10(dur_ms) + b * log10(dom_hz) + c

    from (local shake, confirmed USGS earthquake) pairs. With a distance in
    hand, the amplitude model can invert magnitude from PGA alone — the device
    then produces a full (distance, magnitude) estimate on its own.
    """

    state_file: str
    min_points: int = 5
    points: list[dict] = field(default_factory=list)
    coeffs: list[float] | None = None
    rmse_log10: float | None = None

    def load(self) -> None:
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.points = raw.get("points", [])
            self.coeffs = raw.get("coeffs")
            self.rmse_log10 = raw.get("rmse_log10")
            self._fit()

    def save(self) -> None:
        payload = {
            "points": self.points,
            "coeffs": self.coeffs,
            "rmse_log10": self.rmse_log10,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @property
    def ready(self) -> bool:
        return self.coeffs is not None and len(self.points) >= self.min_points

    def add_point(self, dur_ms: float, dom_hz: float, distance_km: float,
                  event_id: str = "") -> None:
        if not dur_ms or dur_ms <= 0 or dom_hz is None or distance_km <= 0:
            return
        self.points.append(
            {"dur_ms": dur_ms, "dom_hz": dom_hz, "distance_km": distance_km,
             "event_id": event_id}
        )
        self._fit()
        self.save()

    def _fit(self) -> None:
        if len(self.points) < 3:
            return
        x = np.array(
            [[math.log10(p["dur_ms"]), math.log10(max(p["dom_hz"], 0.1)), 1.0]
             for p in self.points]
        )
        y = np.array([math.log10(p["distance_km"]) for p in self.points])
        coeffs, *_ = np.linalg.lstsq(x, y, rcond=None)
        residuals = y - x @ coeffs
        self.coeffs = coeffs.tolist()
        self.rmse_log10 = float(np.sqrt(np.mean(residuals**2)))

    def estimate_distance(self, dur_ms: float, dom_hz: float) -> float | None:
        if self.coeffs is None or not dur_ms or dur_ms <= 0 or dom_hz is None:
            return None
        a, b, c = self.coeffs
        logr = a * math.log10(dur_ms) + b * math.log10(max(dom_hz, 0.1)) + c
        return float(min(max(10 ** logr, 1.0), 1000.0))  # clamp to sane range

    def status(self) -> str:
        n = len(self.points)
        if not self.ready:
            return f"distance model learning ({n}/{self.min_points} points)"
        return f"distance model ready ({n} points, RMSE={self.rmse_log10:.2f} log10km)"
