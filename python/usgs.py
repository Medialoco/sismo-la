"""Minimal USGS catalog client (FDSN event), centered on Los Angeles.

API reference: https://earthquake.usgs.gov/fdsnws/event/1/
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

USGS_ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"


@dataclass
class Quake:
    event_id: str
    time: datetime          # origin time (UTC)
    magnitude: float
    place: str
    lat: float
    lon: float
    depth_km: float
    distance_km: float      # distance to the station


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_recent(
    station_lat: float,
    station_lon: float,
    radius_km: float,
    min_magnitude: float,
    lookback_minutes: int = 120,
    timeout: float = 15.0,
) -> list[Quake]:
    """Return recent earthquakes around the station, sorted by time desc."""
    start = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "latitude": station_lat,
        "longitude": station_lon,
        "maxradiuskm": radius_km,
        "minmagnitude": min_magnitude,
        "orderby": "time",
    }
    resp = requests.get(USGS_ENDPOINT, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    quakes: list[Quake] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [None, None, None])
        lon, lat, depth = coords[0], coords[1], coords[2]
        if lat is None or lon is None or props.get("mag") is None:
            continue
        t = datetime.fromtimestamp(props["time"] / 1000.0, tz=timezone.utc)
        quakes.append(
            Quake(
                event_id=feat.get("id", ""),
                time=t,
                magnitude=float(props["mag"]),
                place=props.get("place", ""),
                lat=float(lat),
                lon=float(lon),
                depth_km=float(depth) if depth is not None else 0.0,
                distance_km=_haversine_km(station_lat, station_lon, lat, lon),
            )
        )
    return quakes
