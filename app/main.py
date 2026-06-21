"""Sismo-LA - Linux application (Dragonwing MPU).

Orchestrates:
  - reading events coming from the MCU (serial port, or mock for development),
  - periodically querying the USGS catalog (LA, >= M3),
  - temporal correlation local <-> USGS,
  - updating the calibration model.

Usage:
    python main.py                 # source = config.yaml (serial by default)
    python main.py --mock          # generates fake shakes, no hardware
    python main.py --config c.yaml
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone

import yaml

import usgs
from calibration import CalibrationModel


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
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

    print(f"[Sismo-LA] station=({st['lat']},{st['lon']}) "
          f"radius={us['radius_km']}km min_mag={us['min_magnitude']}")
    print(f"[Sismo-LA] calibration: {model.status()}")

    if args.mock or cfg["source"]["type"] == "mock":
        events = iter_mock_events()
        print("[Sismo-LA] source = MOCK")
    else:
        s = cfg["source"]
        events = iter_serial_events(s["serial_port"], s["baudrate"])
        print(f"[Sismo-LA] source = serial {s['serial_port']}")

    last_poll = 0.0
    quakes: list[usgs.Quake] = []

    for evt in events:
        now = time.monotonic()
        if now - last_poll > us["poll_interval_s"]:
            try:
                quakes = usgs.fetch_recent(
                    st["lat"], st["lon"], us["radius_km"], us["min_magnitude"]
                )
                last_poll = now
            except Exception as e:  # flaky network: keep going
                print(f"[USGS] request error: {e}")

        match = find_match(evt["recv_time"], quakes, corr["match_window_s"])
        ts = evt["recv_time"].strftime("%H:%M:%S")

        if match:
            model.add_point(
                pga_g=evt["pga_g"],
                distance_km=match.distance_km,
                magnitude=match.magnitude,
                event_id=match.event_id,
            )
            print(f"[{ts}] shake PGA={evt['pga_g']}g  <->  USGS M{match.magnitude} "
                  f"@ {match.distance_km:.0f}km ({match.place}) | {model.status()}")
        else:
            est = model.estimate_magnitude(evt["pga_g"], distance_km=30.0)
            est_txt = f"~M{est:.1f} (estimated @30km)" if est is not None else "unclassified"
            print(f"[{ts}] shake PGA={evt['pga_g']}g  no USGS match "
                  f"-> {est_txt} [noise candidate?]")


if __name__ == "__main__":
    main()
