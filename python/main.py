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
                 mode: str = "live"):
        self._lock = threading.Lock()
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

    def set_quakes(self, quakes: list[usgs.Quake]) -> None:
        with self._lock:
            self._quakes = quakes
            self._updated = datetime.now(timezone.utc)

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
            return {
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
                "detections": list(self._detections),
                "updated": self._updated.isoformat(),
            }


def synth_event_from_quake(q: usgs.Quake) -> dict:
    """Synthesize a plausible sensor reading for a real cataloged quake, using
    standard attenuation shapes + noise. Used by the replay demo mode."""
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


def detection_loop(cfg: dict, mode: str, state: SharedState,
                   model: CalibrationModel, clf: QuakeNoiseClassifier,
                   dist_model: DistanceModel) -> None:
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

    # Startup calibration check: fetch USGS before the first shake arrives.
    last_poll = 0.0
    quakes: list[usgs.Quake] = []
    try:
        quakes = usgs.fetch_recent(
            st["lat"], st["lon"], us["radius_km"],
            us.get("display_min_magnitude", us["min_magnitude"]),
            lookback_minutes=us.get("lookback_minutes", 120),
        )
        state.set_quakes(quakes)
        last_poll = time.monotonic()
        print(f"[Sismo-LA] startup USGS check: {len(quakes)} recent quakes")
    except Exception as e:
        print(f"[USGS] startup check failed (will retry): {e}")

    for evt in events:
        now = time.monotonic()
        if now - last_poll > us["poll_interval_s"]:
            try:
                quakes = usgs.fetch_recent(
                    st["lat"], st["lon"], us["radius_km"],
                    us.get("display_min_magnitude", us["min_magnitude"]),
                    lookback_minutes=us.get("lookback_minutes", 120),
                )
                state.set_quakes(quakes)
                last_poll = now
            except Exception as e:  # flaky network: keep going
                print(f"[USGS] request error: {e}")

        # Correlation/calibration only trusts confirmed events >= min_magnitude.
        if "replay_quake" in evt:
            # Replay mode: the pairing is exact by construction (the event was
            # synthesized from this cataloged quake), so the live correlation
            # threshold does not apply.
            match = evt["replay_quake"]
        else:
            match_pool = [q for q in quakes if q.magnitude >= us["min_magnitude"]]
            match = find_match(evt["recv_time"], match_pool, corr["match_window_s"])
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
    window_days = float(pub_cfg.get("window_days", 7))
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

    mode = "replay" if args.replay else ("mock" if args.mock else "live")
    state = SharedState(cfg["station"], cfg["usgs"], model, clf, dist_model,
                        mode=mode)
    worker = threading.Thread(
        target=detection_loop,
        args=(cfg, mode, state, model, clf, dist_model),
        daemon=True,
    )
    worker.start()

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
