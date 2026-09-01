"""Append-only journal of everything the station observed.

One JSON object per line, appended the moment a detection is handled and never
rewritten. It exists for two reasons the calibration state files cannot cover:

  - those files keep only the points that *matched* a cataloged earthquake, so
    the far more numerous unmatched shakes — exactly the material the noise
    filter learns from — used to be lost;
  - every record stores the estimate the models produced **before** this
    observation was folded into them. Replaying the journal therefore yields
    prequential (out-of-sample) residuals. The RMSE the models report about
    themselves is a training residual over the same points they were fitted
    on, and is optimistic by construction.

The journal is the raw material: `audit.py` replays it. Keeping it append-only
means a replay always reproduces the same numbers, and a bug fixed later can be
re-run against every shake ever recorded instead of only future ones.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# Schema 2 (2026-09-01) redefines `pga_g`: it is the peak of the 0.7-12 Hz
# band-passed acceleration, the amplitude that actually crossed the trigger,
# where schema 1 recorded the wideband vector magnitude. `dur_ms` and `dom_hz`
# moved to the same band with it. The two eras must never be pooled — a schema-1
# reading is systematically larger, by whatever fraction of that shake's energy
# sat outside the band. Nothing of value was lost in the break: all 255 schema-1
# records are unmatched noise, the calibration stood at 0/8 points, and they
# remain the station's only characterisation of its own ambient noise, which is
# why the journal is appended to and never rewritten. `pga_wb_g` carries the old
# definition alongside the new one so the two can still be related.
SCHEMA = 2


class EventLog:
    """Journal writer. Never raises: losing a log line must not kill the run."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.enabled = bool(path)

    def append(self, evt: dict, match, p_quake: float | None,
               prior: dict) -> None:
        """Record one detection.

        ``prior`` holds what the models predicted *before* learning this event,
        which is the whole point of the file; see the module docstring.
        """
        if not self.enabled:
            return

        record = {
            "schema": SCHEMA,
            "wall_time": _iso(evt.get("recv_time")),
            "mcu_t_ms": evt.get("t_ms"),
            "pga_g": evt.get("pga_g"),
            "pga_wb_g": evt.get("pga_wb_g"),
            "dur_ms": evt.get("dur_ms"),
            "dom_hz": evt.get("dom_hz"),
            "p_quake_prior": p_quake,
            "prior": prior,
            "match": _match_record(evt, match),
        }
        try:
            directory = os.path.dirname(self.path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            print(f"[journal] could not append: {e}", flush=True)

    def count(self) -> int:
        if not self.enabled or not os.path.exists(self.path):
            return 0
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0


def read(path: str) -> list[dict]:
    """Load a journal, skipping corrupt lines rather than aborting.

    A truncated last line is normal if the station lost power mid-write.
    """
    records: list[dict] = []
    if not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"[journal] skipping malformed line {n}")
    return records


def matched_pairs(path: str, limit: int = 400) -> list[dict]:
    """Every confirmed earthquake the station ever caught, oldest first.

    Compact on purpose: this travels in the published snapshot so a public page
    can show the whole record instead of whatever happens to be in memory. The
    in-memory detection list is short and dies with the process, while this
    survives restarts and reinstalls as long as the journal file does.

    The magnitude reported here is the one from ``prior``, i.e. what the model
    predicted BEFORE this earthquake was folded into it. It is therefore an
    honest out-of-sample estimate, not the training residual the dashboard
    quotes about itself. Replay matches are excluded: they are true by
    construction and would flatter the record. See the module docstring.
    """
    out: list[dict] = []
    for r in read(path):
        m, p = r.get("match"), r.get("prior") or {}
        if not m or m.get("synthetic"):
            continue
        dev, usgs_mag = p.get("magnitude_operational"), m.get("magnitude")
        if dev is None or usgs_mag is None:
            continue
        entry = {
            "t": r.get("wall_time"),
            "usgs": round(usgs_mag, 2),
            "dev": round(dev, 2),
            "usgs_km": round(m["distance_km"], 1) if m.get("distance_km") else None,
            "dev_km": round(p["distance_km"], 1) if p.get("distance_km") else None,
        }
        out.append(entry)
    return out[-limit:]


def recent_events(path: str, days: float = 30.0, limit: int = 300) -> list[dict]:
    """Everything the station felt in a rolling window, newest first.

    Read from the journal rather than from the in-memory deque, which holds
    only the last few and restarts empty. Unmatched shakes are kept: a list of
    confirmed earthquakes alone would hide how much of the day is traffic and
    footsteps, which is most of it.

    Keys are terse because this travels in a snapshot that is committed to a
    repository every time it changes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for r in read(path):
        when = _parse(r.get("wall_time"))
        if when is None or when < cutoff:
            continue
        m, p = r.get("match"), r.get("prior") or {}
        entry = {
            "t": r.get("wall_time"),
            "pga": r.get("pga_g"),
            "dur": r.get("dur_ms"),
            "hz": r.get("dom_hz"),
            "dev": _round(p.get("magnitude_operational"), 2),
            "dev_km": _round(p.get("distance_km"), 1),
            "p": _round(r.get("p_quake_prior"), 2),
        }
        if m and not m.get("synthetic"):
            # Kept so a page can tie this reading to the exact catalog event
            # it recognised, rather than guessing from magnitude and time.
            entry["id"] = m.get("event_id") or ""
            entry["usgs"] = _round(m.get("magnitude"), 2)
            entry["usgs_km"] = _round(m.get("distance_km"), 1)
            entry["place"] = m.get("place") or ""
        out.append(entry)
    out.reverse()
    return out[:limit]


def _round(value, digits: int):
    return round(value, digits) if isinstance(value, (int, float)) else None


def _parse(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _iso(value) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return None


def _match_record(evt: dict, match) -> dict | None:
    if match is None:
        return None
    record = {
        "event_id": getattr(match, "event_id", ""),
        "magnitude": getattr(match, "magnitude", None),
        "distance_km": getattr(match, "distance_km", None),
        "depth_km": getattr(match, "depth_km", None),
        "place": getattr(match, "place", ""),
        "origin_time": _iso(getattr(match, "time", None)),
        # Replay pairs an event with the quake it was synthesized from, so its
        # matches are true by construction and must not be counted as evidence
        # that the correlation works.
        "synthetic": "replay_quake" in evt,
    }
    recv = evt.get("recv_time")
    origin = getattr(match, "time", None)
    if isinstance(recv, datetime) and isinstance(origin, datetime):
        record["dt_s"] = (recv - origin).total_seconds()
    return record
