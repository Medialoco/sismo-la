"""AI filter: earthquake vs local noise (truck, door, footsteps...).

A lightweight online logistic-regression classifier over the event features the
MCU already emits: PGA, duration, dominant frequency. It needs no offline
training set: labels come for free from the USGS correlation loop —

  - a detection matched to a cataloged earthquake  -> label 1 (quake)
  - an unmatched detection                          -> label 0 (noise)

so the device learns the *local* signature of real quakes at its own location,
exactly like the amplitude calibration. Weights and samples are persisted to
disk. Runs fine on the Dragonwing MPU (numpy only).

Physical intuition the model can capture: real (even small) earthquakes carry
low dominant frequencies (~1-10 Hz) and last several seconds, while a passing
truck is short, higher-frequency, and its amplitude/duration ratio differs.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import numpy as np

# Feature vector: [log10(pga_g), log10(dur_ms), dom_hz, 1.0 (bias)]
N_FEATURES = 4
LEARNING_RATE = 0.05
EPOCHS_PER_UPDATE = 40  # small dataset: refit hard on every new sample
MIN_PER_CLASS = 3       # predictions stay None until both classes are seen


def event_features(pga_g: float, dur_ms: float, dom_hz: float) -> list[float] | None:
    if pga_g <= 0 or dur_ms is None or dur_ms <= 0 or dom_hz is None:
        return None
    return [math.log10(pga_g), math.log10(dur_ms), float(dom_hz), 1.0]


@dataclass
class QuakeNoiseClassifier:
    state_file: str
    samples: list[dict] = field(default_factory=list)
    weights: list[float] | None = None

    # ---- persistence -------------------------------------------------------
    def load(self) -> None:
        if os.path.exists(self.state_file):
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.samples = raw.get("samples", [])
            self.weights = raw.get("weights")

    def save(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump({"samples": self.samples, "weights": self.weights}, f, indent=2)

    # ---- training ----------------------------------------------------------
    @property
    def counts(self) -> tuple[int, int]:
        pos = sum(1 for s in self.samples if s["label"] == 1)
        return pos, len(self.samples) - pos

    @property
    def ready(self) -> bool:
        pos, neg = self.counts
        return self.weights is not None and pos >= MIN_PER_CLASS and neg >= MIN_PER_CLASS

    def add_sample(self, pga_g: float, dur_ms: float, dom_hz: float,
                   label: int) -> None:
        x = event_features(pga_g, dur_ms, dom_hz)
        if x is None:
            return
        self.samples.append({"x": x, "label": int(label)})
        self._fit()
        self.save()

    def _fit(self) -> None:
        pos, neg = self.counts
        if pos == 0 or neg == 0:
            return
        xs = np.array([s["x"] for s in self.samples])
        ys = np.array([s["label"] for s in self.samples], dtype=float)
        # Standardize non-bias columns so the SGD is well-conditioned.
        mu = xs[:, :-1].mean(axis=0)
        sd = xs[:, :-1].std(axis=0) + 1e-9
        xn = xs.copy()
        xn[:, :-1] = (xs[:, :-1] - mu) / sd

        w = np.array(self.weights["w"]) if isinstance(self.weights, dict) else np.zeros(N_FEATURES)
        if w.shape != (N_FEATURES,):
            w = np.zeros(N_FEATURES)
        # Balance classes so a flood of noise does not drown the rare quakes.
        cw = np.where(ys == 1, len(ys) / (2 * pos), len(ys) / (2 * neg))
        for _ in range(EPOCHS_PER_UPDATE):
            p = 1.0 / (1.0 + np.exp(-xn @ w))
            grad = xn.T @ ((p - ys) * cw) / len(ys)
            w -= LEARNING_RATE * grad
        self.weights = {"w": w.tolist(), "mu": mu.tolist(), "sd": sd.tolist()}

    # ---- inference ---------------------------------------------------------
    def predict_proba(self, pga_g: float, dur_ms: float, dom_hz: float) -> float | None:
        """Probability that the event is a real earthquake, or None if the
        classifier has not seen enough of both classes yet."""
        if not self.ready:
            return None
        x = event_features(pga_g, dur_ms, dom_hz)
        if x is None:
            return None
        w = np.array(self.weights["w"])
        mu = np.array(self.weights["mu"])
        sd = np.array(self.weights["sd"])
        xn = np.array(x)
        xn[:-1] = (xn[:-1] - mu) / sd
        return float(1.0 / (1.0 + np.exp(-xn @ w)))

    def status(self) -> str:
        pos, neg = self.counts
        if not self.ready:
            return f"AI filter learning ({pos} quakes / {neg} noise, needs {MIN_PER_CLASS}+ each)"
        return f"AI filter active ({pos} quakes / {neg} noise)"
