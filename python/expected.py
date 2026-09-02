"""What the station should have felt, set against what it actually felt.

WHY THIS EXISTS
===============
An absence of detection is mute. When a cataloged earthquake goes by and the
station says nothing, that silence covers two completely different situations:

  - the shaking never reached the trigger, which is the normal outcome for
    almost every earthquake in this catalog and says nothing about the station;
  - the shaking *should* have reached it and did not, which is a fault — a dead
    sensor link, a mis-set threshold, a correlation window that rejected a
    genuine pairing.

Nothing in the station could tell those apart. This module does, by computing,
for every cataloged event, the amplitude it should have delivered here and the
noise the station was actually sitting in at that instant, and confronting the
two with what the journal says happened.

MEASURED vs PREDICTED — the distinction this module exists to keep
==================================================================
Every field is tagged, and the two must never be read as the same kind of thing:

  PREDICTED (a model, with 0.39 log10 of scatter)
      ``expected.pga_g``    the median ground motion REF_GMPE puts at the
                            station for that magnitude and distance.
      ``p_trigger``,
      ``p_retro``           probabilities derived from it.

  MEASURED (the station's own record, no model)
      ``noise.g``           the median envelope level over the three minutes
                            before the arrival, read out of the continuous
                            recording. This is the number that makes the
                            analysis honest: an earthquake that arrived while
                            somebody was walking over the sensor was not
                            detectable, and saying so avoids diagnosing a bug
                            that is not there. The level varies by a factor of
                            four between a quiet night and a busy afternoon.
      ``z``                 how far the envelope actually stood above that
                            noise at the arrival instant.
      ``observed``          what the journal recorded.

An expected amplitude is not an observation, and no count derived from one may
be presented as a detection.

HOW THE THRESHOLD FOLLOWS THE NOISE
===================================
The blind trigger is STA/LTA, so the amplitude needed to fire it is
proportional to the level the LTA is tracking. Two measurements fix the
constant: the smallest peak that has ever triggered this station is 0.0044 g
before the band-pass, i.e. 0.00308 g after it (the band-pass lowered the at-rest
floor by a measured 1.43x and the trigger floor follows, being a ratio), and the
at-rest floor itself is 0.00036 g. Their quotient, 8.55, is the only free
parameter here, and it is measured rather than chosen. At any instant, then:

    trigger floor = 8.55 x (the envelope level measured at that instant)
    retro  floor  = trigger floor / 7.4

The 7.4 is the amplitude gain of the retrospective search over the blind
trigger, simulated by ``tools/retro-gain.py`` on this station's own noise with
the estimator that runs on the board.

Feed it the reference at-rest floor and the trigger floor comes back out at
0.00308 g, so this reproduces the station's published sensitivity exactly
instead of competing with it. ``tools/expected-report.py --verify`` checks that
against the published 1.98-9.79 detections per year and refuses to go on if it
has drifted.

Probabilities are computed by the same routine ``tools/sensor-gain.py`` uses:
the 0.390 log10 scatter of the ground-motion fit, integrated over the threshold,
with the unknown indoor site amplification carried as a x1 to x4 range rather
than as a point value. That range is the dominant uncertainty in every number
here and it is why nothing below is a verdict of "would have been detected".

ONE LIMIT OF THE RETROSPECTIVE COLUMN. Its real test is significance against the
local *dispersion*, and dispersion grows faster than the median when the site is
busy. Scaling its floor by the measured median therefore flatters it in exactly
those periods; ``p_retro`` should be read as an upper bound whenever
``noise.g`` is well above the at-rest floor.

PRIVACY — READ BEFORE PUBLISHING ANY OF THIS
============================================
A per-event detection probability is an epicentral distance in disguise. Given a
magnitude, which the catalog publishes, the probability computed here is a
monotone function of hypocentral distance, so a dozen of these rows trilaterate
the station just as the raw ``distance_km`` field did before ``strip_location``
removed it. The watchlist is therefore an OPERATOR artefact: it belongs on the
local dashboard, on the operator's own network, and it must never reach the
published snapshot.

What may be published is ``summarise()`` alone, and deliberately only three
integers: how many cataloged events were examined, how many the envelope
covered, and how many fall in the "should have been seen" category. The first
two are properties of the catalog rate and of recording uptime, neither of which
is a distance. The third is the alarm, it is zero in normal operation, and a
count carries no geometry. Anything richer — the reach counts, a magnitude, a
probability, an event id — is withheld, because with only a handful of cataloged
events in a window, knowing which ones were "in reach" is knowing a distance
band for each of them.
"""

