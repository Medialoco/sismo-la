"""Look for a cataloged earthquake at the instant it must have arrived.

WHAT THIS IS NOT
================
This is not a second detector, and a shake found here is not a detection the
station made. The catalog said where to look. Every record produced by this
module carries ``detector: "retro"`` and every surface that shows it — journal,
dashboard, published snapshot, public page — keeps it in a category of its own,
labelled "confirmed at a known time" against the blind trigger's "detected
autonomously". Collapsing the two would turn a defensible result into a false
claim, so the separation is structural rather than a matter of wording.

WHY IT HELPS
============
The blind trigger examines something like 170000 independent windows a day and
has to be right about all of them, which pushes its threshold far out into the
tail of the noise: measured on this station's own noise, an earthquake-shaped
wavetrain needs about 2 mg of peak band-passed acceleration to fire it.

Searching a known instant tests a handful of windows per earthquake instead. The
same false-alarm budget is then met much closer to the noise, and the test can
average over the whole wavetrain rather than reacting within half a second.
Measured with this module's own estimator on this station's noise, that is worth
about a factor 5 in amplitude — see ``tools/retro-gain.py``, which computes the
figure by calling ``significance`` below, so the number quoted anywhere in the
repo and the code that runs on the board cannot drift apart.

HOW THE TEST WORKS
==================
1. The origin time and hypocentral distance give a window in which the shaking
   must have landed (``pipeline.travel_time_window``, P at 7 km/s to S at
   2.5 km/s plus margin), extended by a coda allowance.
2. Inside it, take the largest mean of the rms envelope over each candidate
   window length.
3. Compare it against the same statistic over the minutes immediately before,
   using the median of those windows as the baseline and their MAD as the
   dispersion. The comparison is deliberately against the LOCAL noise: this
   site's ambient level varies by a factor of three between a quiet night and a
   busy afternoon, so a fixed threshold would be simultaneously too strict at
   night and meaningless at noon.
4. The excursion has to clear ``z_min`` of that local dispersion, and the
   amplitude has to be one the event could actually deliver
   (``pipeline.amplitude_is_plausible``, the same veto the blind path uses).

Consequence worth stating plainly: this test only reaches its low threshold when
the site is at rest. In a busy period the local dispersion is large and the test
simply fails to confirm anything, which is the honest outcome — it cannot tell
an earthquake from the traffic, and it says so instead of guessing.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timedelta, timezone

from pipeline import amplitude_is_plausible, travel_time_window

# Candidate averaging lengths, seconds. A local M3 at 30 km shakes for a few
# seconds and an M4.5 at 120 km for tens, so no single length fits; the test
# takes the best and pays for the extra look in the multiplicity built into
# z_min.
WINDOWS_S = (5.0, 10.0, 20.0)
BASELINE_S = 180.0          # trailing noise reference
BASELINE_GAP_S = 5.0        # keep the baseline clear of the earliest arrival
POST_S = 20.0               # coda allowance after the latest S arrival
MIN_BASELINE_BINS = 6
# Floor on the dispersion, as a fraction of the baseline for a 1 s window.
#
# It is a guard, not the operating value: the envelope is quantised to 1 ug and
# a very quiet minute can hand back a MAD of exactly zero, which would make any
# excursion infinitely significant. Derived rather than picked: the band-passed
# 3-vector magnitude has a relative standard deviation of 0.42 sample to sample
# (chi with 3 degrees of freedom), the chain's equivalent noise bandwidth of
# 5.21 Hz gives ~10.4 independent samples a second, and each stored value is
# already an rms over one second, which halves the relative fluctuation of a
# power-like quantity. That is 0.42/(2*sqrt(10.4)) = 0.065 for a one-second
# sample, hence 0.065/sqrt(window_s) for the mean over a window.
#
# An earlier draft used 0.41/sqrt(window_s), having forgotten both the
# bandwidth and the per-second averaging. It was 3x too large, which does not
# fail loudly: the floor simply dominated the measured MAD everywhere, every
# significance came out three times too small, and the estimator looked merely
# conservative. Any change here must be checked against the null distribution
# printed by tools/retro-gain.py.
SIGMA_FLOOR_REL = 0.065
# Significance required to call an event confirmed.
#
# Set from the false-alarm budget against the MEASURED null distribution of this
# estimator (tools/retro-gain.py, which calls the function below on pure noise
# at the station's measured floor). About 1.2 cataloged M>=2 events a day within
# 160 km, so a fortnight is ~14 tests and a 10% chance of one false confirmation
# needs p < 7e-3 per test. The within-window multiplicity — three window lengths
# and a one-second slide over ~45 s — is already inside the null, which is why
# the number is calibrated rather than assumed.
Z_MIN = 4.0


def _mad_sigma(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    values = sorted(values)
    median = values[len(values) // 2]
    devs = sorted(abs(v - median) for v in values)
    return 1.4826 * devs[len(devs) // 2]


def _median(values: list[float]) -> float:
    values = sorted(values)
    n = len(values)
    if not n:
        return 0.0
    return values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])


def _window_means(samples, start: float, end: float, window_s: float,
                  step_s: float):
    """Means of ``rms`` over sliding windows of ``window_s`` in [start, end].

    ``samples`` is the (epoch, peak, rms) sequence. Sampling is nominally 1 Hz
    but a dropped batch leaves a gap, so windows are built from timestamps and a
    window holding less than 60% of its expected samples is discarded rather
    than averaged over a hole.
    """
    if not samples:
        return []
    out = []
    expected = max(1, int(window_s * 0.6))
    at = start
    i = 0
    while at + window_s <= end + 1e-9:
        while i < len(samples) and samples[i][0] < at:
            i += 1
        total = 0.0
        count = 0
        peak = 0.0
        j = i
        while j < len(samples) and samples[j][0] < at + window_s:
            total += samples[j][2]
            peak = max(peak, samples[j][1])
            count += 1
            j += 1
        if count >= expected:
            out.append((at, total / count, peak, count))
        at += step_s
    return out


def significance(samples, search_start: float, search_end: float,
                 windows_s=WINDOWS_S, baseline_s: float = BASELINE_S,
                 baseline_gap_s: float = BASELINE_GAP_S) -> dict | None:
    """How unusual the envelope is in [search_start, search_end].

    Pure function of the record, so ``tools/retro-gain.py`` can characterise it
    on synthetic data and the board runs exactly the same estimator.

    Returns the best window over all lengths, or None when there is not enough
    baseline to say anything.
    """
    best = None
    base_end = search_start - baseline_gap_s
    base_start = base_end - baseline_s
    for window_s in windows_s:
        # Non-overlapping baseline windows: overlapping ones would share
        # samples and understate the dispersion.
        base_bins = _window_means(samples, base_start, base_end, window_s,
                                  window_s)
        if len(base_bins) < MIN_BASELINE_BINS:
            continue
        base_values = [b[1] for b in base_bins]
        base = _median(base_values)
        if base <= 0:
            continue
        sigma = max(_mad_sigma(base_values),
                    base * SIGMA_FLOOR_REL / math.sqrt(window_s))
        if sigma <= 0:
            continue
        hits = _window_means(samples, search_start, search_end, window_s, 1.0)
        if not hits:
            continue
        at, mean, peak, count = max(hits, key=lambda h: h[1])
        z = (mean - base) / sigma
        if best is None or z > best["z"]:
            best = {
                "z": round(z, 2),
                "ratio": round(mean / base, 3),
                "window_s": window_s,
                "at": at,
                "rms_g": mean,
                "peak_g": peak,
                "baseline_g": base,
                "sigma_g": sigma,
                "n_baseline": len(base_bins),
                "n_samples": count,
            }
    return best


def search_window(quake, post_s: float = POST_S) -> tuple[float, float]:
    """Absolute epoch bounds in which this earthquake's shaking must have landed."""
    lo, hi = travel_time_window(getattr(quake, "distance_km", 0.0) or 0.0,
                                getattr(quake, "depth_km", 0.0) or 0.0)
    origin = quake.time.timestamp()
    return origin + lo, origin + hi + post_s


