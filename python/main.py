"""Sismo-LA - web dashboard server (Dragonwing MPU).

Runs the same detection/correlation/calibration loop as ``pipeline.py`` in a
background thread, keeps the resulting state in memory, and exposes:

  - ``GET /api/state``  -> JSON snapshot (station, USGS quakes, device
    detections, calibration status) consumed by the dashboard.
  - ``GET /``           -> the Leaflet dashboard (``dashboard/index.html``).

The dashboard overlays the USGS catalog (colored circles at epicenters) with
the device's own estimates drawn in RED on the same map, so errors against USGS
are visible at a glance. That comparison is the whole story of the project.

Read the red markers carefully: the device measures magnitude and distance, but
a single station cannot measure azimuth. When a match exists the marker borrows
the true bearing purely so it can be drawn as a point; without a match it is
drawn as a ring, which is the honest representation.

Usage:
    python main.py --mock                   # hardware-free development
    python main.py --replay                 # demo: replay recent USGS quakes
    python main.py                          # real sensor source (config.yaml)

This is the entry point Arduino App Lab starts on the MPU: an App is a folder
holding ``app.yaml``, ``python/main.py`` and ``sketch/``, and the runtime builds
the sketch, flashes the MCU, installs these requirements and runs this file.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import os
import shlex
import subprocess
import tempfile

import requests

import usgs
from calibration import CalibrationModel, DistanceModel
from classifier import QuakeNoiseClassifier
import eventlog
import retro
from envelope import EnvelopeStore
from eventlog import EventLog
from pipeline import (
    find_match,
    iter_bridge_events,
    iter_mock_events,
    iter_monitor_events,
    iter_serial_events,
    load_config,
)

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
# Distance assumed for an unmatched shake, only to give an indicative estimate.
ASSUMED_DISTANCE_KM = 30.0
MAX_DETECTIONS = 50
EARTH_R_KM = 6371.0

# --- Liveness thresholds ---------------------------------------------------
# The sketch heartbeats every 10 s and the catalog is polled every 60 s, so
# these are generous: they flag a link that is gone, not one that is late.
# Both exist because on 2026-09-01 the MCU went silent and the station kept
# serving its start-up snapshot for 24 minutes as though nothing had happened.
MCU_SILENT_LIMIT_S = 60.0
USGS_STALE_LIMIT_S = 300.0


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, in degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x))


def destination(lat: float, lon: float, bearing: float, dist_km: float) -> tuple[float, float]:
    """Point at ``dist_km`` from (lat, lon) along ``bearing`` degrees."""
    d = dist_km / EARTH_R_KM
    b = math.radians(bearing)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(p1),
        math.cos(d) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), math.degrees(l2)


class SharedState:
    """Thread-safe snapshot shared between the detection loop and HTTP handlers."""

    def __init__(self, station: dict, usgs_cfg: dict, model: CalibrationModel,
                 clf: QuakeNoiseClassifier, dist_model: DistanceModel,
                 mode: str = "live", store: EnvelopeStore | None = None,
                 retro_log: "retro.RetroLog | None" = None):
        self._lock = threading.Lock()
        self._store = store
        self._retro = retro_log
        self._retro_last: datetime | None = None
        self._retro_scanned = 0
        self._station = station
        self._usgs_cfg = usgs_cfg
        self._model = model
        self._clf = clf
        self._dist_model = dist_model
        self._mode = mode
        self._quakes: list[usgs.Quake] = []
        self._detections: deque[dict] = deque(maxlen=MAX_DETECTIONS)
        self._updated = datetime.now(timezone.utc)
        self._counter = 0
        self._started = datetime.now(timezone.utc)
        self._mcu_last_seen: datetime | None = None
        self._mcu_last_detail = ""
        self._mcu_notifications = 0
        self._usgs_last_ok: datetime | None = None
        self._usgs_last_error = ""
        self._loop_restarts = 0

    def set_quakes(self, quakes: list[usgs.Quake]) -> None:
        with self._lock:
            self._quakes = quakes
            self._usgs_last_ok = datetime.now(timezone.utc)
            self._usgs_last_error = ""
            self._updated = datetime.now(timezone.utc)

    def quakes(self) -> list[usgs.Quake]:
        """Current catalog snapshot, for the detection loop to correlate against.

        The catalog is refreshed by its own thread now, so the loop reads it
        here instead of owning it.
        """
        with self._lock:
            return list(self._quakes)

    def note_usgs_error(self, message: str) -> None:
        with self._lock:
            self._usgs_last_error = message

    def note_mcu_activity(self, kind: str, detail: str = "") -> None:
        """Record that the MCU said something — anything."""
        with self._lock:
            self._mcu_last_seen = datetime.now(timezone.utc)
            self._mcu_notifications += 1
            if detail:
                self._mcu_last_detail = detail
            if kind == "heartbeat":
                # A heartbeat is proof of life, so it counts as the state
                # having been confirmed fresh even when nothing shook.
                self._updated = self._mcu_last_seen

    def note_loop_restart(self) -> None:
        with self._lock:
            self._loop_restarts += 1

    def note_retro_scan(self, scanned: int) -> None:
        with self._lock:
            self._retro_last = datetime.now(timezone.utc)
            self._retro_scanned = scanned

    def _retro_block(self) -> dict:
        """What the retrospective search has found, kept apart from detections.

        A separate block rather than extra fields on ``detections``, because
        every consumer then has to decide explicitly which of the two it is
        showing. A flag on a shared list is the shape that eventually gets
        summed.
        """
        if self._retro is None:
            return {"enabled": False}
        found = self._retro.confirmed()
        return {
            "enabled": True,
            "n_confirmed": len(found),
            "n_scanned": len(self._retro.findings),
            "last_scan": self._retro_last.isoformat() if self._retro_last else None,
            "scanned_last_pass": self._retro_scanned,
            "z_min": retro.Z_MIN,
            "confirmed": [
                {
                    "event_id": f["event_id"],
                    "origin_time": f["origin_time"],
                    "magnitude": f["magnitude"],
                    "place": f["place"],
                    "distance_km": f["distance_km"],
                    "z": f["z"],
                    "window_s": f["window_s"],
                    "peak_g": f["peak_g"],
                    "rms_g": f["rms_g"],
                    "baseline_g": f["baseline_g"],
                    "lag_s": f["lag_s"],
                }
                for f in found[-20:]
            ],
            "envelope": self._store.coverage() if self._store else None,
        }

    def _health(self, now: datetime) -> dict:
        mcu_silent = ((now - self._mcu_last_seen).total_seconds()
                      if self._mcu_last_seen else
                      (now - self._started).total_seconds())
        usgs_age = ((now - self._usgs_last_ok).total_seconds()
                    if self._usgs_last_ok else None)
        # Only a live station has an MCU to lose. In mock and replay the events
        # are generated in-process, so demanding a heartbeat would report a
        # permanent fault and train everyone to ignore the flag.
        mcu_expected = self._mode == "live"
        mcu_ok = (not mcu_expected
                  or (self._mcu_last_seen is not None
                      and mcu_silent <= MCU_SILENT_LIMIT_S))
        usgs_ok = usgs_age is not None and usgs_age <= USGS_STALE_LIMIT_S
        problems = []
        if not mcu_ok:
            problems.append(
                "no MCU heartbeat for %.0f s (sensor link down?)" % mcu_silent
                if self._mcu_last_seen else
                "never heard from the MCU (%.0f s since start)" % mcu_silent
            )
        if not usgs_ok:
            problems.append(
                "USGS catalog %.0f s old" % usgs_age if usgs_age is not None
                else "USGS never reached"
            )
        return {
            "mcu_ok": mcu_ok,
            "mcu_expected": mcu_expected,
            "mcu_last_seen": (self._mcu_last_seen.isoformat()
                              if self._mcu_last_seen else None),
            "mcu_silent_s": round(mcu_silent, 1),
            "mcu_notifications": self._mcu_notifications,
            "mcu_last_detail": self._mcu_last_detail,
            "usgs_ok": usgs_ok,
            "usgs_last_ok": (self._usgs_last_ok.isoformat()
                             if self._usgs_last_ok else None),
            "usgs_age_s": round(usgs_age, 1) if usgs_age is not None else None,
            "usgs_last_error": self._usgs_last_error,
            "loop_restarts": self._loop_restarts,
            "started": self._started.isoformat(),
            # One flag for a page to key off. A stale station must look stale:
            # serving an old snapshot as if it were current is worse than
            # serving nothing, because nobody goes to look.
            "stale": not (mcu_ok and usgs_ok),
            "problems": problems,
        }

    def add_detection(self, evt: dict, match: usgs.Quake | None,
                      p_quake: float | None) -> None:
        with self._lock:
            self._counter += 1
            st_lat, st_lon = self._station["lat"], self._station["lon"]

            # The device's OWN estimate: distance from the coda (duration +
            # dominant frequency), then magnitude from PGA at that distance.
            # This is what the red circle shows — deliberately imperfect.
            est_dist = self._dist_model.estimate_distance(
                evt.get("dur_ms"), evt.get("dom_hz")
            )
            dist_for_mag = est_dist if est_dist is not None else ASSUMED_DISTANCE_KM
            est = self._model.estimate_magnitude(evt["pga_g"], dist_for_mag)

            device_est = None
            if est is not None:
                if match is not None and est_dist is not None:
                    # Single station: bearing is unknown; borrow it from the
                    # matched event so the red circle lands at the estimated
                    # distance along the true direction. Center offset + size
                    # difference vs the USGS circle = the device's error.
                    brg = bearing_deg(st_lat, st_lon, match.lat, match.lon)
                    e_lat, e_lon = destination(st_lat, st_lon, brg, est_dist)
                    device_est = {
                        "kind": "point",
                        "lat": round(e_lat, 4),
                        "lon": round(e_lon, 4),
                        "mag": round(est, 2),
                        "distance_km": round(est_dist, 1),
                    }
                elif est_dist is not None:
                    # No bearing available: the epicenter lies somewhere on a
                    # ring of radius est_dist around the station.
                    device_est = {
                        "kind": "ring",
                        "lat": st_lat,
                        "lon": st_lon,
                        "mag": round(est, 2),
                        "distance_km": round(est_dist, 1),
                    }

            if match is not None:
                match_info = {
                    "event_id": match.event_id,
                    "magnitude": match.magnitude,
                    "place": match.place,
                    "lat": match.lat,
                    "lon": match.lon,
                    "distance_km": round(match.distance_km, 1),
                }
            else:
                match_info = None

            self._detections.appendleft(
                {
                    "id": self._counter,
                    "recv_time": evt["recv_time"].isoformat(),
                    "pga_g": evt["pga_g"],
                    "dur_ms": evt.get("dur_ms"),
                    "dom_hz": evt.get("dom_hz"),
                    "est_mag": round(est, 2) if est is not None else None,
                    "device_est": device_est,
                    "match": match_info,
                    "p_quake": round(p_quake, 3) if p_quake is not None else None,
                }
            )
            self._updated = datetime.now(timezone.utc)

    def snapshot(self) -> dict:
        with self._lock:
            now = datetime.now(timezone.utc)
            return {
                "health": self._health(now),
                "station": self._station,
                "mode": self._mode,
                "config": {
                    "radius_km": self._usgs_cfg["radius_km"],
                    "min_magnitude": self._usgs_cfg["min_magnitude"],
                },
                "calibration": {
                    "ready": self._model.ready,
                    "n_points": len(self._model.points),
                    "min_points": self._model.min_points,
                    "rmse": self._model.rmse,
                    "distance_ready": self._dist_model.ready,
                    "distance_points": len(self._dist_model.points),
                },
                "ai": {
                    "ready": self._clf.ready,
                    "n_quakes": self._clf.counts[0],
                    "n_noise": self._clf.counts[1],
                    "status": self._clf.status(),
                },
                "quakes": [
                    {
                        "event_id": q.event_id,
                        "time": q.time.isoformat(),
                        "magnitude": q.magnitude,
                        "place": q.place,
                        "lat": q.lat,
                        "lon": q.lon,
                        "depth_km": q.depth_km,
                        "distance_km": round(q.distance_km, 1),
                    }
                    for q in self._quakes
                ],
                # Two categories, never one list. `detections` is what the
                # station triggered on by itself; `retro` is what it confirmed
                # at an instant the catalog supplied. See python/retro.py.
                "detections": list(self._detections),
                "retro": self._retro_block(),
                "updated": self._updated.isoformat(),
            }


def synth_event_from_quake(q: usgs.Quake) -> dict:
    """Synthesize a sensor reading for a real cataloged quake. Replay mode only.

    The amplitude below comes from `0.7*M - 1.3*log10 R - 1.9`, which is NOT the
    reference law and is known to be wrong: measured against 12324 PGA values
    recorded by USGS ShakeMap stations during 40 southern-California
    earthquakes, it over-predicts ground motion by 37.9x. The law fitted to
    those records is `REF_GMPE` in pipeline.py; that is the one to use for
    anything physical, and the two must not be reconciled without reading this.

    The divergence is deliberate. Corrected amplitudes would put nearly every
    cataloged quake below this station's measured trigger floor (~0.0044 g), so
    a physically honest replay would show an empty dashboard. Replay is a
    demonstration of the software, not of the instrument, and it is allowed to
    be generous because nothing physical is claimed from it.

    Consequence: replay amplitudes are not physical, and no sensitivity or
    "what can it feel" statement may be derived from a replay run. What replay
    does exercise is the chain — matching, fitting, persistence, inference —
    and even that is circular, since the calibration fits the inverse of the law
    used here. Note also that these events bypass `find_match` entirely (main()
    pairs them with their source quake), so the plausibility veto built on
    REF_GMPE never sees them.
    """
    r = max(q.distance_km, 5.0)
    log_pga = 0.7 * q.magnitude - 1.3 * math.log10(r) - 1.9 + random.gauss(0, 0.15)
    pga = max(10 ** log_pga, 1e-5)
    dur_s = max(1.0, 2.0 + 2.2 * q.magnitude + r / 60.0 + random.gauss(0, 1.0))
    dom = max(0.8, 11.0 - 1.2 * q.magnitude - r / 50.0 + random.gauss(0, 0.6))
    return {
        "t_ms": int(time.monotonic() * 1000),
        "pga_g": round(pga, 5),
        "dur_ms": int(dur_s * 1000),
        "dom_hz": round(dom, 2),
        "recv_time": datetime.now(timezone.utc),
        "replay_quake": q,  # direct match: origin times are hours old
    }


def synth_noise_event() -> dict:
    """A passing truck / slammed door: short, high-frequency, no USGS match."""
    return {
        "t_ms": int(time.monotonic() * 1000),
        "pga_g": round(random.uniform(0.003, 0.06), 5),
        "dur_ms": random.randint(300, 2500),
        "dom_hz": round(random.uniform(12.0, 35.0), 2),
        "recv_time": datetime.now(timezone.utc),
    }


def iter_replay_events(st: dict, us: dict, period_s: float = 12.0):
    """Replay the recent USGS catalog as if the sensor were detecting each
    quake live (accelerated), interleaved with local noise events so the AI
    filter has both classes to learn from. Loops forever."""
    quakes = usgs.fetch_recent(
        st["lat"], st["lon"], us["radius_km"],
        us.get("display_min_magnitude", us["min_magnitude"]),
        lookback_minutes=us.get("lookback_minutes", 1440),
    )
    quakes = sorted(quakes, key=lambda q: q.time)
    if not quakes:
        print("[replay] no recent USGS quakes to replay; noise only")
    print(f"[replay] replaying {len(quakes)} cataloged quakes, "
          f"1 event every ~{period_s:.0f}s")
    while True:
        for q in quakes or [None]:
            if q is not None:
                time.sleep(random.uniform(period_s * 0.6, period_s * 1.2))
                yield synth_event_from_quake(q)
            if random.random() < 0.4:  # sprinkle local noise between quakes
                time.sleep(random.uniform(2, 6))
                yield synth_noise_event()


def snapshot_prior(evt: dict, match, model: CalibrationModel,
                   dist_model: DistanceModel) -> dict:
    """What the models predict for this event, before they learn it.

    Two magnitude figures on purpose. ``magnitude_operational`` follows the
    path the station actually walks in the field: estimate the distance from
    duration and frequency, then invert the amplitude law with that estimate.
    It is the number that matters, and it carries both errors.
    ``magnitude_true_distance`` substitutes the catalog distance instead, which
    isolates the amplitude law from distance-estimation error.
    """
    est_distance = dist_model.estimate_distance(evt.get("dur_ms"), evt.get("dom_hz"))
    prior = {
        "distance_km": est_distance,
        "magnitude_operational": (
            model.estimate_magnitude(evt["pga_g"], est_distance)
            if est_distance else None
        ),
        "magnitude_true_distance": None,
        "amplitude_points": len(model.points),
        "amplitude_ready": model.ready,
        "distance_points": len(dist_model.points),
        "distance_ready": dist_model.ready,
    }
    if match is not None and getattr(match, "distance_km", None):
        prior["magnitude_true_distance"] = model.estimate_magnitude(
            evt["pga_g"], match.distance_km
        )
    return prior


def usgs_poll_loop(cfg: dict, state: SharedState) -> None:
    """Refresh the catalog on a timer, in its own thread.

    This used to live inside the detection loop, which meant the refresh only
    happened when the MCU delivered a shake. On 2026-09-01 the MCU went silent
    and the loop blocked on its queue forever, so the catalog stopped being
    fetched and ``updated`` froze at the start-up value — while the dashboard
    happily served that snapshot for 24 minutes. Polling the catalog has nothing
    to do with the sensor and must not wait on it.
    """
    st = cfg["station"]
    us = cfg["usgs"]
    interval = float(us.get("poll_interval_s", 60))
    while True:
        try:
            quakes = usgs.fetch_recent(
                st["lat"], st["lon"], us["radius_km"],
                us.get("display_min_magnitude", us["min_magnitude"]),
                lookback_minutes=us.get("lookback_minutes", 120),
            )
            state.set_quakes(quakes)
        except Exception as e:  # flaky DNS/network: report, keep going
            print(f"[USGS] request error: {e}", flush=True)
            state.note_usgs_error(str(e))
        time.sleep(interval)


def retro_loop(cfg: dict, state: SharedState, store: EnvelopeStore,
               retro_log: "retro.RetroLog", journal: EventLog) -> None:
    """Re-scan the recent catalog against the stored envelope, on a timer.

    Runs on its own thread and never touches the detection path. It reads the
    envelope files and the catalog, and writes only to ``retro_state.json`` and
    to the journal — so a bug here can lose a confirmation but cannot cost the
    station a trigger or corrupt the calibration.

    Every pass re-scans the whole lookback rather than only what is new. The USGS
    revises magnitudes and locations for hours, sometimes days; the arrival
    window is computed from the distance, so a scan run one minute after the
    origin time is provisional. ``RetroLog`` is keyed by event id, so re-scanning
    updates a finding instead of duplicating it, and only a transition to
    confirmed appends to the journal.
    """
    st = cfg["station"]
    us = cfg["usgs"]
    rcfg = cfg.get("retro") or {}
    interval = float(rcfg.get("interval_s", 900))
    lookback_h = float(rcfg.get("lookback_hours", 72))
    z_min = float(rcfg.get("z_min", retro.Z_MIN))
    feed = bool(rcfg.get("feed_calibration", False))
    print(f"[retro] search on: every {interval:.0f}s over the last "
          f"{lookback_h:.0f}h, z_min={z_min}, "
          f"{'FEEDS' if feed else 'does not feed'} the calibration", flush=True)

    while True:
        try:
            quakes = usgs.fetch_recent(
                st["lat"], st["lon"], us["radius_km"], us["min_magnitude"],
                lookback_minutes=int(lookback_h * 60),
            )
            scanned = 0
            for quake in quakes:
                finding = retro.scan_quake(store, quake, z_min=z_min)
                if finding is None:
                    continue          # no envelope covering that instant
                scanned += 1
                if retro_log.record(finding):
                    journal.append_retro(finding)
                    print(f"[retro] CONFIRMED M{quake.magnitude} @ "
                          f"{quake.distance_km:.0f}km ({quake.place}) "
                          f"z={finding['z']} over {finding['window_s']:.0f}s, "
                          f"{finding['peak_g']*1000:.2f} mg peak vs "
                          f"{finding['baseline_g']*1000:.3f} mg baseline "
                          f"- NOT an autonomous detection", flush=True)
            retro_log.save()
            state.note_retro_scan(scanned)
            print(f"[retro] scanned {scanned} of {len(quakes)} cataloged events "
                  f"against the envelope; {retro_log.status()}", flush=True)
        except Exception as e:
            print(f"[retro] scan failed: {e}", flush=True)
        time.sleep(interval)


def supervise(name: str, target, state: SharedState, *args) -> None:
    """Run ``target`` forever, surviving any exception it raises.

    A bare ``threading.Thread`` dies silently on an uncaught exception, taking
    the pipeline with it while the HTTP server keeps answering. For a station
    meant to run unattended for weeks that is the worst possible failure mode:
    invisible. Restarting with a printed traceback is strictly better, and the
    restart count is published so the dashboard can show it.
    """
    import traceback

    backoff = 5.0
    while True:
        try:
            target(*args)
            print(f"[{name}] returned unexpectedly; restarting", flush=True)
        except Exception:
            print(f"[{name}] CRASHED:\n{traceback.format_exc()}", flush=True)
        state.note_loop_restart()
        time.sleep(backoff)
        backoff = min(backoff * 2, 300.0)


def detection_loop(cfg: dict, mode: str, state: SharedState,
                   model: CalibrationModel, clf: QuakeNoiseClassifier,
                   dist_model: DistanceModel,
                   store: EnvelopeStore | None = None) -> None:
    st = cfg["station"]
    us = cfg["usgs"]
    corr = cfg["correlation"]

    journal = EventLog(cfg["calibration"].get("journal_file", "event_log.jsonl"))
    if journal.enabled:
        print(f"[Sismo-LA] journal: {journal.path} ({journal.count()} records) "
              f"- replay it with `python audit.py`")

    if mode == "replay":
        events = iter_replay_events(st, us)
        print("[Sismo-LA] source = REPLAY (recent USGS catalog)")
    elif mode == "mock" or cfg["source"]["type"] == "mock":
        events = iter_mock_events()
        print("[Sismo-LA] source = MOCK")
    elif cfg["source"]["type"] == "bridge":
        on_envelope = None
        if store is not None and store.enabled:
            on_envelope = store.append_batch
        events = iter_bridge_events(on_mcu_activity=state.note_mcu_activity,
                                    on_envelope=on_envelope)
        print("[Sismo-LA] source = Bridge RPC (MCU notifications)")
    elif cfg["source"]["type"] == "monitor":
        cmd = cfg["source"].get("monitor_command", "arduino-app-cli monitor")
        events = iter_monitor_events(cmd)
        print(f"[Sismo-LA] source = Bridge Monitor ({cmd})")
    else:
        s = cfg["source"]
        events = iter_serial_events(s["serial_port"], s["baudrate"])
        print(f"[Sismo-LA] source = serial {s['serial_port']}")

    # The catalog is fetched by usgs_poll_loop in its own thread; this loop only
    # reads the latest snapshot. Keeping the fetch here is what let a silent MCU
    # freeze the whole station on 2026-09-01.
    for evt in events:
        # Correlation/calibration only trusts confirmed events >= min_magnitude.
        if "replay_quake" in evt:
            # Replay mode: the pairing is exact by construction (the event was
            # synthesized from this cataloged quake), so the live correlation
            # threshold does not apply.
            match = evt["replay_quake"]
        else:
            match_pool = [q for q in state.quakes()
                          if q.magnitude >= us["min_magnitude"]]
            match = find_match(evt["recv_time"], match_pool,
                               corr["match_window_s"], pga_g=evt["pga_g"])
        p_quake = clf.predict_proba(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"))

        # Snapshot the models BEFORE they learn this event. Once the point is
        # folded in, any estimate is contaminated by the answer, and the
        # residual stops being an out-of-sample error. See eventlog.py.
        prior = snapshot_prior(evt, match, model, dist_model)
        journal.append(evt, match, p_quake, prior)

        if match:
            model.add_point(
                pga_g=evt["pga_g"],
                distance_km=match.distance_km,
                magnitude=match.magnitude,
                event_id=match.event_id,
            )
            dist_model.add_point(
                dur_ms=evt.get("dur_ms"),
                dom_hz=evt.get("dom_hz"),
                distance_km=match.distance_km,
                event_id=match.event_id,
            )
            clf.add_sample(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"), label=1)
        else:
            clf.add_sample(evt["pga_g"], evt.get("dur_ms"), evt.get("dom_hz"), label=0)
        state.add_detection(evt, match, p_quake)
        ts = evt["recv_time"].strftime("%H:%M:%S")
        ai_txt = f"AI p(quake)={p_quake:.2f}" if p_quake is not None else "AI warming up"
        shake = (f"PGA={evt['pga_g']:.4f}g dur={evt.get('dur_ms', 0)}ms "
                 f"f={evt.get('dom_hz', 0):.1f}Hz")
        if match:
            print(f"[{ts}] shake {shake} <-> USGS M{match.magnitude} "
                  f"@ {match.distance_km:.0f}km ({match.place}) | {ai_txt} | {model.status()}")
        else:
            print(f"[{ts}] shake {shake} no USGS match | {ai_txt} | {model.status()}")


def strip_location(snapshot: dict) -> dict:
    """Drop the station's coordinates from a snapshot before publishing.

    The public page does not need them: it draws the catalog, and the device's
    contribution is a magnitude and a distance attached to the matched event.
    Only the local dashboard, on the operator's own network, plots the station.

    This is not anonymity. The distances to several known epicenters still
    trilaterate the station, roughly. It only avoids publishing a home address
    outright.
    """
    out = dict(snapshot)
    out["station"] = {"label": snapshot.get("station", {}).get("label", "Los Angeles")}
    out["detections"] = []
    for d in snapshot.get("detections", []):
        d = dict(d)
        est = d.get("device_est")
        if est is not None:
            # "kind" (point vs ring) only described how to draw it on a map
            # centred on the station, so it goes with the coordinates.
            drop = ("lat", "lon", "kind")
            d["device_est"] = {k: v for k, v in est.items() if k not in drop}
        out["detections"].append(d)
    return out


def publisher_loop(pub_cfg: dict, state: SharedState,
                   journal_path: str = "") -> None:
    """Periodically publish the station snapshot to a remote site, so the
    device is fully autonomous and a public web page can display its data.

    Methods:
      - "post":    HTTP POST the JSON to ``url`` (with optional bearer token).
      - "file":    write JSON to ``path`` (atomic), e.g. a synced folder.
      - "command": write JSON to a temp file, then run ``command`` with the
                   file path appended — e.g. an scp/rsync/curl upload to
                   static hosting like benoit-prieur.fr.
    """
    method = pub_cfg.get("method", "post")
    interval = float(pub_cfg.get("interval_s", 60))
    with_location = bool(pub_cfg.get("include_location", False))
    window_days = float(pub_cfg.get("window_days", 30))
    while True:
        time.sleep(interval)
        snapshot = state.snapshot()
        if not with_location:
            snapshot = strip_location(snapshot)
        # The in-memory detection list is short and dies with the process. The
        # journal is the thing that accumulates, so the published record is
        # rebuilt from it every time rather than from what is still in RAM.
        if journal_path:
            try:
                snapshot["history"] = eventlog.matched_pairs(journal_path)
                snapshot["recent"] = eventlog.recent_events(
                    journal_path, days=window_days
                )
                # A third list, and it stays a third list all the way to the
                # public page: cataloged earthquakes found in the stored
                # envelope at their computed arrival time. Real ground motion,
                # not an autonomous detection. `history` and `recent` already
                # filter it out at source (eventlog.kind_of), so nothing here
                # can leak into the autonomous record by omission.
                snapshot["confirmed"] = eventlog.confirmed_events(
                    journal_path, days=window_days
                )
                snapshot["window_days"] = window_days
            except OSError as e:
                print(f"[publish] could not read journal: {e}")
        payload = json.dumps(snapshot).encode("utf-8")
        try:
            if method == "post":
                headers = {"Content-Type": "application/json"}
                if pub_cfg.get("token"):
                    headers["Authorization"] = f"Bearer {pub_cfg['token']}"
                requests.post(pub_cfg["url"], data=payload, headers=headers,
                              timeout=15).raise_for_status()
            elif method == "file":
                path = pub_cfg["path"]
                tmp = path + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(payload)
                os.replace(tmp, path)
            elif method == "command":
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".json", delete=False,
                    prefix="station_"
                ) as f:
                    f.write(payload)
                    tmp_path = f.name
                try:
                    argv = shlex.split(pub_cfg["command"])
                    if any("{file}" in a for a in argv):
                        argv = [a.replace("{file}", tmp_path) for a in argv]
                    else:
                        argv.append(tmp_path)
                    subprocess.run(argv, check=True, timeout=60,
                                   capture_output=True)
                finally:
                    os.unlink(tmp_path)
        except Exception as e:  # publishing must never kill the pipeline
            print(f"[publish] {method} failed: {e}")


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, state: SharedState, **kwargs):
        self._state = state
        super().__init__(*args, **kwargs)

    def log_message(self, *args):  # silence default request logging
        pass

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            body = json.dumps(self._state.snapshot()).encode("utf-8")
            self._send(200, body, "application/json")
            return

        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (DASHBOARD_DIR / rel).resolve()
        if DASHBOARD_DIR not in target.parents or not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript",
            ".css": "text/css",
        }.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sismo-LA dashboard server")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mock", action="store_true", help="simulated source")
    parser.add_argument("--replay", action="store_true",
                        help="demo: replay recent USGS quakes as detections")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    cfg = load_config(args.config)
    calcfg = cfg["calibration"]
    model = CalibrationModel(
        state_file=calcfg["state_file"], min_points=calcfg["min_points"]
    )
    model.load()
    clf = QuakeNoiseClassifier(
        state_file=calcfg.get("classifier_state_file", "classifier_state.json")
    )
    clf.load()
    dist_model = DistanceModel(
        state_file=calcfg.get("distance_state_file", "distance_state.json")
    )
    dist_model.load()

    # The continuous envelope and the retrospective search over it. Both are
    # live-only: in mock and replay the "sensor" is a random number generator,
    # so there is no ground motion to record and confirming a cataloged
    # earthquake against synthetic noise would be theatre.
    mode = "replay" if args.replay else ("mock" if args.mock else "live")
    envcfg = cfg.get("envelope") or {}
    store = None
    if mode == "live" and envcfg.get("enabled", True):
        store = EnvelopeStore(envcfg.get("directory", "envelope"),
                              retention_days=envcfg.get("retention_days", 14))
        store.purge()
        print(f"[Sismo-LA] envelope -> {store.directory} "
              f"({store.coverage()['days']} day files, keeping "
              f"{store.retention_days})")
    retro_log = None
    if store is not None and (cfg.get("retro") or {}).get("enabled", True):
        retro_log = retro.RetroLog(
            (cfg.get("retro") or {}).get("state_file", "retro_state.json"))
        retro_log.load()
        print(f"[Sismo-LA] {retro_log.status()}")

    state = SharedState(cfg["station"], cfg["usgs"], model, clf, dist_model,
                        mode=mode, store=store, retro_log=retro_log)

    # Startup catalog check, so the station knows its seismic context before the
    # first shake arrives and the dashboard is not empty on first load.
    st, us = cfg["station"], cfg["usgs"]
    try:
        startup = usgs.fetch_recent(
            st["lat"], st["lon"], us["radius_km"],
            us.get("display_min_magnitude", us["min_magnitude"]),
            lookback_minutes=us.get("lookback_minutes", 120),
        )
        state.set_quakes(startup)
        print(f"[Sismo-LA] startup USGS check: {len(startup)} recent quakes")
    except Exception as e:
        print(f"[USGS] startup check failed (will retry): {e}")
        state.note_usgs_error(str(e))

    # Both loops are supervised: an uncaught exception must be loud and
    # recoverable, not a silent thread death behind a live HTTP server.
    threading.Thread(
        target=supervise,
        args=("detection", detection_loop, state,
              cfg, mode, state, model, clf, dist_model, store),
        daemon=True,
    ).start()
    threading.Thread(
        target=supervise, args=("usgs", usgs_poll_loop, state, cfg, state),
        daemon=True,
    ).start()
    if retro_log is not None:
        journal = EventLog(calcfg.get("journal_file", "event_log.jsonl"))
        threading.Thread(
            target=supervise,
            args=("retro", retro_loop, state, cfg, state, store, retro_log,
                  journal),
            daemon=True,
        ).start()

    pub_cfg = cfg.get("publish") or {}
    if pub_cfg.get("enabled"):
        pub = threading.Thread(
            target=publisher_loop,
            args=(pub_cfg, state, calcfg.get("journal_file", "event_log.jsonl")),
            daemon=True,
        )
        pub.start()
        print(f"[Sismo-LA] publisher on ({pub_cfg.get('method', 'post')}, "
              f"every {pub_cfg.get('interval_s', 60)}s)")

    handler = partial(DashboardHandler, state=state)
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"[Sismo-LA] dashboard on http://{args.host}:{args.port}  "
          f"(station {cfg['station']['lat']},{cfg['station']['lon']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Sismo-LA] shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