from __future__ import annotations

import bisect
import math
from datetime import datetime, timezone

import eventlog
import retro
from pipeline import (
    REF_GMPE,
    REF_GMPE_SIGMA,
    amplitude_is_plausible,
    travel_time_window,
)

# --- The measured constants this module rests on ---------------------------
# At-rest in-band envelope level, g. Measured over the quietest quarter of 277
# paired heartbeats and confirmed to be the sensor's own electrical noise: the
# LSM6DSOX's datasheet 110 ug/sqrt(Hz) over the band-passed chain's 5.21 Hz
# equivalent noise bandwidth predicts 0.00040 g, and the wideband channel of the
# same ten seconds predicted 0.00050 g and measured 0.00052 g.
REST_FLOOR_G = 0.00036
# Smallest peak that has ever fired the blind trigger, carried across the
# band-pass by the measured 1.43x reduction of the floor at rest.
TRIGGER_FLOOR_G = 0.0044 / 1.43
# The only ratio in this module, and it is a quotient of two measurements, not a
# tuning knob: how far above the ambient level a shake has to reach to trip
# STA/LTA. Changing either constant above changes it consistently.
TRIGGER_OVER_NOISE = TRIGGER_FLOOR_G / REST_FLOOR_G
# Amplitude gain of the retrospective search, geometric mean over three
# wavetrain shapes; tools/retro-gain.py, which calls retro.significance itself.
# Run-to-run Monte-Carlo scatter is real (7.4 and 8.0 on two passes), so this is
# "about 7-8", never a third digit.
RETRO_GAIN = 7.4
# Unknown for an indoor mount, and station-to-station scatter dominates the
# ground-motion fit (0.347 of 0.390 log10). Every probability is a range.
SITE_AMPLIFICATION = (1.0, 4.0)

# --- Where the categories cut ----------------------------------------------
# Deliberately asymmetric. An event is only called "should have been seen" when
# even the PESSIMISTIC end of the site range says it was more likely than not,
# so the alarm cannot be raised by the optimistic assumption alone. It is called
# out of reach only when even the OPTIMISTIC end says it was unlikely.
P_EXPECTED = 0.5
P_NEGLIGIBLE = 0.10

V_TRIGGERED = "triggered"        # the station fired on its own
V_CONFIRMED = "confirmed"        # found at an instant the catalog supplied
V_MISSED = "missed"              # in reach, recorded, and nothing happened
V_MARGINAL = "marginal"          # the interesting middle: at the limit
V_OUT_OF_REACH = "out-of-reach"  # normal, nothing to report
V_NO_COVERAGE = "no-coverage"    # no recording at that instant: no verdict

# Worst first: the whole point is that a miss surfaces immediately.
ORDER = (V_MISSED, V_MARGINAL, V_TRIGGERED, V_CONFIRMED, V_NO_COVERAGE,
         V_OUT_OF_REACH)


def norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def expected_log_pga(magnitude: float, distance_km: float,
                     depth_km: float = 0.0) -> float:
    """Median log10 PGA at the station, in g. PREDICTED, not measured.

    REF_GMPE, refit on 12324 PGA values recorded by USGS ShakeMap stations
    during 40 southern-California earthquakes. Not the law replay uses, which
    over-predicts by 37.9x; see pipeline.py.
    """
    a, b, c = REF_GMPE
    hypo = max(math.hypot(distance_km or 0.0, depth_km or 0.0), 3.0)
    return a * magnitude + b * math.log10(hypo) + c


def detection_probability(median_log10: float, threshold_g: float,
                          amplification: float) -> float:
    """Probability that the real ground motion cleared ``threshold_g``.

    The same computation tools/sensor-gain.py uses for the published rates: the
    0.390 log10 scatter of the fit stands in for path and site luck, and the
    probability is integrated rather than the median being compared to the
    threshold, because the rate is dominated by the tail.
    """
    if threshold_g <= 0:
        return 0.0
    target = math.log10(threshold_g) - math.log10(amplification)
    return norm_cdf((median_log10 - target) / REF_GMPE_SIGMA)


def probability_range(median_log10: float, threshold_g: float
                      ) -> tuple[float, float]:
    lo, hi = SITE_AMPLIFICATION
    return (detection_probability(median_log10, threshold_g, lo),
            detection_probability(median_log10, threshold_g, hi))


