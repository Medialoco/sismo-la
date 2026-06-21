# Sismo-LA — Low-cost community seismograph for Los Angeles

A **low-cost** seismic node built on the **Arduino UNO Q**, made credible by
**continuous self-calibration against the USGS catalog**.

Project for the
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
contest. Target category: **Best Social Impact** (alternative: Industrial IoT).

## Idea in one sentence

A cheap MEMS sensor is not a seismometer. But in Los Angeles, the USGS catalog
provides a permanent ground truth (time, magnitude, distance). By **correlating**
locally measured shaking with confirmed earthquakes **≥ M3**, the device
**learns its own response function**: it becomes a useful seismograph without
expensive hardware.

## Why it is realistic (and its limits)

- **Realistic**: detecting a **nearby M3–M4 earthquake** (a few tens of km) with
  an LSM6DSOX-class IMU, because the local peak ground acceleration (PGA) rises
  above the sensor noise floor.
- **Realistic**: calibrating amplitude ↔ magnitude/distance by regression on
  USGS-confirmed events.
- **Acknowledged limit**: no teleseismic detection (distant earthquakes) — that
  requires a geophone. This is a **local strong-motion detector**, not a research
  seismometer.
- **Prior art**: MyShake (UC Berkeley), Quake-Catcher Network, Raspberry Shake.

## Dual-brain architecture

```
                Arduino UNO Q
 ┌───────────────────────────┬───────────────────────────┐
 │   STM32U585 (MCU)         │   Dragonwing QRB2210 (MPU) │
 │   real time               │   Debian Linux             │
 ├───────────────────────────┼───────────────────────────┤
 │ - reads the IMU (LSM6DSOX)│ - WiFi                     │
 │   ~100-200 Hz             │ - USGS feed (≥ M3, 160 km) │
 │ - STA/LTA detection       │ - temporal correlation     │
 │ - captures window + PGA   │ - calibration (regression) │
 │ - emits the event ────────┼─► - Edge Impulse classifier│
 │   (Bridge / Serial)       │ - App Lab web dashboard    │
 └───────────────────────────┴───────────────────────────┘
                          USGS: https://earthquake.usgs.gov/fdsnws/event/1/
```

## Hardware

- **Arduino UNO Q** (built-in WiFi).
- **IMU**: Modulino Movement (LSM6DSOX) over Qwiic, or any compatible I²C
  accelerometer. *(To be adapted to the connectivity actually available.)*
- USB-C power.
- Optional: HDMI display for the local dashboard.

## Repository layout

```
sismo-la/
├── README.md
├── app.yaml                  # App Lab manifest (skeleton, to adapt)
├── docs/
│   ├── architecture.md
│   ├── calibration.md        # the core idea: USGS calibration
│   └── hackster-submission.md # checklist to follow the contest guidelines
├── firmware/seismo_mcu/
│   └── seismo_mcu.ino        # MCU: STA/LTA + event emission
├── app/
│   ├── main.py               # orchestration (reads MCU, correlates, calibrates)
│   ├── usgs.py               # USGS catalog client (LA, ≥ M3)
│   ├── calibration.py        # persistent calibration model
│   ├── requirements.txt
│   └── config.example.yaml
└── web/index.html            # dashboard placeholder
```

## Quick start (PC development, no hardware)

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
python main.py --mock        # simulates MCU events + queries USGS
```

The `--mock` mode generates fake shakes to test the full chain (correlation,
calibration, display) without the UNO Q.

## Roadmap

- [x] Project scaffold + feasibility analysis.
- [ ] MCU STA/LTA sketch validated on a desk (tapping the desk triggers it).
- [ ] MCU → Linux bridge via App Lab Bridge (replaces the prototype's Serial).
- [ ] Robust temporal correlation (clock, P/S window, drift).
- [ ] Calibration: accumulate real M3+ events over LA for a few weeks.
- [ ] Edge Impulse model: earthquake vs noise (truck, door, footsteps).
- [ ] App Lab dashboard + alerts.

## Calibration in brief

For each local shake, we look for a USGS-confirmed earthquake within a time
window. On a match, we add the triple `(log10(PGA), magnitude, distance)` to the
calibration set and re-fit the regression
`Mw ≈ a·log10(PGA) + b·log10(distance) + c`. Details in
[`docs/calibration.md`](docs/calibration.md).
