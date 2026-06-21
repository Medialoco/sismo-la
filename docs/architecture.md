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