def rate_per_year(events, threshold_g: float, amplification: float,
                  years: float) -> float:
    """Expected genuine detections per year over a catalog.

    ``events`` is an iterable of (magnitude, epicentral km, depth km). Kept here
    rather than in the tool so the live watchlist and the retrospective rate are
    the same arithmetic; tools/expected-report.py --verify checks it against the
    published figures.
    """
    total = 0.0
    for magnitude, distance_km, depth_km in events:
        median = expected_log_pga(magnitude, distance_km, depth_km)
        total += detection_probability(median, threshold_g, amplification)
    return total / years if years else 0.0


def magnitude_needed(threshold_g: float, distance_km: float,
                     depth_km: float = 8.0) -> float:
    a, b, c = REF_GMPE
    hypo = max(math.hypot(distance_km, depth_km), 3.0)
    return (math.log10(threshold_g) - b * math.log10(hypo) - c) / a


# --- What the station was sitting in, at that instant ----------------------

def _slice(samples, lo: float, hi: float) -> list:
    """Samples with lo <= epoch <= hi, from a time-ordered list."""
    keys = [s[0] for s in samples]
    return samples[bisect.bisect_left(keys, lo):bisect.bisect_right(keys, hi)]


def read_span(store, quakes, pad_s: float = 30.0) -> list:
    """The envelope around every earthquake in a batch, in one time-ordered list.

    Deliberately NOT one read over the union of the windows. The audit reaches
    back as far as the recording is retained, so that union is a fortnight —
    1.2 million samples, most of them between the events rather than around
    them. Overlapping windows are merged and read individually instead, which
    keeps the result to a few minutes per earthquake however far apart they are.
    """
    if store is None or not getattr(store, "enabled", False) or not quakes:
        return []
    spans = []
    for quake in quakes:
        start, end = retro.search_window(quake)
        spans.append((start - retro.BASELINE_S - retro.BASELINE_GAP_S - pad_s,
                      end + pad_s))
    spans.sort()
    merged = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    out: list = []
    for start, end in merged:
        out.extend(store.read(datetime.fromtimestamp(start, tz=timezone.utc),
                              datetime.fromtimestamp(end, tz=timezone.utc)))
    out.sort(key=lambda r: r[0])
    return out


def envelope_context(samples, quake) -> dict:
    """The MEASURED noise around one earthquake's arrival window.

    Three outcomes, and the difference between them matters:
      coverage "full"    - the arrival window and enough baseline before it were
                           recorded, so the local noise is measured and the
                           retrospective test could run;
      coverage "partial" - the arrival was recorded but not enough of the
                           preceding minutes to say what normal looked like;
      coverage "none"    - nothing was recorded then. Not a miss, not a success.
    """
    start, end = retro.search_window(quake)
    in_window = _slice(samples, start, end) if samples else []
    if not in_window:
        return {"coverage": "none", "n_window": 0}
    stat = retro.significance(samples, start, end)
    if stat is None:
        return {"coverage": "partial", "n_window": len(in_window)}
    return {
        "coverage": "full",
        "n_window": len(in_window),
        "noise_g": stat["baseline_g"],
        "sigma_g": stat["sigma_g"],
        "z": stat["z"],
        "peak_g": stat["peak_g"],
        "rms_g": stat["rms_g"],
        "window_s": stat["window_s"],
        "n_baseline": stat["n_baseline"],
    }


# --- What actually happened ------------------------------------------------