def scan_quake(store, quake, z_min: float = Z_MIN) -> dict | None:
    """Test one cataloged earthquake against the stored envelope.

    Returns a finding whether or not it clears ``z_min``: a "looked and found
    nothing" result is worth recording, because it is the difference between an
    earthquake the station missed and one it never had data for.
    """
    start, end = search_window(quake)
    read_from = datetime.fromtimestamp(start - BASELINE_S - BASELINE_GAP_S - 10,
                                       tz=timezone.utc)
    read_to = datetime.fromtimestamp(end + 10, tz=timezone.utc)
    samples = store.read(read_from, read_to)
    if not samples:
        return None

    stat = significance(samples, start, end)
    if stat is None:
        return None

    distance = getattr(quake, "distance_km", 0.0) or 0.0
    depth = getattr(quake, "depth_km", 0.0) or 0.0
    plausible = amplitude_is_plausible(stat["peak_g"], quake.magnitude,
                                       distance, depth)
    confirmed = bool(stat["z"] >= z_min and plausible)
    return {
        "event_id": quake.event_id,
        "origin_time": quake.time.isoformat(),
        "magnitude": quake.magnitude,
        "place": quake.place,
        "distance_km": round(distance, 1),
        "depth_km": round(depth, 1),
        "detector": "retro",
        "confirmed": confirmed,
        "plausible": plausible,
        "z": stat["z"],
        "ratio": stat["ratio"],
        "window_s": stat["window_s"],
        "rms_g": round(stat["rms_g"], 7),
        "peak_g": round(stat["peak_g"], 7),
        "baseline_g": round(stat["baseline_g"], 7),
        "lag_s": round(stat["at"] - quake.time.timestamp(), 1),
        "n_baseline": stat["n_baseline"],
        "scanned": datetime.now(timezone.utc).isoformat(),
    }


