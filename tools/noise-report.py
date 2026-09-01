#!/usr/bin/env python3
"""Noise floor and trigger rate, hour by hour, from the station's container log.

The journal (`event_log.jsonl`) records shakes only. The noise floor between
them exists nowhere but in the MCU heartbeats, which go to stdout and end up in
the Docker log — so any statement about the floor has to come from there.

Pull the log with the recipe in AGENTS.md ("Reading the whole container log"),
which strips the NUL bytes a power cut leaves behind:

    CID=$(docker inspect -f '{{.Id}}' sismo-la-main-1)
    docker run --rm --user 0:0 --entrypoint sh \
      -v /var/lib/docker:/dh:ro ghcr.io/arduino/app-bricks/python-apps-base:0.10.1 \
      -c "tr -d '\\000' < /dh/containers/$CID/$CID-json.log"

then:  python3 tools/noise-report.py container.log [--tz -7]

Since the 2026-09-01 band-pass firmware a heartbeat also carries the wideband
floor beside the in-band one, both averaged over the same ten seconds. Their
ratio is printed as `out-of-band` and is the only measurement here that does not
depend on comparing one time window against another.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HEARTBEAT = re.compile(
    r"mcu alive t=(?P<t>\d+)ms sta/lta=(?P<ratio>[\d.]+) dyn=(?P<dyn>[\d.]+)g"
    r"(?: lta=(?P<lta>[\d.]+)g)?"
    r"(?: wb=(?P<wb>[\d.]+)g)?"
    r"(?: wb_lta=(?P<wblta>[\d.]+)g)?"
    r"(?: fs=(?P<fs>[\d.]+)Hz)?"
)
SHAKE = re.compile(r"shake PGA=(?P<pga>[\d.]+)g dur=(?P<dur>\d+)ms f=(?P<hz>[\d.]+)Hz")


def quantile(values, p):
    values = sorted(values)
    if not values:
        return float("nan")
    k = (len(values) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (k - lo)


def parse(path):
    beats, shakes = [], []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            line, stamp = entry.get("log", ""), entry.get("time", "")
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            hb = HEARTBEAT.search(line)
            if hb:
                beats.append((when, {k: (float(v) if v is not None else None)
                                     for k, v in hb.groupdict().items()}))
                continue
            sh = SHAKE.search(line)
            if sh:
                shakes.append((when, float(sh.group("pga")), float(sh.group("hz"))))
    return beats, shakes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile")
    ap.add_argument("--tz", type=float, default=-7.0, help="hours from UTC")
    ap.add_argument("--since", default="", help="ISO instant, UTC")
    args = ap.parse_args()

    beats, shakes = parse(args.logfile)
    if args.since:
        cut = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        beats = [b for b in beats if b[0] >= cut]
        shakes = [s for s in shakes if s[0] >= cut]
    if not beats:
        print("no heartbeat found - wrong file, or the log is NUL-corrupted")
        return 1

    shift = timedelta(hours=args.tz)
    print(f"{len(beats)} heartbeats, {len(shakes)} shakes, "
          f"{beats[0][0] + shift:%m-%d %H:%M} to {beats[-1][0] + shift:%m-%d %H:%M} local")

    per_hour = defaultdict(lambda: {"beats": [], "shakes": []})
    for when, fields in beats:
        per_hour[(when + shift).strftime("%m-%d %H")]["beats"].append(fields)
    for when, pga, _hz in shakes:
        per_hour[(when + shift).strftime("%m-%d %H")]["shakes"].append(pga)

    header = (f"{'hour (local)':<13} {'n':>4} {'dyn med':>9} {'floor':>9} "
              f"{'wb floor':>9} {'out-of-band':>12} {'sta/lta max':>11} "
              f"{'shakes/h':>9} {'min PGA':>8}")
    print()
    print(header)
    print("-" * len(header))
    for key in sorted(per_hour):
        bucket = per_hour[key]
        rows = bucket["beats"]
        dyn = [r["dyn"] for r in rows if r["dyn"] is not None]
        lta = [r["lta"] for r in rows if r["lta"] is not None]
        wb = [r["wblta"] for r in rows if r["wblta"] is not None]
        ratio = [r["ratio"] for r in rows if r["ratio"] is not None]
        hours = len(rows) * 10.0 / 3600.0
        pgas = bucket["shakes"]
        out_of_band = (f"{st.median(wb) / st.median(lta):.2f}x"
                       if lta and wb and st.median(lta) > 0 else "-")
        print(f"{key:<13} {len(rows):4d} "
              f"{st.median(dyn) if dyn else float('nan'):9.5f} "
              f"{(st.median(lta) if lta else float('nan')):9.5f} "
              f"{(st.median(wb) if wb else float('nan')):9.5f} "
              f"{out_of_band:>12} "
              f"{(max(ratio) if ratio else float('nan')):11.2f} "
              f"{(len(pgas) / hours if hours else float('nan')):9.1f} "
              f"{(min(pgas) if pgas else float('nan')):8.4f}")

    every_lta = [r["lta"] for _t, r in beats if r["lta"] is not None]
    every_wb = [r["wblta"] for _t, r in beats if r["wblta"] is not None]
    if every_lta and every_wb:
        pairs = [(r["wblta"] / r["lta"]) for _t, r in beats
                 if r["lta"] and r["wblta"] and r["lta"] > 0]
        print(f"\nout-of-band fraction over all {len(pairs)} paired heartbeats: "
              f"median {st.median(pairs):.2f}x, p10 {quantile(pairs, 0.1):.2f}x, "
              f"p90 {quantile(pairs, 0.9):.2f}x")
        print("  1.00x = the floor is entirely inside 0.7-12 Hz and the band-pass")
        print("          cannot lower the detection threshold at all.")

    rates = [r["fs"] for _t, r in beats if r["fs"] is not None]
    if rates:
        print(f"\nsample rate: median {st.median(rates):.2f} Hz, "
              f"min {min(rates):.2f}, max {max(rates):.2f} "
              f"(spread {100 * (max(rates) - min(rates)) / st.median(rates):.1f}%)")

    if shakes:
        pgas = [p for _t, p, _h in shakes]
        print(f"\nall shakes: n={len(pgas)}, min PGA {min(pgas):.4f} g, "
              f"p25 {quantile(pgas, .25):.4f}, median {st.median(pgas):.4f}, "
              f"max {max(pgas):.3f} g")
    return 0


if __name__ == "__main__":
    sys.exit(main())