class Observations:
    """The journal and the retrospective log, indexed for lookup by earthquake.

    The two channels stay apart here exactly as they do everywhere else: a
    triggered record and a confirmation are different fields with different
    names, never a list with a flag on it.
    """

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "Observations":
        """Rebuild from a ``/api/state`` payload instead of from the files.

        The station's journal lives on a board with no shell: off USB the only
        remote surface is the dashboard port. This is what lets the audit run
        from a laptop against a station that cannot be logged into.

        Handles both shapes a snapshot comes in, because they have different
        reaches and the wider one is not always available:

          ``detections`` / ``retro.confirmed``  the live ``/api/state``. RAM
              only: a short deque, so a pairing older than the last few dozen
              shakes is simply absent and would read as a miss.
          ``recent`` / ``confirmed``            the published snapshot. Rebuilt
              from the journal on every publish, so it reaches back the whole
              publication window, but only as far as the last publish.

        Either way this is weaker than reading the journal, and no alarm raised
        from it should be believed before it is checked there.
        """
        self = cls()
        for detection in snapshot.get("detections") or []:
            match = detection.get("match") or {}
            if match.get("event_id"):
                self.matched.setdefault(match["event_id"], {
                    "wall_time": detection.get("recv_time"),
                    "pga_g": detection.get("pga_g"),
                    "dur_ms": detection.get("dur_ms"),
                    "dom_hz": detection.get("dom_hz"),
                    "match": match,
                })
        for shake in snapshot.get("recent") or []:
            if shake.get("id"):
                self.matched.setdefault(shake["id"], {
                    "wall_time": shake.get("t"),
                    "pga_g": shake.get("pga"),
                    "dur_ms": shake.get("dur"),
                    "dom_hz": shake.get("hz"),
                })
        findings = ((snapshot.get("retro") or {}).get("confirmed") or []) \
            + (snapshot.get("confirmed") or [])
        for finding in findings:
            event_id = finding.get("event_id") or finding.get("id")
            if event_id:
                self.findings[event_id] = dict(finding, confirmed=True)
        self.partial = True
        return self

    def __init__(self, journal_path: str = "", retro_log=None) -> None:
        self.matched: dict[str, dict] = {}
        self.timeline: list[tuple[float, dict]] = []
        self.partial = False
        self.findings: dict[str, dict] = dict(
            getattr(retro_log, "findings", None) or {})
        if not journal_path:
            return
        for record in eventlog.read(journal_path):
            if eventlog.kind_of(record) != eventlog.TRIGGERED:
                continue
            when = _parse(record.get("wall_time"))
            if when is not None:
                self.timeline.append((when.timestamp(), record))
            match = record.get("match")
            if match and not match.get("synthetic") and match.get("event_id"):
                self.matched.setdefault(match["event_id"], record)
        self.timeline.sort(key=lambda r: r[0])

    def of(self, quake) -> dict:
        """What the station recorded for this earthquake, if anything."""
        event_id = getattr(quake, "event_id", "")
        trigger = self.matched.get(event_id)
        finding = self.findings.get(event_id)
        out = {
            "triggered": trigger is not None,
            "confirmed": bool(finding and finding.get("confirmed")),
            "scanned": finding is not None,
            "trigger": None,
            "finding": finding,
            "unpaired": [],
        }
        if trigger:
            out["trigger"] = {
                "t": trigger.get("wall_time"),
                "pga_g": trigger.get("pga_g"),
                "dur_ms": trigger.get("dur_ms"),
                "dom_hz": trigger.get("dom_hz"),
            }
            return out
        # No stored pairing. A trigger may still have fired at the right instant
        # and never been attributed — the catalog is polled on a timer, so an
        # event published after the shake was handled can never be matched. That
        # is a pairing gap rather than a miss, and the two want different
        # repairs, so it is reported separately instead of being counted as a
        # detection.
        out["unpaired"] = self._in_window(quake)
        return out

    def _in_window(self, quake) -> list[dict]:
        distance = getattr(quake, "distance_km", 0.0) or 0.0
        depth = getattr(quake, "depth_km", 0.0) or 0.0
        lo, hi = travel_time_window(distance, depth)
        origin = quake.time.timestamp()
        keys = [t for t, _ in self.timeline]
        left = bisect.bisect_left(keys, origin + lo)
        right = bisect.bisect_right(keys, origin + hi)
        out = []
        for _, record in self.timeline[left:right]:
            pga = record.get("pga_g")
            if pga is not None and not amplitude_is_plausible(
                pga, quake.magnitude, distance, depth
            ):
                continue
            out.append({"t": record.get("wall_time"), "pga_g": pga,
                        "dur_ms": record.get("dur_ms"),
                        "dom_hz": record.get("dom_hz")})
        return out


# --- Putting the two together ----------------------------------------------

