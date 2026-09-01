"""Sismo-LA - Linux application (Dragonwing MPU).

Orchestrates:
  - reading events coming from the MCU (serial port, or mock for development),
  - periodically querying the USGS catalog (LA, >= M3),
  - temporal correlation local <-> USGS,
  - updating the calibration model.

Usage:
    python pipeline.py                 # source = config.yaml (serial by default)
    python pipeline.py --mock          # generates fake shakes, no hardware
    python pipeline.py --config c.yaml

Headless variant. ``main.py`` is the App Lab entry point and reuses the
detection/correlation helpers defined here.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

import usgs
from calibration import CalibrationModel
from classifier import QuakeNoiseClassifier


def resolve_config_path(path: str) -> Path:
    """Locate the config file regardless of where the process was launched.

    App Lab runs the app from the repo root while the config sits next to this
    module, and ``config.yaml`` is gitignored, so a fresh clone has only the
    example. Falling back to it keeps "clone and start" working.
    """
    here = Path(__file__).resolve().parent
    candidates = [Path(path), here / path]
    if Path(path).name == "config.yaml":
        candidates.append(here / "config.example.yaml")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"no configuration file found (tried: {tried})")


def load_config(path: str) -> dict:
    resolved = resolve_config_path(path)
    print(f"[config] {resolved}", flush=True)
    with open(resolved, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def iter_serial_events(port: str, baudrate: int):
    """Generator of events from the MCU over the serial port (JSON lines)."""
    import serial  # lazy import: not needed in mock mode

    ser = serial.Serial(port, baudrate, timeout=1)
    _ = ser.readline()  # discard a possibly partial first line
    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        evt["recv_time"] = datetime.now(timezone.utc)
        yield evt


def iter_bridge_events(on_mcu_activity=None, on_envelope=None):
    """Generator of events pushed by the MCU over the Bridge RPC link.

    This is the transport to use on the board. App Lab runs this half inside a
    container, where the MCU's Monitor stream is out of reach but the router
    socket is bind-mounted, so ``iter_monitor_events`` cannot work there.

    The sketch sends one ``seismic_event`` notification per detection. The
    Bridge dispatches it on its own daemon thread, so the handler only hands
    the event to this generator through a queue.

    ``on_mcu_activity(kind, detail)`` is called for every notification of any
    kind, heartbeats included. Without it the only evidence that the MCU is
    alive is a log line, and a station whose MCU has gone quiet then looks
    exactly like a station in a quiet neighbourhood — which is precisely the
    failure that went unnoticed on 2026-09-01.

    ``on_envelope(payload, n, bucket_ms, received)`` receives the continuous
    envelope batches the sketch sends between events. They are not events and
    never enter the queue: nothing crossed a trigger, and treating them as
    detections would flood the journal and the calibration with the noise floor.
    """
    import queue

    from arduino.app_utils import Bridge  # provided by the App Lab runtime

    pending: "queue.Queue[dict]" = queue.Queue()

    def note(kind, detail=""):
        if on_mcu_activity is not None:
            try:
                on_mcu_activity(kind, detail)
            except Exception as e:  # never let bookkeeping kill the link
                print(f"[bridge] activity hook failed: {e}", flush=True)

    def on_seismic_event(t_ms, pga_g, dur_ms, dom_hz, pga_wb_g=None):
        # ``pga_g`` is the 0.7-12 Hz band-passed peak since the 2026-09-01
        # firmware; ``pga_wb_g`` is the old wideband definition, kept so the two
        # eras can be related after the fact. The default keeps this handler
        # working against a firmware that predates the change, which matters
        # because Python is deployed by pushing a file and the MCU by a flash:
        # the two are never simultaneous.
        pending.put({
            "t_ms": int(t_ms),
            "pga_g": float(pga_g),
            "dur_ms": int(dur_ms),
            "dom_hz": float(dom_hz),
            "pga_wb_g": float(pga_wb_g) if pga_wb_g is not None else None,
            "recv_time": datetime.now(timezone.utc),
        })
        note("event")

    def on_mcu_status(message):
        print(f"[bridge] mcu status: {message}", flush=True)
        note("status", str(message))

    def on_mcu_heartbeat(t_ms, sta_lta, dyn_g, lta_g=None, dyn_wb_g=None,
                         lta_wb_g=None, fs_hz=None):
        # The noise floor is the one number that tells you the detector is
        # actually looking at a sensor rather than at a dead I2C bus.
        #
        # The extra fields exist for one measurement. ``lta_g`` is the noise
        # floor inside 0.7-12 Hz and ``lta_wb_g`` the wideband floor, averaged
        # over the SAME ten seconds, so their ratio is the fraction of the floor
        # that lies outside the seismic band — the quantity that decides whether
        # band-passing buys any sensitivity at all. Measuring it this way avoids
        # comparing a daytime window against a night one, which is how the
        # previous attempt at the same question ended up inconclusive.
        detail = (f"sta/lta={float(sta_lta):.2f} dyn={float(dyn_g):.5f}g")
        if lta_g is not None:
            detail += f" lta={float(lta_g):.5f}g"
        if dyn_wb_g is not None:
            detail += f" wb={float(dyn_wb_g):.5f}g"
        if lta_wb_g is not None:
            detail += f" wb_lta={float(lta_wb_g):.5f}g"
        if fs_hz is not None:
            detail += f" fs={float(fs_hz):.1f}Hz"
        print(f"[bridge] mcu alive t={int(t_ms)}ms {detail}", flush=True)
        note("heartbeat", detail)

    def on_mcu_envelope(t_end_ms, n, bucket_ms, payload):
        # The MCU's own clock is NOT used to date these. It runs 1099 ppm slow
        # against the board's NTP-synced clock — 10 s of error in three hours,
        # measured — so an absolute time built from `t_end_ms` would drift
        # silently through the width of the arrival window the search uses. The
        # batch is anchored here, on arrival, and `bucket_ms` only spaces the
        # samples inside it, over 10 s, where the same drift is 11 ms.
        received = datetime.now(timezone.utc)
        note("envelope")
        if on_envelope is None:
            return
        try:
            on_envelope(str(payload), int(n), int(bucket_ms), received)
        except Exception as e:
            print(f"[bridge] envelope handler failed: {e}", flush=True)

    Bridge.provide("seismic_event", on_seismic_event)
    Bridge.provide("mcu_status", on_mcu_status)
    Bridge.provide("mcu_heartbeat", on_mcu_heartbeat)
    Bridge.provide("mcu_envelope", on_mcu_envelope)
    print("[bridge] waiting for seismic_event notifications from the MCU")
    while True:
        yield pending.get()


def iter_monitor_events(command: str):
    """Generator of events from the MCU via the Bridge Monitor stream.

    On the UNO Q the MCU's Monitor is exposed by the arduino-router, not by a
    tty. ``command`` is whatever attaches to it and prints JSON lines:
      - on the board:   arduino-app-cli monitor
      - from a dev Mac: adb shell arduino-app-cli monitor
    Heartbeats ({"status": "alive", ...}) prove the link but are not shakes,
    so anything without a ``pga_g`` field is skipped.
    """
    import shlex
    import subprocess

    while True:
        proc = subprocess.Popen(
            shlex.split(command), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True,
        )
        print(f"[monitor] attached via: {command}")
        for line in proc.stdout:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "pga_g" not in evt:
                continue  # heartbeat / status line
            evt["recv_time"] = datetime.now(timezone.utc)
            yield evt
        proc.wait()
        print("[monitor] stream ended, re-attaching in 3s...")
        time.sleep(3)


def iter_mock_events(min_seconds=8, max_seconds=20):
    """Generate fake shakes to test the chain without the UNO Q."""
    while True:
        time.sleep(random.uniform(min_seconds, max_seconds))
        pga = round(random.uniform(0.002, 0.08), 5)
        yield {
            "t_ms": int(time.monotonic() * 1000),
            "pga_g": pga,
            "dur_ms": random.randint(800, 6000),
            "dom_hz": round(random.uniform(1.0, 8.0), 2),
            "recv_time": datetime.now(timezone.utc),
        }


# --- Correlation gates -----------------------------------------------------
#
# A match feeds the calibration as ground truth, so a wrong one is worse than
# no match at all. Two things can put a local shake next to a cataloged
# earthquake: a genuine detection, or an unrelated door slam landing by chance
# inside the acceptance window. Measured on this station, the second is by far
# the more likely of the two: the trigger fires 3 to 23 times an hour depending
# on where the board sits, while the measured 0.00308 g floor convolved with the
# real catalog predicts 2 to 10 genuine detections a *year*. Both gates below
# exist to suppress that mismatch.

# Crustal body-wave speeds around Los Angeles, km/s. The detector triggers on
# whichever part of the wavetrain first crosses STA/LTA — the P arrival for a
# close event, the S arrival or the start of the coda for a distant one — so the
# admissible delay has to span both. The same bounds define the window the
# retrospective search looks in (retro.search_window).
#
# Reference: the Hadley-Kanamori 1D model as the Southern California Seismic
# Network uses it, tabulated in Hutton, Woessner & Hauksson, "Earthquake
# Monitoring in Southern California for Seventy-Seven Years (1932-2008)", BSSA
# 100(2), 423-446, 2010, Table 5 — Vp = 5.5 / 6.3 / 6.7 / 7.8 km/s at 0 / 5.5 /
# 16 / 32 km depth, with Vp/Vs = 1.73, so Vs runs 3.2-4.5 km/s. That is
# deliberately the reference to use here: it is the velocity model the network
# that produces our ground-truth catalog locates its own events with.
#
# Both constants sit OUTSIDE that range on purpose, because the point is a
# bracket that cannot be wrong rather than a best estimate:
P_SPEED_KM_S = 7.0    # fast end; between the 6.7 crustal layer and Pn at 7.8
S_SPEED_KM_S = 2.5    # slow end; below any crustal Vs, to cover basin surface
                      # waves and the onset of the coda
# On the fast side 7.0 is not strictly the fastest path available: Pn at
# 7.8 km/s, and the 8.3 km/s refractor Hadley & Kanamori (1977) found at 40 km
# under the Transverse Ranges — which is where this station sits — would both
# arrive earlier. The difference is small against the margin below: at 160 km it
# is 3.6 s between 7.0 and 8.3 km/s, so the earliest admissible arrival is still
# ahead of any real one.
#
# Absorbs the STA's 0.5 s lag before the ratio crosses, the Bridge/RPC hop to
# the Python half, and the board's NTP clock error.
TIMING_MARGIN_S = 15.0

# Ground-motion reference, fitted by least squares to 12324 PGA values actually
# recorded by USGS ShakeMap stations during 40 southern-California earthquakes
# (M3.03-5.51, 3-200 km, 1006 distinct stations):
#     log10(PGA_g) = 0.867*M - 1.740*log10(R_hypo_km) - 3.305
# with 0.390 log10 units of scatter (R^2=0.80). This is used ONLY as a veto on
# absurd pairings, never to estimate anything: the amplitude law the station
# reports is still the one it learns for itself.
#
# Two caveats that matter for how far to trust it. The smallest earthquake in
# the data is M3.03, so every value below that is extrapolation, and the
# magnitude slope is itself unsettled — it moves from 0.87 to 1.00 when the fit
# is restricted to M<4.5, which is the range this station cares about. And most
# of the scatter is station-to-station rather than event-to-event (0.347 vs
# 0.198 log10), i.e. site response dominates, which is precisely the term an
# unknown indoor mount makes unknowable. Hence the generous allowances below.
#
# This is not the law `main.py:synth_event_from_quake` uses to generate replay
# amplitudes. That one over-predicts by 37.9x and is kept on purpose, because a
# corrected replay would trigger on almost nothing; see its docstring before
# changing either.
REF_GMPE = (0.8668, -1.7400, -3.3053)
REF_GMPE_SIGMA = 0.3903
# Both allowances are deliberately generous. Being wrong in this direction
# discards the genuine matches the whole project is waiting for, so the veto is
# tuned to reject only the physically absurd: together they permit an observed
# amplitude ~180x above the reference median before a pairing is refused.
SITE_AMPLIFICATION_ALLOWANCE = 4.0   # unknown building, floor and mount
PLAUSIBILITY_SIGMA = 4.0             # path-to-path luck


def travel_time_window(distance_km: float, depth_km: float = 0.0,
                       margin_s: float = TIMING_MARGIN_S) -> tuple[float, float]:
    """Delays after an origin time at which shaking from it can plausibly land.

    Uses the hypocentral distance: LA earthquakes are typically 5-15 km deep,
    which dominates the path length for a nearby epicenter.
    """
    hypo = math.hypot(distance_km, depth_km or 0.0)
    return (max(0.0, hypo / P_SPEED_KM_S - margin_s),
            hypo / S_SPEED_KM_S + margin_s)


def amplitude_is_plausible(pga_g: float, magnitude: float,
                           distance_km: float, depth_km: float = 0.0) -> bool:
    """Could this earthquake have produced the amplitude we recorded?

    One-sided on purpose. An amplitude far *below* the reference is not
    suspicious — weak coupling and unfavourable paths are normal, and refusing
    those would throw away real matches. Only an amplitude far *above* what the
    event can deliver is evidence that the two are unrelated: a 0.05 g shake
    cannot be an M2.2 that happened 150 km away.
    """
    if pga_g is None or pga_g <= 0 or magnitude is None:
        return True
    a, b, c = REF_GMPE
    hypo = max(math.hypot(distance_km or 0.0, depth_km or 0.0), 3.0)
    predicted = a * magnitude + b * math.log10(hypo) + c
    margin = (PLAUSIBILITY_SIGMA * REF_GMPE_SIGMA
              + math.log10(SITE_AMPLIFICATION_ALLOWANCE))
    return math.log10(pga_g) <= predicted + margin


def find_match(evt_time, quakes, window_s, pga_g=None):
    """Find the cataloged earthquake that could have produced a local shake.

    Two conditions, both physical. The delay must be consistent with waves
    travelling from the hypocenter — accepting anything up to ``window_s``, as
    this did, admits a detection 170 s after an M2 whose S wave passed the
    station at 9 s. And, when ``pga_g`` is given, the recorded amplitude must be
    one that event could actually deliver at that distance.

    ``window_s`` is kept as an outer bound on the search; the travel-time gate
    is tighter than it at every distance inside the station's radius.
    """
    best = None
    for q in quakes:
        dt = (evt_time - q.time).total_seconds()
        if dt < 0 or dt > window_s:
            continue
        dist = getattr(q, "distance_km", 0.0) or 0.0
        depth = getattr(q, "depth_km", 0.0) or 0.0
        lo, hi = travel_time_window(dist, depth)
        if not lo <= dt <= hi:
            continue
        if pga_g is not None and not amplitude_is_plausible(
            pga_g, getattr(q, "magnitude", None), dist, depth
        ):
            continue
        if best is None or dt < best[1]:
            best = (q, dt)
    return best[0] if best else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Sismo-LA (Linux application)")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mock", action="store_true", help="simulated source")
    args = parser.parse_args()

    cfg = load_config(args.config)
    st = cfg["station"]
    us = cfg["usgs"]
    corr = cfg["correlation"]
    calcfg = cfg["calibration"]

    model = CalibrationModel(
        state_file=calcfg["state_file"], min_points=calcfg["min_points"]
    )
    model.load()
    clf = QuakeNoiseClassifier(
        state_file=calcfg.get("classifier_state_file", "classifier_state.json")
    )
    clf.load()

    print(f"[Sismo-LA] station=({st['lat']},{st['lon']}) "
          f"radius={us['radius_km']}km min_mag={us['min_magnitude']}")
    print(f"[Sismo-LA] calibration: {model.status()}")
    print(f"[Sismo-LA] {clf.status()}")

    # --- Startup calibration check: query USGS right away so the device knows
    # the current local seismic context before the first shake arrives.
    quakes: list[usgs.Quake] = []
    last_poll = 0.0
    try:
        quakes = usgs.fetch_recent(
            st["lat"], st["lon"], us["radius_km"],
            us.get("display_min_magnitude", us["min_magnitude"]),
            lookback_minutes=us.get("lookback_minutes", 120),
        )
        last_poll = time.monotonic()
        n_cal = sum(1 for q in quakes if q.magnitude >= us["min_magnitude"])
        print(f"[Sismo-LA] startup USGS check: {len(quakes)} recent quakes "
              f"({n_cal} usable for calibration >= M{us['min_magnitude']})")
        for q in quakes[:3]:
            print(f"           M{q.magnitude:.1f} @ {q.distance_km:.0f}km  {q.place}")
    except Exception as e:
        print(f"[USGS] startup check failed (will retry): {e}")

    if args.mock or cfg["source"]["type"] == "mock":
        events = iter_mock_events()
        print("[Sismo-LA] source = MOCK")
    elif cfg["source"]["type"] == "bridge":
        events = iter_bridge_events()
        print("[Sismo-LA] source = Bridge RPC (MCU notifications)")
    elif cfg["source"]["type"] == "monitor":
        cmd = cfg["source"].get("monitor_command", "arduino-app-cli monitor")
        events = iter_monitor_events(cmd)
        print(f"[Sismo-LA] source = Bridge Monitor ({cmd})")
    else:
        s = cfg["source"]
        events = iter_serial_events(s["serial_port"], s["baudrate"])
        print(f"[Sismo-LA] source = serial {s['serial_port']}")

    for evt in events:
        now = time.monotonic()
        if now - last_poll > us["poll_interval_s"]:
            try:
                quakes = usgs.fetch_recent(
                    st["lat"], st["lon"], us["radius_km"],
                    us.get("display_min_magnitude", us["min_magnitude"]),
                    lookback_minutes=us.get("lookback_minutes", 120),
                )
                last_poll = now
            except Exception as e:  # flaky network: keep going
                print(f"[USGS] request error: {e}")

        # Correlation/calibration only trusts confirmed events >= min_magnitude.
        match_pool = [q for q in quakes if q.magnitude >= us["min_magnitude"]]
        match = find_match(evt["recv_time"], match_pool,
                           corr["match_window_s"], pga_g=evt["pga_g"])
        ts = evt["recv_time"].strftime("%H:%M:%S")

        # AI filter: predict before learning from this event.
        p_quake = clf.predict_proba(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"))
        ai_txt = f"AI p(quake)={p_quake:.2f}" if p_quake is not None else "AI warming up"

        if match:
            model.add_point(
                pga_g=evt["pga_g"],
                distance_km=match.distance_km,
                magnitude=match.magnitude,
                event_id=match.event_id,
            )
            clf.add_sample(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"), label=1)
            print(f"[{ts}] shake PGA={evt['pga_g']:.4f}g dur={evt.get('dur_ms', 0)}ms "
                  f"f={evt.get('dom_hz', 0):.1f}Hz  <->  USGS M{match.magnitude} "
                  f"@ {match.distance_km:.0f}km ({match.place}) | {ai_txt} "
                  f"| {model.status()}")
        else:
            clf.add_sample(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"), label=0)
            est = model.estimate_magnitude(evt["pga_g"], distance_km=30.0)
            est_txt = f"~M{est:.1f} (estimated @30km)" if est is not None else "unclassified"
            verdict = "noise" if (p_quake is not None and p_quake < 0.5) else "unconfirmed"
            print(f"[{ts}] shake PGA={evt['pga_g']:.4f}g dur={evt.get('dur_ms', 0)}ms "
                  f"f={evt.get('dom_hz', 0):.1f}Hz  no USGS match "
                  f"-> {est_txt} | {ai_txt} [{verdict}]")


if __name__ == "__main__":
    main()
