#!/usr/bin/env python3
"""What a quieter accelerometer would buy this station, in detections per year.

Convolves a candidate sensor's noise density with the real USGS catalog around
the station, through the refit ground-motion law in `python/pipeline.py`. It is
the same computation that produced the station's published 2.0-9.8/year figure
(`docs/sensor-upgrade.md`), made re-runnable so a sensor choice can be argued
from numbers instead of from datasheet headlines.

The chain, and the one assumption that carries it: the trigger is STA/LTA, so
the amplitude a shake needs in order to fire is proportional to the noise floor
the LTA tracks, and the floor at rest was *measured* to be the sensor's own
white noise -- 0.00036 g in band against 0.00040 g predicted from the datasheet,
and 0.00052 g against 0.00050 g wideband, the two channels averaged over the
same ten seconds. Swapping the sensor therefore scales the trigger floor by
the ratio of noise densities -- as long as the new floor stays sensor-limited.
Below roughly 1e-4 g that stops being safe, because the site's own contribution
was only shown to be negligible *at 0.00036 g*, and the script says so.

Usage:
    python3 tools/sensor-gain.py [--lat L --lon L] [catalog.geojson]

With no catalog argument it queries USGS directly. The station position comes
from python/config.yaml when present (gitignored, board-only) and otherwise
falls back to the neutral downtown placeholder -- which is NOT where the board
is and inflates the rates by about 24%, because the station sits further from
the seismicity that dominates the downtown counts. Pass --lat/--lon to
reproduce the published figures.
"""
from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path

# Refit against 12324 USGS ShakeMap PGA values; see python/pipeline.py.
A, B, C = 0.8668, -1.7400, -3.3053
SIGMA = 0.3903

YEARS = 5.0
RADIUS_KM = 160.0
MIN_MAG = 2.0

# Measured on the hardware, 2026-09-01. The smallest PGA that ever triggered
# was 0.0044 g in the quietest window, before the band-pass; the band-pass
# lowered the at-rest floor by a measured 1.43x, and the trigger floor follows
# it because STA/LTA is a ratio.
TRIGGER_FLOOR_G = 0.0044 / 1.43
LSM6DSOX_UG_RTHZ = 110.0

# Site amplification is unknown for an indoor mount, and station-to-station
# scatter dominates the fit (0.347 of 0.390 log10), so every rate is a range.
SITE_AMPLIFICATION = (1.0, 4.0)

# Days left to the contest deadline, for the last column.
DEADLINE_DAYS = 12

# Densities are datasheet values at the stated full scale, not vendor-page
# numbers; the range matters because the density moves with it.
CANDIDATES = [
    # (label, noise density ug/rtHz, full scale the density applies to)
    ("KX134-1211", 300.0, "+-8 g, ODR 50 Hz"),
    ("KX132-1211", 130.0, "+-2 g"),
    ("LSM6DSOX (current)", 110.0, "+-4 g"),
    ("ADXL357", 75.0, "+-10 g"),
    ("ISM330DHCX", 60.0, "HP, any FS"),
    ("SCA3300-D01", 44.0, "+-3 g, mode 1"),
    ("ADXL355", 22.5, "+-2 g"),
    ("IIS2ICLX", 15.0, "2-axis, any FS"),
]


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def station_position(override: tuple[float, float] | None) -> tuple[float, float, str]:
    if override:
        return override[0], override[1], "command line"
    cfg = Path(__file__).resolve().parent.parent / "python" / "config.yaml"
    if not cfg.exists():
        cfg = cfg.with_name("config.example.yaml")
    lat = lon = None
    for line in cfg.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("lat:"):
            lat = float(stripped.split(":", 1)[1].split("#")[0])
        elif stripped.startswith("lon:"):
            lon = float(stripped.split(":", 1)[1].split("#")[0])
    if lat is None or lon is None:
        raise SystemExit(f"no station position in {cfg}")
    return lat, lon, cfg.name


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def load_catalog(path: str | None,
                 override: tuple[float, float] | None = None
                 ) -> list[tuple[float, float, float]]:
    """Return (magnitude, epicentral distance km, depth km) per event."""
    lat, lon, which = station_position(override)
    if path:
        raw = json.loads(Path(path).read_text())
    else:
        url = (
            "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
            f"&latitude={lat}&longitude={lon}&maxradiuskm={RADIUS_KM:g}"
            f"&minmagnitude={MIN_MAG:g}"
            "&starttime=2021-09-01T00:00:00Z&endtime=2026-09-01T00:00:00Z"
        )
        with urllib.request.urlopen(url, timeout=60) as fh:
            raw = json.loads(fh.read())
    out = []
    for feat in raw["features"]:
        mag = feat["properties"].get("mag")
        coords = feat["geometry"]["coordinates"]
        if mag is None or coords is None:
            continue
        qlon, qlat, depth = coords[0], coords[1], coords[2] or 0.0
        out.append((float(mag), haversine_km(lat, lon, qlat, qlon), float(depth)))
    print(f"[catalog] {len(out)} events, position from {which}")
    return out


