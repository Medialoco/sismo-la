#!/usr/bin/env python3
"""Which cataloged earthquakes should this station have felt, and did it?

    python3 tools/expected-report.py --verify --lat L --lon L
    python3 tools/expected-report.py --years 5 --lat L --lon L
    python3 tools/expected-report.py --live --hours 72
    python3 tools/expected-report.py --from-api http://board:8000/api/state

Four modes, one arithmetic (``python/expected.py``, which is also what the
station runs):

--verify        Reproduce the sensitivity figures already published for this
                station before producing any new ones. If the blind trigger no
                longer scores 1.98-9.79 detections per year over the same
                catalog, something in the chain has drifted and the rest of the
                output is not to be trusted. This exits non-zero when it fails.

--years N       Retrospective. Over N years of catalog, how many events were
                within reach, at the trigger and with the retrospective search.
                No envelope existed before 2026-09-01, so the noise here is the
                measured at-rest floor standing in for it -- an ASSUMPTION, and
                labelled as one in every row it produces.

--live          The watchlist. For each recent cataloged event: the amplitude
                REF_GMPE predicts at the station (PREDICTED), the noise the
                station was actually sitting in at the arrival instant, read out
                of its own continuous recording (MEASURED), what the journal
                says happened (MEASURED), and a verdict. Run it on the board,
                where the envelope and the journal are.

--from-api URL  The same watchlist read off a running station's dashboard port.
                Weaker, and it says so: no envelope travels over HTTP, so the
                noise is assumed rather than measured, and the pairings come
                from a capped in-memory list rather than from the journal. It
                exists because the board has no shell once it leaves USB, and
                this is then the only way to ask it anything.

DO NOT PUBLISH THE PER-EVENT OUTPUT. A detection probability is a monotone
function of hypocentral distance once the magnitude is known, and the catalog
publishes the magnitude. A dozen of these rows locate the station as precisely
as the raw distances that were stripped out of the published snapshot for
exactly that reason. See the privacy section of python/expected.py.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))

import expected                                       # noqa: E402
from expected import (                                # noqa: E402
    REST_FLOOR_G, RETRO_GAIN, TRIGGER_FLOOR_G, SITE_AMPLIFICATION,
)

# The station is at rest about half the time, measured over 17 logged hours, and
# the retrospective test only reaches its threshold then. Every combined figure
# in the documentation carries this weighting; repeating it here keeps the
# comparison like for like.
QUIET_FRACTION = 0.47

# What this must reproduce before it is allowed to produce anything new.
# Published in docs/sensor-upgrade.md and docs/hackster-story.md, computed over
# the five years ending 2026-09-01.
PUBLISHED = {
    "blind": (1.98, 9.79),
    "combined": (9.85, 36.89),
}
VERIFY_START, VERIFY_END = "2021-09-01", "2026-09-01"
TOLERANCE = 0.04


# --- catalog ---------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = (math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2)
         * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def fetch_catalog(lat: float, lon: float, start: str, end: str,
                  radius_km: float, min_mag: float, cache: str = ""):
    """(magnitude, epicentral km, depth km) per event.

    A cache is a disc around one centre. Reusing one fetched around a different
    centre silently truncates the catalog on one side and mis-states every
    distance, which is the class of error this project already made once by
    running for weeks on a position 15.5 km off, so the centre travels with the
    file and a mismatch is refused.
    """
    raw = None
    if cache and os.path.exists(cache):
        raw = json.load(open(cache))
        centre = raw.get("sismo_centre")
        if centre and (abs(centre[0] - lat) > 0.02 or abs(centre[1] - lon) > 0.02):
            raise SystemExit(f"{cache} was fetched around {centre[0]}, "
                             f"{centre[1]}, not {lat}, {lon}")
    if raw is None:
        url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
               f"&latitude={lat}&longitude={lon}&maxradiuskm={radius_km:g}"
               f"&minmagnitude={min_mag:g}&starttime={start}&endtime={end}"
               "&orderby=time")
        with urllib.request.urlopen(url, timeout=120) as fh:
            raw = json.loads(fh.read())
        raw["sismo_centre"] = [lat, lon]
        if cache:
            json.dump(raw, open(cache, "w"))
    out = []
    for feature in raw.get("features", []):
        magnitude = feature["properties"].get("mag")
        coords = feature["geometry"]["coordinates"]
        if magnitude is None or coords is None or coords[1] is None:
            continue
        out.append((float(magnitude),
                    haversine_km(lat, lon, coords[1], coords[0]),
                    float(coords[2] or 0.0)))
    return out


def read_snapshot(where: str) -> dict:
    if where.startswith("http"):
        with urllib.request.urlopen(where, timeout=30) as fh:
            return json.loads(fh.read())
    with open(where, "r", encoding="utf-8") as fh:
        return json.load(fh)


def station_position(args, snapshot: dict | None = None) -> tuple[float, float, str]:
    """Where the station is, from the most trustworthy source available.

    The order matters and the reason is a mistake this project already made:
    it ran for weeks on a centre 15.5 km off the real one, which mis-stated
    every epicentral distance and therefore every probability this tool
    computes. So the live station's own snapshot wins over any local file, and
    a fallback to the example config -- which carries a neutral placeholder,
    not this station -- is reported as such rather than silently used.
    """
    if args.lat is not None and args.lon is not None:
        return args.lat, args.lon, "command line"
    for source in (snapshot, ) if snapshot else ():
        station = (source or {}).get("station") or {}
        if station.get("lat") is not None and station.get("lon") is not None:
            return float(station["lat"]), float(station["lon"]), "the snapshot"
    if getattr(args, "station_from", ""):
        remote = read_snapshot(args.station_from)
        station = remote.get("station") or {}
        if station.get("lat") is None:
            raise SystemExit(
                f"{args.station_from} publishes no station position -- that is "
                "the privacy stripping working as intended on a public "
                "snapshot. Point --station-from at the station's own "
                "/api/state on the local network, or pass --lat/--lon.")
        return float(station["lat"]), float(station["lon"]), args.station_from
    from pipeline import load_config, resolve_config_path
    resolved = resolve_config_path(args.config)
    cfg = load_config(args.config)
    which = str(resolved)
    if resolved.name == "config.example.yaml" and args.config.endswith(
            "config.yaml"):
        which += "  <-- PLACEHOLDER POSITION, not this station"
    return cfg["station"]["lat"], cfg["station"]["lon"], which


# --- modes -----------------------------------------------------------------

def rates(events, floor_g: float, years: float) -> tuple[float, float]:
    lo, hi = SITE_AMPLIFICATION
    return (expected.rate_per_year(events, floor_g, lo, years),
            expected.rate_per_year(events, floor_g, hi, years))


def verify(events, years: float) -> int:
    """Reproduce the published rates, or say loudly that the chain has moved."""
    blind = rates(events, TRIGGER_FLOOR_G, years)
    retro = rates(events, TRIGGER_FLOOR_G / RETRO_GAIN, years)
    combined = tuple(b + QUIET_FRACTION * (r - b) for b, r in zip(blind, retro))

    print(f"catalog: {len(events)} events over {years:g} years")
    print(f"trigger floor {TRIGGER_FLOOR_G * 1000:.3f} mg "
          f"(at-rest floor {REST_FLOOR_G * 1000:.2f} mg "
          f"x {expected.TRIGGER_OVER_NOISE:.2f})")
    failures = 0
    for label, got in (("blind", blind), ("combined", combined)):
        want = PUBLISHED[label]
        drift = max(abs(g - w) / w for g, w in zip(got, want))
        ok = drift <= TOLERANCE
        failures += not ok
        print(f"  {label:9s} {got[0]:6.2f} - {got[1]:6.2f} /yr   "
              f"published {want[0]:.2f} - {want[1]:.2f}   "
              f"drift {100 * drift:4.1f}%   {'ok' if ok else 'MISMATCH'}")
    if failures:
        print("\nThe published figures are not reproduced. Either the catalog "
              "has moved under the query or a constant has changed; do not "
              "quote anything this tool prints until this passes.")
    else:
        print("\nReproduced. The per-event probabilities below rest on the same "
              "arithmetic as the published rates.")
    return failures


def retrospective(events, years: float) -> None:
    """How often the ground has actually been within reach, over N years."""
    print(f"catalog: {len(events)} events M>=2, {years:g} years\n")
    print("Every row is PREDICTED. The envelope recording only begins "
          "2026-09-01,\nso the noise here is the measured at-rest floor "
          f"({REST_FLOOR_G * 1000:.2f} mg) standing in for\nthe real level at "
          "each arrival, which is an assumption, not a measurement.\n")

    header = (f"{'channel':<28s}{'floor':>9s}{'det/yr, site x1..x4':>22s}"
              f"{'mean wait':>12s}{'P(12 d)':>12s}")
    print(header)
    print("-" * len(header))
    blind = rates(events, TRIGGER_FLOOR_G, years)
    retro = rates(events, TRIGGER_FLOOR_G / RETRO_GAIN, years)
    combined = tuple(b + QUIET_FRACTION * (r - b) for b, r in zip(blind, retro))
    rows = (
        ("blind trigger", TRIGGER_FLOOR_G, blind),
        ("retrospective, site at rest", TRIGGER_FLOOR_G / RETRO_GAIN, retro),
        (f"both, quiet fraction {QUIET_FRACTION:.2f}", None, combined),
    )
    for label, floor, (lo, hi) in rows:
        floor_txt = f"{floor * 1000:.3f} mg" if floor else ""
        print(f"{label:<28s}{floor_txt:>9s}"
              f"{lo:>11.2f} -{hi:>9.2f}"
              f"{365 / hi:>7.0f}-{365 / lo:<5.0f}"
              f"{100 * (1 - math.exp(-lo * 12 / 365)):>7.1f}"
              f"-{100 * (1 - math.exp(-hi * 12 / 365)):<4.1f}%")

    # How the expectation is distributed over events, which the rate alone
    # hides: a rate of 2/yr made of two near-certainties is a different station
    # from the same rate made of two thousand long shots.
    print("\nhow that rate is made up (blind trigger, pessimistic site x1)")
    bands = ((expected.P_EXPECTED, 1.01, "in reach      p >= 0.50"),
             (expected.P_NEGLIGIBLE, expected.P_EXPECTED, "marginal      0.10 - 0.50"),
             (0.0, expected.P_NEGLIGIBLE, "out of reach  p <  0.10"))
    for lo_p, hi_p, label in bands:
        n = 0
        for magnitude, distance_km, depth_km in events:
            median = expected.expected_log_pga(magnitude, distance_km, depth_km)
            p = expected.detection_probability(median, TRIGGER_FLOOR_G,
                                               SITE_AMPLIFICATION[0])
            n += lo_p <= p < hi_p
        print(f"  {label:<28s}{n:6d} events  ({100.0 * n / max(1, len(events)):.1f}%)")

    print("\nmagnitude needed, 8 km deep, site x1, +-0.45 Mw (1 sigma)")
    dists = (10, 30, 50, 100, 160)
    print("   km      " + "".join(f"{d:>7d}" for d in dists))
    for label, floor in (("blind", TRIGGER_FLOOR_G),
                         ("retro", TRIGGER_FLOOR_G / RETRO_GAIN)):
        cells = "".join(f"{expected.magnitude_needed(floor, d):7.1f}"
                        for d in dists)
        print(f"   {label:<7s}" + cells)


def from_api(args) -> None:
    """Audit a station that cannot be logged into, over its dashboard port.

    The board has no shell once it leaves USB, so this is the only remote
    diagnostic surface there is. It is a weaker audit than the one that runs on
    the station and the output says so: there is no envelope over HTTP, so the
    noise is the at-rest floor assumed rather than measured, and the pairings
    come from a short in-memory list rather than from the journal.
    """
    import usgs

    snapshot = read_snapshot(args.from_api)

    min_mag = (snapshot.get("config") or {}).get("min_magnitude",
                                                 args.min_magnitude)
    quakes = []
    for q in snapshot.get("quakes") or []:
        if q.get("distance_km") is None:
            # A published snapshot has had the distances stripped out of it, on
            # purpose: a dozen of them trilaterate the station. The catalog is
            # public, so it can simply be refetched around a centre the operator
            # supplies rather than one the snapshot leaks.
            quakes = []
            break
        quakes.append(usgs.Quake(
            q.get("event_id", ""), datetime.fromisoformat(q["time"]),
            float(q["magnitude"]), q.get("place", ""), float(q["lat"]),
            float(q["lon"]), float(q.get("depth_km") or 0.0),
            float(q["distance_km"])))

    source = "the snapshot's own catalog"
    if not quakes or args.hours_given:
        lat, lon, which = station_position(args, snapshot)
        radius = (snapshot.get("config") or {}).get("radius_km",
                                                    args.radius_km)
        quakes = usgs.fetch_recent(lat, lon, radius, min_mag,
                                   lookback_minutes=int(args.hours * 60))
        source = f"USGS, last {args.hours:g} h, position from {which}"
    quakes = [q for q in quakes if q.magnitude >= min_mag]

    observations = expected.Observations.from_snapshot(snapshot)
    rows = expected.build(quakes, store=None, observations=observations)
    health = snapshot.get("health") or {}
    print(f"{args.from_api}\n  mode {snapshot.get('mode')}, "
          f"mcu_ok={health.get('mcu_ok')}, published {snapshot.get('updated')}"
          f"\n  catalog: {source}, {len(rows)} events M>={min_mag}\n")
    report(rows)
    print("\nREMOTE AUDIT, weaker than the one that runs on the station: no "
          "envelope travels\n  over HTTP, so every noise figure above is the "
          "at-rest floor ASSUMED, and the\n  pairings come from a snapshot list "
          "rather than from the journal. A 'missed'\n  here is a lead, not a "
          "finding; confirm it against event_log.jsonl.")


def report(rows) -> None:
    """The watchlist table, shared by the on-board and the remote modes."""
    header = (f"{'verdict':<13s}{'origin (UTC)':<18s}{'M':>4s}{'km':>6s}"
              f"{'exp mg':>8s}{'noise mg':>10s}{'P trig':>13s}"
              f"{'P retro':>13s}{'z':>7s}  observed")
    print(header)
    print("-" * len(header))
    for row in rows:
        noise = row["noise"]
        mark = "*" if noise["source"] == "measured" else " "
        z = f"{row['z']:.1f}" if row.get("z") is not None else "-"
        observed = row["observed"]
        if row.get("unpaired"):
            observed += f" (+{len(row['unpaired'])} unpaired shakes)"
        print(f"{row['verdict']:<13s}"
              f"{row['origin_time'][:16].replace('T', ' '):<18s}"
              f"{row['magnitude']:>4.1f}{row['distance_km']:>6.0f}"
              f"{row['expected']['pga_g'] * 1000:>8.3f}"
              f"{noise['g'] * 1000:>9.3f}{mark}"
              f"{row['p_trigger'][0]:>6.2f}-{row['p_trigger'][1]:<6.2f}"
              f"{row['p_retro'][0]:>6.2f}-{row['p_retro'][1]:<6.2f}"
              f"{z:>7s}  {observed}")

    print("\n* noise MEASURED in the station's own envelope at that instant; "
          "otherwise the\n  at-rest floor is assumed. 'exp mg' is PREDICTED by "
          "REF_GMPE and carries\n  0.39 log10 of scatter. Probability ranges "
          "are site amplification x1 to x4.")

    counts = expected.counts(rows)
    print("\n" + "  ".join(f"{v}: {counts[v]}" for v in expected.ORDER
                           if counts[v]))
    missed = [r for r in rows if r["verdict"] == expected.V_MISSED]
    if missed:
        print(f"\n{len(missed)} event(s) SHOULD HAVE BEEN SEEN AND WERE NOT. "
              "That is a fault, not\nseismology: check the MCU heartbeat, the "
              "trigger threshold and the pairing gates.")
        for row in missed:
            print(f"  M{row['magnitude']:.1f} at {row['distance_km']:.0f} km, "
                  f"{row['origin_time'][:19]}, via the {row['channel']} "
                  f"channel, {row['place']}")
    else:
        print("\nNothing in the 'should have been seen' category.")

    print("\nOperator output. Per-event probabilities are epicentral distances "
          "in disguise;\nonly the three counts in expected.summarise() are safe "
          "to publish.")


def live(args) -> None:
    """The watchlist: what the recent catalog implies, against what happened."""
    import usgs
    from envelope import EnvelopeStore
    from pipeline import load_config
    import retro as retro_mod

    cfg = load_config(args.config)
    st, us = cfg["station"], cfg["usgs"]
    envcfg = cfg.get("envelope") or {}
    rcfg = cfg.get("retro") or {}
    calcfg = cfg.get("calibration") or {}

    store = EnvelopeStore(args.envelope or envcfg.get("directory", "envelope"),
                          retention_days=envcfg.get("retention_days", 14))
    retro_log = retro_mod.RetroLog(
        args.retro_state or rcfg.get("state_file", "retro_state.json"))
    retro_log.load()
    journal = args.journal or calcfg.get("journal_file", "event_log.jsonl")

    quakes = usgs.fetch_recent(st["lat"], st["lon"], us["radius_km"],
                               us["min_magnitude"],
                               lookback_minutes=int(args.hours * 60))
    rows = expected.build(quakes, store=store, journal_path=journal,
                          retro_log=retro_log)
    if not rows:
        print(f"no cataloged event M>={us['min_magnitude']} in the last "
              f"{args.hours:g} h")
        return

    coverage = store.coverage()
    print(f"{len(rows)} cataloged events in the last {args.hours:g} h; "
          f"envelope holds {coverage['days']} day files "
          f"({coverage['bytes'] / 1e6:.1f} MB)\n")
    report(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--years", type=float, default=0.0)
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--radius-km", type=float, default=160.0)
    ap.add_argument("--min-magnitude", type=float, default=2.0)
    ap.add_argument("--catalog", default="", help="cached USGS geojson")
    ap.add_argument("--envelope", default="")
    ap.add_argument("--journal", default="")
    ap.add_argument("--retro-state", default="")
    ap.add_argument("--from-api", default="",
                    help="audit a running station over its dashboard port, "
                         "e.g. http://<board>:8000/api/state - the only remote "
                         "surface once the board leaves USB")
    ap.add_argument("--station-from", default="",
                    help="take the station position from a running station's "
                         "/api/state instead of a local config; the position "
                         "is deliberately absent from this repository, so "
                         "--verify and the retrospective mode need this or "
                         "--lat/--lon to mean anything")
    args = ap.parse_args()
    # --hours means "refetch the catalog over this window" rather than "use the
    # one the snapshot happens to carry", so the two have to be distinguishable.
    args.hours_given = any(a.startswith("--hours") for a in sys.argv[1:])

    if args.from_api:
        from_api(args)
        return
    if args.live:
        live(args)
        return

    lat, lon, which = station_position(args)
    if "PLACEHOLDER" in which:
        # Every number below is an epicentral distance, so a placeholder centre
        # does not give an approximate answer, it gives a different station's.
        # The published figures were computed for the real one and --verify
        # would report a mismatch that looks like a code regression.
        raise SystemExit(
            "The station position is not in this repository, by design, and\n"
            f"{args.config} is absent here, so the example placeholder was\n"
            "loaded instead. Give the real one:\n"
            "  --station-from http://<board>:8000/api/state   (on the LAN)\n"
            "  --lat <deg> --lon <deg>                        (anywhere)")
    if args.verify:
        events = fetch_catalog(lat, lon, VERIFY_START, VERIFY_END,
                               args.radius_km, args.min_magnitude, args.catalog)
        print(f"[position from {which}]  verification window "
              f"{VERIFY_START} .. {VERIFY_END}")
        raise SystemExit(1 if verify(events, 5.0) else 0)

    years = args.years or 5.0
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365.25 * years)
    events = fetch_catalog(lat, lon, start.strftime("%Y-%m-%d"),
                           end.strftime("%Y-%m-%d"), args.radius_km,
                           args.min_magnitude, args.catalog)
    print(f"[position from {which}]")
    retrospective(events, years)


if __name__ == "__main__":
    main()