class RetroLog:
    """Findings, keyed by event id so a re-scan updates rather than duplicates.

    Re-scanning matters: the USGS revises magnitudes and locations for hours
    after an event, and the arrival window depends on the distance, so a scan
    run one minute after the origin time is not the last word.
    """

    def __init__(self, state_file: str) -> None:
        self.state_file = state_file
        self.findings: dict[str, dict] = {}

    def load(self) -> None:
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.findings = {k: v for k, v in (raw.get("findings") or {}).items()}
        except (OSError, ValueError) as e:
            print(f"[retro] could not read {self.state_file}: {e}", flush=True)

    def save(self) -> None:
        if not self.state_file:
            return
        try:
            tmp = self.state_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"findings": self.findings}, f, indent=1)
            os.replace(tmp, self.state_file)
        except OSError as e:
            print(f"[retro] could not write {self.state_file}: {e}", flush=True)

    def record(self, finding: dict) -> bool:
        """Store a finding. True when it is newly confirmed."""
        event_id = finding["event_id"]
        was = self.findings.get(event_id, {}).get("confirmed", False)
        self.findings[event_id] = finding
        return bool(finding["confirmed"] and not was)

    def confirmed(self) -> list[dict]:
        out = [f for f in self.findings.values() if f.get("confirmed")]
        out.sort(key=lambda f: f.get("origin_time") or "")
        return out

    def status(self) -> str:
        n = len(self.findings)
        c = len(self.confirmed())
        if not n:
            return "retrospective search: nothing scanned yet"
        return (f"retrospective search: {c} confirmed of {n} cataloged events "
                f"scanned")