def rate_per_year(events, floor_g: float, amplification: float) -> float:
    """Expected genuine detections per year at a given trigger floor.

    Each event contributes the probability that its ground motion at the
    station exceeded the floor, the 0.390 log10 scatter of the fit standing in
    for path and site luck. Summing probabilities rather than counting events
    above the median matters: the rate is dominated by the tail.
    """
    target = math.log10(floor_g) - math.log10(amplification)
    total = 0.0
    for mag, dist_km, depth_km in events:
        hypo = max(math.hypot(dist_km, depth_km), 3.0)
        median = A * mag + B * math.log10(hypo) + C
        total += norm_cdf((median - target) / SIGMA)
    return total / YEARS


def magnitude_needed(floor_g: float, dist_km: float, depth_km: float = 8.0) -> float:
    hypo = max(math.hypot(dist_km, depth_km), 3.0)
    return (math.log10(floor_g) - B * math.log10(hypo) - C) / A


def main() -> None:
    args = sys.argv[1:]
    override = None
    if "--lat" in args and "--lon" in args:
        override = (float(args[args.index("--lat") + 1]),
                    float(args[args.index("--lon") + 1]))
    catalog = next((a for a in args if not a.startswith("--")
                    and not _is_number(a)), None)
    events = load_catalog(catalog, override)
    lo, hi = SITE_AMPLIFICATION
    dists = (10, 30, 50, 100, 160)

    print()
    print("floor scaled from the MEASURED 0.00308 g trigger floor at "
          f"{LSM6DSOX_UG_RTHZ:g} ug/rtHz")
    header = (f"{'sensor':20s} {'ug/rtHz':>8s} {'floor g':>9s} "
              + " ".join(f"{'M@' + str(d):>6s}" for d in dists)
              + f" {'det/yr':>13s} {'wait (d)':>10s} "
              f"{'P(' + str(DEADLINE_DAYS) + 'd)':>11s}")
    print(header)
    print("-" * len(header))
    for label, density, fs in CANDIDATES:
        floor = TRIGGER_FLOOR_G * density / LSM6DSOX_UG_RTHZ
        mags = " ".join(f"{magnitude_needed(floor, d):6.1f}" for d in dists)
        r_lo = rate_per_year(events, floor, lo)
        r_hi = rate_per_year(events, floor, hi)
        wait = f"{365 / r_hi:.0f}-{365 / r_lo:.0f}"
        # Poisson: one or more genuine detections inside the remaining window.
        p_lo = 1 - math.exp(-r_lo * DEADLINE_DAYS / 365)
        p_hi = 1 - math.exp(-r_hi * DEADLINE_DAYS / 365)
        print(f"{label:20s} {density:8.1f} {floor:9.5f} {mags} "
              f"{r_lo:5.1f}-{r_hi:6.1f} {wait:>10s} "
              f"{100 * p_lo:4.0f}-{100 * p_hi:3.0f}%  ({fs})")

    print()
    print("Add +-0.45 Mw (1 sigma) to every magnitude; below M3 it is "
          "extrapolation (smallest event in the fit is M3.03).")
    print("Rates below ~1e-4 g assume the floor stays sensor-limited, which "
          "was only measured AT 0.00036 g.")


if __name__ == "__main__":
    main()
