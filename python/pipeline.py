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


def iter_bridge_events():
    """Generator of events pushed by the MCU over the Bridge RPC link.

    This is the transport to use on the board. App Lab runs this half inside a
    container, where the MCU's Monitor stream is out of reach but the router
    socket is bind-mounted, so ``iter_monitor_events`` cannot work there.

    The sketch sends one ``seismic_event`` notification per detection. The
    Bridge dispatches it on its own daemon thread, so the handler only hands
    the event to this generator through a queue.
    """
    import queue

    from arduino.app_utils import Bridge  # provided by the App Lab runtime

    pending: "queue.Queue[dict]" = queue.Queue()

    def on_seismic_event(t_ms, pga_g, dur_ms, dom_hz):
        pending.put({
            "t_ms": int(t_ms),
            "pga_g": float(pga_g),
            "dur_ms": int(dur_ms),
            "dom_hz": float(dom_hz),
            "recv_time": datetime.now(timezone.utc),
        })

    def on_mcu_status(message):
        print(f"[bridge] mcu status: {message}", flush=True)

    def on_mcu_heartbeat(t_ms, sta_lta, dyn_g):
        # The noise floor is the one number that tells you the detector is
        # actually looking at a sensor rather than at a dead I2C bus.
        print(f"[bridge] mcu alive t={int(t_ms)}ms sta/lta={float(sta_lta):.2f} "
              f"dyn={float(dyn_g):.5f}g", flush=True)

    Bridge.provide("seismic_event", on_seismic_event)
    Bridge.provide("mcu_status", on_mcu_status)
    Bridge.provide("mcu_heartbeat", on_mcu_heartbeat)
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


def find_match(evt_time, quakes, window_s):
    """Find a USGS earthquake whose origin time precedes the local reception
    within the allowed window."""
    best = None
    for q in quakes:
        dt = (evt_time - q.time).total_seconds()
        if 0 <= dt <= window_s:
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
        match = find_match(evt["recv_time"], match_pool, corr["match_window_s"])
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
