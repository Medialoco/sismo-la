# Technical architecture

## Overview

The UNO Q is used as a heterogeneous dual-processor system whose two cores
communicate over the Arduino Bridge (RPC):

- **STM32U585 MCU**: real-time, deterministic task. IMU sampling and event
  detection. This is the core that "never misses a shake".
- **Dragonwing MPU (Debian)**: high-level, non-real-time tasks — networking,
  correlation, calibration, AI, web UI.

## Processing pipeline

1. **Acquisition (MCU)** — read 3-axis acceleration at a fixed rate (target
   100–200 Hz). Gravity is removed by tracking a slow average, and we work on the
   magnitude of the dynamic acceleration vector.

2. **STA/LTA detection (MCU)** — the standard seismology algorithm:
   - `STA` = short-term average (e.g. 0.5 s) of the signal energy.
   - `LTA` = long-term average (e.g. 10 s).
   - Trigger when `STA/LTA > on_threshold` (e.g. 4), end when `< off_threshold`
     (e.g. 1.5). This adapts automatically to the ambient noise floor.

3. **Event characterization (MCU)** — over the triggered window: `PGA` (peak
   ground acceleration, in g), duration, approximate dominant frequency
   (zero-crossing count). Emits a compact event message.

4. **MCU → MPU transport** — in production: the **App Lab Bridge (RPC)**. For the
   prototype and PC development: **JSON lines over the serial port**. The Python
   code reads through an "event source" abstraction so both work.

5. **USGS correlation (MPU)** — for each local event, search for a USGS
   earthquake **≥ M3** within a 160 km radius of LA and within a time window (see
   clock note below). A match is a high-confidence calibration point.

6. **Calibration (MPU)** — update the amplitude → magnitude regression (see
   `calibration.md`). Persisted to disk so it survives restarts.

7. **Classification (MPU, Edge Impulse)** — a lightweight model classifies the
   event window: `earthquake` vs `noise` (truck, door, footsteps...). This cuts
   the false positives inherent to a low-cost MEMS sensor.

8. **Presentation (MPU)** — web dashboard (App Lab brick): live acceleration,
   local events, recent USGS earthquakes, calibration state, estimated magnitude.

## The second channel: retrospective search

Steps 1–8 describe a station that waits to trigger. That path tests on the order
of 170,000 windows a day, and the false-alarm budget that implies is what sets
its threshold — well above the noise floor. Alongside it runs a channel that
works the other way round:

A. **Continuous envelope (MCU)** — independently of any trigger, the band-passed
   signal is reduced to one peak and one rms per second and shipped in batches of
   ten (`mcu_envelope`). A few bytes a second.

B. **Absolute dating (MPU)** — `python/envelope.py` writes those samples to
   `envelope/YYYY-MM-DD.csv`, one file per UTC day, purged past a retention
   window. **Each batch is dated on arrival, from the NTP-synced host clock**;
   the MCU's `millis()` only spaces the ten samples inside the batch. This is not
   a detail: that oscillator was measured 1099 ppm slow, which is 10 s of error
   in three hours — the width of the search window itself.

C. **Search at a known instant (MPU)** — `python/retro.py` takes each cataloged
   event, propagates P and S arrivals to the station (`pipeline.travel_time_window`),
   and compares the envelope inside that window against the dispersion of the
   preceding minutes, measured with a median and a MAD so a single spike cannot
   set the bar. Above a threshold in units of that local dispersion, the event is
   marked confirmed.

Testing a handful of windows per earthquake instead of 170,000 a day buys the
same confidence far closer to the noise: a factor 7 to 8 in amplitude, one
magnitude unit.

**These two channels are different claims and the code never merges them.** The
journal tags each record (`eventlog.kind_of`), `matched_pairs` and
`recent_events` return autonomous triggers only, confirmations have their own
accessor and their own key in the published snapshot, `audit.py` excludes them
from scoring by default, and neither the dashboard nor the public page shows them
in the same list. A confirmation is real ground motion; it is not a detection the
station made, because the catalog is what said where to look.

## The audit: what should have been felt

Both channels above answer "what did the station see". Neither answers the
question a run of zeros provokes: *was there anything to see?*
`python/expected.py` does, on the same thread as the retrospective search
because it needs the same two inputs.

D. **Predicted amplitude** — `REF_GMPE` gives the median ground motion each
   cataloged event should have delivered at the station. A model, with 0.39 log10
   of scatter, and labelled as such everywhere it appears.

E. **Measured noise at that instant** — the median of the recorded envelope over
   the three minutes before the arrival window. The trigger is STA/LTA, so its
   threshold in g is 8.55 times whatever the station was sitting in at the time,
   a ratio fixed by two measurements rather than chosen. This is what stops the
   audit reporting a fault for an earthquake that arrived during a footstep.

F. **Verdict** — the scatter of the fit converted to a detection probability, as
   the published sensitivity figures already do, and crossed with the journal:
   `out-of-reach`, `marginal`, `triggered`, `confirmed`, `missed`, or
   `no-coverage` when there was no recording at that instant. Only `missed` is a
   problem, and it means a fault rather than an earthquake.

The per-event output stays inside the station's own network. A detection
probability is a monotone function of hypocentral distance once the magnitude is
known, so a dozen rows trilaterate the station; `strip_watchlist` reduces the
published snapshot to three counts, unconditionally. Full method, validation and
limits in [`expected-vs-observed.md`](expected-vs-observed.md).

## Note on time synchronization

This is the tricky part. The MCU has no absolute time; the MPU does (NTP over
WiFi). Strategy:

- The MPU timestamps the reception of each MCU event (Bridge latency is small and
  bounded).
- The correlation window must absorb: seismic wave propagation delay (P/S, several
  seconds depending on distance), clock drift, and USGS publication delay (often a
  few minutes). So we correlate **after the fact** over recent history, not in
  strict real time.

## Acknowledged "low-cost" trade-offs

- A single I²C IMU, no dedicated analog acquisition chain.
- No precise leveling/orientation: using the magnitude of the dynamic vector makes
  detection insensitive to orientation.
- The intelligence is in software (STA/LTA + calibration + AI), not in the sensor.