def assess(quake, samples, observations: Observations) -> dict:
    """One row of the watchlist: predicted reach against recorded reality."""
    distance = getattr(quake, "distance_km", 0.0) or 0.0
    depth = getattr(quake, "depth_km", 0.0) or 0.0
    median = expected_log_pga(quake.magnitude, distance, depth)

    env = envelope_context(samples, quake)
    measured = env.get("coverage") == "full"
    noise_g = env["noise_g"] if measured else REST_FLOOR_G
    trigger_floor = TRIGGER_OVER_NOISE * noise_g
    retro_floor = trigger_floor / RETRO_GAIN

    p_trigger = probability_range(median, trigger_floor)
    p_retro = probability_range(median, retro_floor)
    seen = observations.of(quake)

    # The retrospective channel only existed where there is a recording. The
    # blind trigger ran at all times, so its column is meaningful either way —
    # with the at-rest floor standing in for the noise, which is an assumption
    # and is labelled as one.
    if seen["triggered"]:
        verdict, channel = V_TRIGGERED, "trigger"
    elif seen["confirmed"]:
        verdict, channel = V_CONFIRMED, "retro"
    elif p_trigger[0] >= P_EXPECTED:
        verdict, channel = V_MISSED, "trigger"
    elif measured and p_retro[0] >= P_EXPECTED:
        verdict, channel = V_MISSED, "retro"
    elif max(p_trigger[1], p_retro[1]) < P_NEGLIGIBLE:
        # Out of reach for both channels, so the missing recording would not
        # have changed anything and saying "no coverage" would be noise.
        verdict, channel = V_OUT_OF_REACH, None
    elif not measured:
        verdict, channel = V_NO_COVERAGE, None
    else:
        verdict, channel = V_MARGINAL, None

    row = {
        "event_id": getattr(quake, "event_id", ""),
        "origin_time": quake.time.isoformat(),
        "magnitude": quake.magnitude,
        "place": getattr(quake, "place", ""),
        "distance_km": round(distance, 1),
        "depth_km": round(depth, 1),
        # PREDICTED
        "expected": {
            "pga_g": round(10.0 ** median, 7),
            "log10_sigma": REF_GMPE_SIGMA,
        },
        "p_trigger": [round(p_trigger[0], 3), round(p_trigger[1], 3)],
        "p_retro": [round(p_retro[0], 3), round(p_retro[1], 3)],
        "trigger_floor_g": round(trigger_floor, 7),
        "retro_floor_g": round(retro_floor, 7),
        # MEASURED
        "coverage": env.get("coverage", "none"),
        "noise": {
            "g": round(noise_g, 7),
            "source": "measured" if measured else "assumed",
        },
        "z": env.get("z"),
        "observed": (V_TRIGGERED if seen["triggered"] else
                     V_CONFIRMED if seen["confirmed"] else "none"),
        "verdict": verdict,
        "channel": channel,
    }
    if measured:
        row["noise"]["sigma_g"] = round(env["sigma_g"], 7)
        row["noise"]["n_baseline"] = env["n_baseline"]
        row["peak_g"] = round(env["peak_g"], 7)
    if seen["trigger"]:
        row["trigger"] = seen["trigger"]
    if seen["unpaired"]:
        # A shake at the right instant with no stored pairing. Reported, never
        # counted as a detection: only the station's own correlation decides
        # that, and this is a note that it may have had the chance and missed it.
        row["unpaired"] = seen["unpaired"][:3]
    return row


def build(quakes, store=None, journal_path: str = "", retro_log=None,
          observations: "Observations | None" = None) -> list[dict]:
    """Assess a whole catalog slice. Worst verdict first, then most recent."""
    quakes = list(quakes)
    if not quakes:
        return []
    samples = read_span(store, quakes)
    if observations is None:
        observations = Observations(journal_path, retro_log)
    rows = [assess(q, samples, observations) for q in quakes]
    rank = {v: i for i, v in enumerate(ORDER)}
    rows.sort(key=lambda r: (rank.get(r["verdict"], 99),
                             -_epoch(r["origin_time"])))
    return rows


def summarise(rows) -> dict:
    """The only part of this that may be published. See the module docstring.

    Three integers, none of which is a distance: how many cataloged events were
    examined, how many the recording covered, and how many should have been seen
    and were not. The last is the alarm and is zero in normal operation.
    """
    return {
        "n": len(rows),
        "covered": sum(1 for r in rows if r["coverage"] == "full"),
        "missed": sum(1 for r in rows if r["verdict"] == V_MISSED),
    }


def counts(rows) -> dict:
    """Full breakdown by verdict. OPERATOR ONLY - a reach count is a distance."""
    out = {v: 0 for v in ORDER}
    for row in rows:
        out[row["verdict"]] = out.get(row["verdict"], 0) + 1
    return out


def _epoch(iso) -> float:
    when = _parse(iso)
    return when.timestamp() if when else 0.0


def _parse(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
