"""Sismo-LA - application Linux (MPU Dragonwing).

Orchestre :
  - la lecture des evenements venant du MCU (port serie, ou mock pour le dev),
  - l'interrogation periodique du catalogue USGS (LA, >= M3),
  - la correlation temporelle local <-> USGS,
  - la mise a jour du modele d'etalonnage.

Usage :
    python main.py                 # source = config.yaml (serial par defaut)
    python main.py --mock          # genere de fausses secousses, sans materiel
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
    """Generateur d'evenements depuis le MCU via port serie (lignes JSON)."""
    import serial  # import tardif : inutile en mode mock

    ser = serial.Serial(port, baudrate, timeout=1)
    buf = ser.readline()  # purge premiere ligne potentiellement partielle
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
    """Genere de fausses secousses pour tester la chaine sans UNO Q."""
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
    """Cherche un seisme USGS dont l'heure d'origine precede la reception
    locale dans la fenetre autorisee."""
    best = None
    for q in quakes:
        dt = (evt_time - q.time).total_seconds()
        if 0 <= dt <= window_s:
            if best is None or dt < best[1]:
                best = (q, dt)
    return best[0] if best else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Sismo-LA (application Linux)")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--mock", action="store_true", help="source simulee")
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
          f"rayon={us['radius_km']}km min_mag={us['min_magnitude']}")
    print(f"[Sismo-LA] etalonnage : {model.status()}")

    if args.mock or cfg["source"]["type"] == "mock":
        events = iter_mock_events()
        print("[Sismo-LA] source = MOCK")
    else:
        s = cfg["source"]
        events = iter_serial_events(s["serial_port"], s["baudrate"])
        print(f"[Sismo-LA] source = serie {s['serial_port']}")

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
            except Exception as e:  # reseau capricieux : on continue
                print(f"[USGS] erreur de requete : {e}")

        match = find_match(evt["recv_time"], quakes, corr["match_window_s"])
        ts = evt["recv_time"].strftime("%H:%M:%S")

        if match:
            model.add_point(
                pga_g=evt["pga_g"],
                distance_km=match.distance_km,
                magnitude=match.magnitude,
                event_id=match.event_id,
            )
            print(f"[{ts}] secousse PGA={evt['pga_g']}g  <->  USGS M{match.magnitude} "
                  f"@ {match.distance_km:.0f}km ({match.place}) | {model.status()}")
        else:
            est = model.estimate_magnitude(evt["pga_g"], distance_km=30.0)
            est_txt = f"~M{est:.1f} (estime @30km)" if est is not None else "non classe"
            print(f"[{ts}] secousse PGA={evt['pga_g']}g  sans correspondance USGS "
                  f"-> {est_txt} [candidat bruit ?]")


if __name__ == "__main__":
    main()
