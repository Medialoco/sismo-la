#!/usr/bin/env python3
"""What does searching a KNOWN instant buy over the blind STA/LTA trigger?

    python3 tools/retro-gain.py
    python3 tools/retro-gain.py --floor 0.00036 --catalog /tmp/catalog5y.json

Everything here is measured or simulated on this station's own numbers, and the
retrospective side calls ``retro.significance`` — the estimator that actually
runs on the board — so the figure quoted in the documentation and the code that
produces it cannot drift apart.

Method, in three steps.

1. NOISE. White, band-limited by the firmware's own 0.7-12 Hz cascade, scaled so
   the in-band envelope mean equals the station's measured at-rest floor
   (0.00036 g). That model is not an assumption: the two-channel heartbeat
   measurement put the at-rest floor on the LSM6DSOX's datasheet white-noise
   line in two independent bands, 10% low in band and 4% high wideband
   (AGENTS.md, "The seismic band-pass").

2. THRESHOLDS. Both detectors are run on the same synthetic earthquake
   wavetrains buried in that noise, and the amplitude each one needs is found by
   bisection. The blind side is the exact firmware STA/LTA (0.5 s / 10 s
   exponential averages, TRIGGER_ON = 2.5); the retrospective side is
   ``retro.significance`` on a 1 Hz envelope built exactly as the sketch builds
   it. Because both sides see the same noise and the same signal, the RATIO is
   robust even where the absolute scale depends on convention (this station
   reports the peak of the band-passed 3-vector magnitude, not a horizontal
   component).

3. RATE. The amplitude threshold is converted to a magnitude threshold with
   REF_GMPE and convolved with the real USGS catalog around the station, exactly
   as the earlier sensitivity estimates in AGENTS.md were, so the before/after
   comparison is like for like.

The honest caveat is printed with the result: the retrospective threshold is only
reachable when the site is at rest, and this station is at rest roughly half the
time.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "python"))

import retro                                  # noqa: E402
from pipeline import REF_GMPE, REF_GMPE_SIGMA, load_config  # noqa: E402

FS = 95.3               # measured steady-state loop rate on this board
BP_HP, BP_LP = 0.7, 12.0
STA_SEC, LTA_SEC = 0.5, 10.0
TRIGGER_ON = 2.5
SEARCH_LEN_S = 300.0
T0_S = 240.0            # arrival instant inside the simulated record

rng = np.random.default_rng(20260901)


# --------------------------------------------------------------- the cascade
def transfer(n: int, fs: float = FS) -> np.ndarray:
    """Exact frequency response of the firmware's band-pass, unity in band.

    Two one-pole high-pass sections then two one-pole low-pass sections, with
    the same normalisation the sketch applies at f0 = sqrt(0.7*12) Hz.
    """
    a = math.exp(-2 * math.pi * BP_HP / fs)
    b = 1 - math.exp(-2 * math.pi * BP_LP / fs)
    theta = 2 * math.pi * math.sqrt(BP_HP * BP_LP) / fs
    c = math.cos(theta)
    mhp = a * 2 * math.sin(theta / 2) / math.sqrt(1 - 2 * a * c + a * a)
    p = 1 - b
    mlp = b / math.sqrt(1 - 2 * p * c + p * p)
    norm = 1.0 / (mhp * mhp * mlp * mlp)

    z = np.exp(-2j * np.pi * np.fft.rfftfreq(n))
    hp = a * (1 - z) / (1 - a * z)
    lp = b / (1 - p * z)
    return norm * hp ** 2 * lp ** 2


def filt(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    return np.fft.irfft(np.fft.rfft(x) * h, n=len(x))


N = int(SEARCH_LEN_S * FS)
H = transfer(N)


def noise3() -> list[np.ndarray]:
    return [filt(rng.standard_normal(N), H) for _ in range(3)]


def envelope(axes: list[np.ndarray]) -> np.ndarray:
    return np.sqrt(sum(a * a for a in axes))


def one_hz(env: np.ndarray) -> list[tuple[float, float, float]]:
    """The record the sketch keeps: per second, the peak and the rms."""
    per = int(round(FS))
    out = []
    for k in range(len(env) // per):
        chunk = env[k * per:(k + 1) * per]
        out.append((float(k + 1), float(chunk.max()),
                    float(math.sqrt(float((chunk ** 2).mean())))))
    return out


# ------------------------------------------------------------- the detectors
def blind_triggers(env: np.ndarray) -> bool:
    """The exact firmware STA/LTA."""
    sta_w = 2.0 / (STA_SEC * FS + 1.0)
    lta_w = 2.0 / (LTA_SEC * FS + 1.0)
    sta = lta = max(float(env[0]), 1e-6)
    warm = int(LTA_SEC * FS)
    for v in env[:warm]:
        lta += lta_w * (v - lta)
        sta += sta_w * (v - sta)
    for v in env[warm:]:
        sta += sta_w * (v - sta)
        lta = max(lta + lta_w * (v - lta), 1e-7)
        if sta / lta > TRIGGER_ON:
            return True
    return False


def retro_z(env: np.ndarray, lo_s: float, hi_s: float) -> float:
    stat = retro.significance(one_hz(env), lo_s, hi_s)
    return stat["z"] if stat else -99.0


def wavelet3(peak_g: float, f_hz: float, dur_s: float) -> list[np.ndarray]:
    """An earthquake-shaped wavetrain: rise, then an exponentially decaying coda.

    Scaled so the band-passed 3-vector magnitude peaks at ``peak_g``, which is
    the quantity the firmware reports as ``pga_g`` and the quantity REF_GMPE
    predicts.
    """
    t = np.arange(N) / FS - T0_S
    tau = 0.25 * dur_s
    ramp = np.clip(t, 0.0, None)
    env = ramp / tau * np.exp(1 - ramp / tau)
    axes = []
    for _ in range(3):
        phase = rng.uniform(0, 2 * math.pi)
        wobble = 0.6 * np.sin(2 * math.pi * 0.3 * np.arange(N) / FS)
        axes.append(filt(env * np.sin(2 * math.pi * f_hz * np.arange(N) / FS
                                      + phase + wobble), H))
    mag = envelope(axes)
    return [a * (peak_g / float(mag.max())) for a in axes]


def bisect(test, f_hz: float, dur_s: float, scale: float, trials: int,
           hit: float = 0.5) -> float:
    lo, hi = 1e-5, 0.3
    for _ in range(17):
        mid = math.sqrt(lo * hi)
        hits = 0
        for _ in range(trials):
            axes = [a * scale for a in noise3()]
            sig = wavelet3(mid, f_hz, dur_s)
            if test(envelope([a + s for a, s in zip(axes, sig)])):
                hits += 1
        if hits / trials >= hit:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo * hi)


# ------------------------------------------------------------------ the rate
def catalog(path: str | None, lat: float, lon: float, years: float):
    """Real USGS events around (lat, lon), as (magnitude, hypocentral km).

    The cache records the centre it was fetched around and this refuses to use
    it from anywhere else. A cache is a radius-160 km disc, so reusing one
    around a different centre silently truncates the catalog on one side and
    mis-states every distance — which is exactly the class of error the station
    already made once by running for weeks on a position 15.5 km off.
    """
    if path and os.path.exists(path):
        raw = json.load(open(path))
        centre = raw.get("sismo_centre")
        if centre and (abs(centre[0] - lat) > 0.02 or abs(centre[1] - lon) > 0.02):
            raise SystemExit(
                f"catalog cache {path} was fetched around "
                f"{centre[0]}, {centre[1]} but the station is at {lat}, {lon}. "
                "Delete the cache or pass --lat/--lon to match it.")
        if not centre:
            print(f"WARNING: {path} carries no centre; assuming {lat}, {lon}")
    else:
        import requests
        start = datetime.now(timezone.utc).replace(microsecond=0)
        raw = requests.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={"format": "geojson", "latitude": lat, "longitude": lon,
                    "maxradiuskm": 160, "minmagnitude": 2.0,
                    "starttime": (start.replace(year=start.year - int(years))
                                  ).strftime("%Y-%m-%d"),
                    "endtime": start.strftime("%Y-%m-%d"), "orderby": "time"},
            timeout=120).json()
        raw["sismo_centre"] = [lat, lon]
        if path:
            json.dump(raw, open(path, "w"))
    out = []
    for f in raw.get("features", []):
        lon2, lat2, dep = (f["geometry"]["coordinates"] + [0, 0, 0])[:3]
        mag = f["properties"].get("mag")
        if mag is None or lat2 is None:
            continue
        r = 6371.0
        p1, p2 = math.radians(lat), math.radians(lat2)
        h = (math.sin((p2 - p1) / 2) ** 2
             + math.cos(p1) * math.cos(p2)
             * math.sin(math.radians(lon2 - lon) / 2) ** 2)
        d = 2 * r * math.asin(math.sqrt(h))
        out.append((float(mag), math.hypot(d, max(dep or 0.0, 0.0))))
    return out


def rate_per_year(events, thresh_g: float, amp: float, years: float) -> float:
    a, b, c = REF_GMPE
    total = 0.0
    for mag, hypo in events:
        pred = a * mag + b * math.log10(max(hypo, 3.0)) + c + math.log10(amp)
        z = (pred - math.log10(thresh_g)) / REF_GMPE_SIGMA
        total += 0.5 * math.erfc(-z / math.sqrt(2))
    return total / years


def null_from_record(directory: str, samples: int = 4000) -> list[float]:
    """The estimator's null distribution at random instants of the real record.

    The synthetic null assumes the noise is white and stationary. It is neither:
    a door, a passing truck or the daily rhythm of a house all raise the
    envelope, and the whole reason the test compares against the trailing
    minutes rather than a constant is to survive that. This measures how well
    it does, on the station's own recording, at instants where nothing was
    announced — so every excursion found here is by construction a false one.
    """
    from envelope import EnvelopeStore

    store = EnvelopeStore(directory, retention_days=0)
    out: list[float] = []
    span = retro.BASELINE_S + retro.BASELINE_GAP_S + 60.0
    for day in store.days():
        start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        record = store.read(start, start.replace(hour=23, minute=59, second=59))
        if len(record) < span + 120:
            continue
        first, last = record[0][0], record[-1][0]
        at = first + span
        step = max(30.0, (last - first) / max(1, samples // max(1, len(store.days()))))
        while at + 60.0 <= last:
            stat = retro.significance(record, at, at + 45.0)
            if stat:
                out.append(stat["z"])
            at += step
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--floor", type=float, default=0.00036,
                    help="measured at-rest in-band envelope mean, g")
    ap.add_argument("--catalog", default="", help="cached USGS geojson")
    ap.add_argument("--lat", type=float, default=None,
                    help="override the station latitude from the config")
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--from-envelope", default="",
                    help="also measure the null distribution on the station's "
                         "REAL recorded envelope instead of synthetic noise; "
                         "this is the only check that covers non-stationary "
                         "site noise, which the white model does not")
    ap.add_argument("--years", type=float, default=5.0)
    ap.add_argument("--null-trials", type=int, default=300)
    ap.add_argument("--trials", type=int, default=13)
    ap.add_argument("--quiet-fraction", type=float, default=0.47,
                    help="fraction of the time the site is at rest; measured "
                         "0.47 over 17 logged hours, and that is a floor "
                         "because the quietest local hours are missing")
    args = ap.parse_args()

    # scale the white noise to the measured floor
    cal = envelope(noise3())
    scale = args.floor / float(cal.mean())
    print(f"noise: white, band-limited, scaled to an in-band envelope mean of "
          f"{args.floor:.5f} g")
    print(f"       per-axis rms {scale * float(noise3()[0].std()):.6f} g, "
          f"loop rate {FS} Hz")

    lo_s, hi_s = T0_S, T0_S + 45.0

    # 1. null distribution of the shipped estimator
    null = []
    for _ in range(args.null_trials):
        null.append(retro_z(envelope([a * scale for a in noise3()]), lo_s, hi_s))
    null = sorted(z for z in null if z > -90)
    print(f"\nnull distribution of retro.significance on pure noise "
          f"(n={len(null)})")
    print("   med %.2f  p90 %.2f  p99 %.2f  max %.2f  (sigma units)"
          % (st.median(null), null[int(.90 * len(null))],
             null[int(.99 * len(null))], null[-1]))
    print(f"   retro.Z_MIN = {retro.Z_MIN}  -> "
          f"{sum(1 for z in null if z >= retro.Z_MIN)}/{len(null)} false "
          f"confirmations on pure noise")

    if args.from_envelope:
        real = null_from_record(args.from_envelope)
        if real:
            real.sort()
            print(f"\nsame estimator on the station's REAL recorded envelope "
                  f"(n={len(real)})")
            print("   med %.2f  p90 %.2f  p99 %.2f  max %.2f"
                  % (st.median(real), real[int(.90 * len(real))],
                     real[int(.99 * len(real))], real[-1]))
            over = sum(1 for z in real if z >= retro.Z_MIN)
            print(f"   Z_MIN = {retro.Z_MIN} -> {over}/{len(real)} "
                  f"({100.0 * over / len(real):.2f}%) at random instants")
            print("   This is the number that matters: the synthetic null above")
            print("   assumes stationary white noise, and a real site is neither.")
        else:
            print(f"\n{args.from_envelope}: not enough recorded envelope yet")

    # 2. thresholds
    print("\nthreshold amplitude, peak band-passed PGA")
    print("   wavetrain          blind      retro    gain")
    gains = []
    blinds = []
    for f_hz, dur_s in ((2.0, 20.0), (3.0, 12.0), (5.0, 8.0)):
        b = bisect(blind_triggers, f_hz, dur_s, scale, args.trials)
        r = bisect(lambda e: retro_z(e, lo_s, hi_s) >= retro.Z_MIN,
                   f_hz, dur_s, scale, args.trials)
        gains.append(b / r)
        blinds.append(b)
        print("   %3.0f Hz / %2.0f s     %6.2f mg  %6.2f mg   x%5.2f  %+.2f Mw"
              % (f_hz, dur_s, b * 1000, r * 1000, b / r,
                 math.log10(b / r) / REF_GMPE[0]))
    gain = math.exp(sum(math.log(g) for g in gains) / len(gains))
    print("   geometric mean                        x%5.2f  %+.2f Mw"
          % (gain, math.log10(gain) / REF_GMPE[0]))

    # 3. rate over the real catalog
    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
    else:
        cfg = load_config(args.config)
        lat, lon = cfg["station"]["lat"], cfg["station"]["lon"]
    events = catalog(args.catalog or None, lat, lon, args.years)
    # The blind reference is the station's published floor rather than this
    # simulation's, so the before/after is measured against what AGENTS.md
    # already quotes; the simulated blind threshold is printed above for
    # comparison and is the more optimistic of the two.
    thr_blind = 0.0044 / 1.43
    thr_retro = thr_blind / gain
    print(f"\ncatalog: {len(events)} events M>=2 within 160 km over "
          f"{args.years:.0f} years")
    print(f"published blind floor {thr_blind * 1000:.2f} mg "
          f"(simulated {st.mean(blinds) * 1000:.2f} mg)")

    rows = []
    for label, thr in (("blind trigger", thr_blind),
                       ("retrospective, site at rest", thr_retro)):
        r1 = rate_per_year(events, thr, 1.0, args.years)
        r4 = rate_per_year(events, thr, 4.0, args.years)
        rows.append((label, thr, r1, r4))
        print("   %-28s %6.3f mg  %5.2f - %5.2f /yr  wait %3.0f-%4.0f d  "
              "P(12 d) %4.1f-%4.1f%%"
              % (label, thr * 1000, r1, r4, 365 / r4, 365 / r1,
                 100 * (1 - math.exp(-r1 * 12 / 365)),
                 100 * (1 - math.exp(-r4 * 12 / 365))))

    q = args.quiet_fraction
    (_, _, b1, b4), (_, _, q1, q4) = rows
    c1, c4 = b1 + q * (q1 - b1), b4 + q * (q4 - b4)
    print(f"\nboth detectors, quiet fraction {q:.2f} (the retrospective test only")
    print("reaches its threshold when the site is at rest; the blind trigger")
    print("runs at all times, so this is the combination, not a replacement)")
    print("   %5.2f - %5.2f /yr   wait %3.0f-%4.0f d   P(one in 12 d) "
          "%4.1f-%4.1f%%"
          % (c1, c4, 365 / c4, 365 / c1,
             100 * (1 - math.exp(-c1 * 12 / 365)),
             100 * (1 - math.exp(-c4 * 12 / 365))))
    print("\nranges are site amplification x1 to x4, which is unknown for an")
    print("indoor mount and is the dominant uncertainty in every figure above.")

    a, b, c = REF_GMPE
    print("\nmagnitude needed, 8 km deep, x1 site")
    print("   km        " + "".join(f"{r:>7d}" for r in (10, 30, 50, 100, 160)))
    for label, thr in (("blind", thr_blind), ("retro", thr_retro)):
        cells = []
        for r in (10, 30, 50, 100, 160):
            hypo = math.hypot(r, 8.0)
            cells.append((math.log10(thr) - b * math.log10(hypo) - c) / a)
        print(f"   {label:<9} " + "".join(f"{m:7.1f}" for m in cells))
    print("   add +-%.2f Mw (1 sigma of REF_GMPE / its magnitude slope)"
          % (REF_GMPE_SIGMA / a))


if __name__ == "__main__":
    main()
